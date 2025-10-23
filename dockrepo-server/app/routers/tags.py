from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select ,func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
import json
import redis.asyncio as redis

from app.core.deps import get_current_user, require_admin
from app.core.cache import get_redis
from app.db.session import get_session
from app.db.models import Tag
from app.services.cache_sync import refresh_all_tags

router = APIRouter(prefix="/tags", tags=["tags"])

# --------- Schemas
class TagOut(BaseModel):
    tag_id: int
    name: str

class TagCreateIn(BaseModel):
    name: str = Field(min_length=1, max_length=50)

class TagUpdateIn(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=50)

# --------- Helpers
def _to_out(t: Tag) -> TagOut:
    return TagOut(tag_id=t.tag_id, name=t.name)

# --------- List / typeahead
@router.get("", response_model=List[TagOut])
async def list_tags(
    q: Optional[str] = Query(None, description="typeahead on name"),
    limit: int = Query(20, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
    _: str = Depends(get_current_user),
    r: redis.Redis = Depends(get_redis),
):
    # Fast-path from Redis lex index if q is provided
    if q:
        prefix = q.strip().lower()
        try:
            names: list[str] = await r.zrangebylex("tag:lex", f"[{prefix}", f"[{prefix}\xff", 0, limit)
            if names:
                pipe = r.pipeline()
                for nm in names:
                    pipe.hget("tag:name2id", nm)
                ids = await pipe.execute()  # <- get all results in one await
                keys = [f"tag:{tid}" for tid in ids if tid]
                if keys:
                    vals = await r.mget(keys)
                    out: list[TagOut] = []
                    for v in vals:
                        if not v:
                            continue
                        d = json.loads(v)
                        out.append(TagOut(tag_id=int(d["tag_id"]), name=d["name"]))
                    if out:
                        return out[:limit]
        except Exception:
            # fall through to DB query if Redis errors
            pass

    # DB fallback (or full list)
    stmt = select(Tag).order_by(Tag.name).limit(limit)
    if q:
        stmt = stmt.where(Tag.name.ilike(f"%{q}%"))
    rows = (await session.execute(stmt)).scalars().all()
    return [_to_out(t) for t in rows]

# --------- Get one
@router.get("/{tag_id}", response_model=TagOut)
async def get_tag(
    tag_id: int,
    session: AsyncSession = Depends(get_session),
    _: str = Depends(get_current_user),
):
    t = await session.get(Tag, tag_id)
    if not t:
        raise HTTPException(status_code=404, detail="Tag not found")
    return _to_out(t)

# --------- Create (admin)
@router.post("", response_model=TagOut, status_code=status.HTTP_201_CREATED)
async def create_tag(
    payload: TagCreateIn,
    session: AsyncSession = Depends(get_session),
    _: "AppUser" = Depends(get_current_user),          # <-- any logged-in user
    r: redis.Redis = Depends(get_redis),
):
    # normalize: collapse internal whitespace, trim
    raw = payload.name or ""
    name = " ".join(raw.split()).strip()
    if not name:
        raise HTTPException(status_code=400, detail="Tag name must not be empty")

    # case-insensitive get-or-create
    existing = await session.scalar(
        select(Tag).where(func.lower(Tag.name) == name.lower())
    )
    if existing:
        # idempotent: return the existing tag
        return _to_out(existing)

    t = Tag(name=name)
    session.add(t)
    try:
        await session.commit()
    except IntegrityError:
        # race: someone inserted same (case-insensitive) name concurrently
        await session.rollback()
        again = await session.scalar(
            select(Tag).where(func.lower(Tag.name) == name.lower())
        )
        if again:
            return _to_out(again)
        raise HTTPException(status_code=409, detail="Tag name already exists")

    # keep Redis tag cache in sync
    await refresh_all_tags(session, r)
    return _to_out(t)
# --------- Update (admin)
@router.patch("/{tag_id}", response_model=TagOut)
async def update_tag(
    tag_id: int,
    payload: TagUpdateIn,
    session: AsyncSession = Depends(get_session),
    __: str = Depends(require_admin),
    r: redis.Redis = Depends(get_redis),
):
    t = await session.get(Tag, tag_id)
    if not t:
        raise HTTPException(status_code=404, detail="Tag not found")
    if payload.name and payload.name.strip() != t.name:
        t.name = payload.name.strip()
        try:
            await session.commit()
        except IntegrityError:
            await session.rollback()
            raise HTTPException(status_code=409, detail="Tag name already exists")

    await refresh_all_tags(session, r)
    return _to_out(t)
# --------- Delete (admin)
@router.delete("/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tag(
    tag_id: int,
    session: AsyncSession = Depends(get_session),
    __: str = Depends(require_admin),
    r: redis.Redis = Depends(get_redis),
):
    t = await session.get(Tag, tag_id)
    if not t:
        raise HTTPException(status_code=404, detail="Tag not found")
    await session.delete(t)
    await session.commit()
    await refresh_all_tags(session, r)
    return
