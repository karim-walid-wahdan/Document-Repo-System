# app/routers/documents.py
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Annotated, Optional, List

import redis.asyncio as redis
from fastapi import (
    APIRouter,
    Depends,
    UploadFile,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    status,
)

from pydantic import BaseModel, Field
from sqlalchemy import (
    and_,
    delete,
    desc,
    exists,
    func,
    select,
    update,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import get_redis
from app.core.deps import get_current_user
from app.core.settings import settings
from app.db.models import (
    ActionLog,
    AppUser,
    Department,
    DocAccess,
    Document,
    DocumentTag,
    DocumentVersion,
    DocVisibility,
    Role,
    Tag,
)
from app.db.session import get_session
from app.storage.s3 import get_s3_client

router = APIRouter(prefix="/documents", tags=["documents"])

# ---------------------------- Constants / thresholds ----------------------------

# Permission thresholds based on DocAccess.access_level (0..10)
OWNER_THRESHOLD = 2       # <= 2 => owner
EDIT_THRESHOLD = 5        # <  5 => can edit
MODIFY_THRESHOLD = 3      # <  3 => can delete

# Enum API <-> numeric mapping for ACLs
class PermLevel(str, Enum):
    view = "view"
    edit = "edit"
    owner = "owner"

_LEVEL_TO_NUM = {PermLevel.owner: 2, PermLevel.edit: 4, PermLevel.view: 8}


# ---------------------------- Schemas ----------------------------

class DocumentOut(BaseModel):
    doc_id: int
    title: str
    description: str
    visibility: DocVisibility
    updated_at: datetime


class VersionOut(BaseModel):
    version_no: int
    storage_key: str
    file_size: int
    uploaded_at: datetime
    uploaded_by: int
    is_latest: bool


class SearchOut(BaseModel):
    doc: DocumentOut
    tags: List[str] = Field(default_factory=list)
    latest_version: Optional[VersionOut] = None


class ActionLogOut(BaseModel):
    log_id: int
    action_type: str
    ip: str
    time_stamp: datetime
    user_id: int
    doc_id: int
    version_no: int


class DocumentUpdateIn(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    visibility: Optional[DocVisibility] = None


class PermsOut(BaseModel):
    can_view: bool
    can_edit: bool
    can_modify: bool
    access_level: Optional[int] = None  # None => no doc_access row for caller's dept


class PermissionOut(BaseModel):
    department_id: int
    level: PermLevel


class PermissionIn(BaseModel):
    level: PermLevel


class BulkPermissionsIn(BaseModel):
    departments: list[PermissionOut]  # {department_id, level}


class DocumentDetailsOut(BaseModel):
    doc: DocumentOut
    tags: List[str] = Field(default_factory=list)
    latest_version: Optional[VersionOut] = None
    perms: PermsOut


# ---------------------------- Helper functions ----------------------------

async def _next_version_no(session: AsyncSession, doc_id: int) -> int:
    q = await session.execute(
        select(func.coalesce(func.max(DocumentVersion.version_no), 0)).where(
            DocumentVersion.doc_id == doc_id
        )
    )
    return int(q.scalar_one()) + 1


async def _log_action(
    session: AsyncSession,
    *,
    user_id: int,
    doc_id: int,
    version_no: int,
    action_type: str,
    ip: str,
) -> None:
    """Non-fatal audit insert (swallowed exceptions)."""
    try:
        entry = ActionLog(
            action_type=action_type,
            ip=ip,
            user_id=user_id,
            doc_id=doc_id,
            version_no=version_no,
        )
        session.add(entry)
        await session.commit()
    except Exception:
        await session.rollback()


async def _access_level_for(
    session: AsyncSession, *, doc_id: int, department_id: int
) -> int | None:
    lvl = await session.scalar(
        select(DocAccess.access_level).where(
            DocAccess.doc_id == doc_id, DocAccess.department_id == department_id
        )
    )
    return int(lvl) if lvl is not None else None


async def _is_admin(session: AsyncSession, user: AppUser) -> bool:
    rname = await session.scalar(select(Role.name).where(Role.role_id == user.role_id))
    return (rname or "").lower() == "admin"


async def _require_edit(session: AsyncSession, *, doc_id: int, user: AppUser) -> int:
    if await _is_admin(session, user):
        return 0
    lvl = await _access_level_for(
        session, doc_id=doc_id, department_id=user.department_id
    )
    if lvl is None or lvl >= EDIT_THRESHOLD:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Edit access required for this document",
        )
    return lvl


async def _require_modify(
    session: AsyncSession, *, doc_id: int, user: AppUser
) -> int:
    if await _is_admin(session, user):
        return 0
    lvl = await _access_level_for(
        session, doc_id=doc_id, department_id=user.department_id
    )
    if lvl is None or lvl >= MODIFY_THRESHOLD:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Modify/delete access required for this document",
        )
    return lvl


def _num_to_level(n: int) -> PermLevel:
    if n <= OWNER_THRESHOLD:
        return PermLevel.owner
    if n < EDIT_THRESHOLD:
        return PermLevel.edit
    return PermLevel.view


async def _require_can_manage_perms(
    session: AsyncSession, *, doc_id: int, user: AppUser
) -> None:
    """Admin or owner (<=2) can manage ACLs."""
    if await _is_admin(session, user):
        return
    lvl = await _access_level_for(
        session, doc_id=doc_id, department_id=user.department_id
    )
    if lvl is None or int(lvl) > OWNER_THRESHOLD:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Owner-level access required to manage permissions",
        )


# ---------------------------- Endpoints ----------------------------

@router.post("", response_model=VersionOut, status_code=status.HTTP_201_CREATED)
async def create_document(
    request: Request,
    title: Annotated[str, Form()],
    description: Annotated[str, Form()],
    visibility: Annotated[DocVisibility, Form()] = DocVisibility.internal,
    tags: Annotated[Optional[str], Form()] = None,  # comma-separated
    file: UploadFile = File(...),
    user: AppUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """
    Create a new document (or add a new version if title already exists).
    If a **brand new** doc is created (v1), the uploader's department is granted
    **owner** permission (access_level=2).
    """
    # basic file validation
    filename = (file.filename or "").strip()
    if not filename:
        raise HTTPException(status_code=400, detail="File must have a name")
    if filename.lower().endswith(".exe"):
        raise HTTPException(
            status_code=415, detail="Executable files are not allowed"
        )

    now = datetime.now(timezone.utc)

    # find-or-create by title
    doc = await session.scalar(select(Document).where(Document.title == title))
    brand_new = False
    if doc:
        # new version of existing doc
        vno = await _next_version_no(session, doc.doc_id)
        # refresh metadata (optional)
        doc.description = description or doc.description
        doc.visibility = visibility or doc.visibility
    else:
        # brand new doc
        brand_new = True
        doc = Document(
            title=title,
            description=description,
            visibility=visibility,
            created_at=now,
            updated_at=now,
        )
        session.add(doc)
        await session.flush()  # get doc_id
        vno = 1

    # tags
    tag_names = [t.strip() for t in (tags or "").split(",") if t.strip()]
    if tag_names:
        existing = dict(
            (name, tid)
            for name, tid in (
                await session.execute(
                    select(Tag.name, Tag.tag_id).where(Tag.name.in_(tag_names))
                )
            ).all()
        )
        for name in tag_names:
            tid = existing.get(name)
            if not tid:
                t = Tag(name=name)
                session.add(t)
                await session.flush()
                tid = t.tag_id
                existing[name] = tid
            # avoid duplicate link
            link_exists = await session.scalar(
                select(DocumentTag).where(
                    DocumentTag.doc_id == doc.doc_id, DocumentTag.tag_id == tid
                )
            )
            if not link_exists:
                session.add(DocumentTag(doc_id=doc.doc_id, tag_id=tid))

    # upload file to S3
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    key = f"docs/{doc.doc_id}/v{vno}/{filename}"
    s3 = get_s3_client()
    try:
        s3.put_object(
            Bucket=settings.S3_BUCKET,
            Key=key,
            Body=data,
            ContentType=file.content_type or "application/octet-stream",
        )
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to upload to storage: {e}")

    # unset previous latest if new version
    if vno > 1:
        await session.execute(
            update(DocumentVersion)
            .where(
                DocumentVersion.doc_id == doc.doc_id,
                DocumentVersion.is_latest == True,  # noqa: E712
            )
            .values(is_latest=False)
        )

    # insert version row
    ver = DocumentVersion(
        doc_id=doc.doc_id,
        version_no=vno,
        storage_key=key,
        file_size=len(data),
        is_latest=True,
        uploaded_at=now,
        uploaded_by=user.user_id,
    )
    session.add(ver)
    doc.updated_at = now

    # OWNER GRANT for creator's department (only when brand-new)
    if brand_new:
        session.add(
            DocAccess(
                department_id=user.department_id,
                doc_id=doc.doc_id,
                access_level=OWNER_THRESHOLD,
            )
        )

    # response before commit
    out = VersionOut(
        version_no=vno,
        storage_key=key,
        file_size=len(data),
        uploaded_at=now,
        uploaded_by=user.user_id,
        is_latest=True,
    )

    await session.commit()

    # audit (best-effort)
    try:
        await _log_action(
            session,
            user_id=user.user_id,
            doc_id=doc.doc_id,
            version_no=vno,
            action_type="upload",
            ip=str(request.client.host if request.client else "unknown"),
        )
    except Exception:
        pass

    return out


@router.post("/{doc_id}/versions", response_model=VersionOut, status_code=status.HTTP_201_CREATED)
async def add_version(
    request: Request,
    doc_id: int,
    file: UploadFile = File(...),
    user: AppUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Add a new version. Requires edit permission (or admin)."""
    doc = await session.get(Document, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # must have edit access
    await _require_edit(session, doc_id=doc_id, user=user)

    filename = (file.filename or "").strip()
    if not filename:
        raise HTTPException(status_code=400, detail="File must have a name")
    if filename.lower().endswith(".exe"):
        raise HTTPException(
            status_code=415, detail="Executable files are not allowed"
        )

    now = datetime.now(timezone.utc)
    vno = await _next_version_no(session, doc_id)
    key = f"docs/{doc_id}/v{vno}/{filename}"

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    s3 = get_s3_client()
    try:
        s3.put_object(
            Bucket=settings.S3_BUCKET,
            Key=key,
            Body=data,
            ContentType=file.content_type or "application/octet-stream",
        )
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to upload to storage: {e}")

    # unset previous latest
    await session.execute(
        update(DocumentVersion)
        .where(
            DocumentVersion.doc_id == doc_id, DocumentVersion.is_latest == True  # noqa: E712
        )
        .values(is_latest=False)
    )

    # insert new version
    ver = DocumentVersion(
        doc_id=doc_id,
        version_no=vno,
        storage_key=key,
        file_size=len(data),
        is_latest=True,
        uploaded_at=now,
        uploaded_by=user.user_id,
    )
    session.add(ver)
    doc.updated_at = now

    out = VersionOut(
        version_no=vno,
        storage_key=key,
        file_size=len(data),
        uploaded_at=now,
        uploaded_by=user.user_id,
        is_latest=True,
    )

    await session.commit()

    # audit (best-effort)
    try:
        await _log_action(
            session,
            user_id=user.user_id,
            doc_id=doc_id,
            version_no=vno,
            action_type="upload",
            ip=str(request.client.host if request.client else "unknown"),
        )
    except Exception:
        pass

    return out


@router.get("", response_model=list[SearchOut])
async def search_documents(
    q: Optional[str] = Query(None, description="Search in title"),
    tags: Optional[list[str]] = Query(None),
    uploader: Optional[int] = Query(None, description="Filter by uploader user_id"),
    limit: int = 25,
    offset: int = 0,
    user: AppUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """
    Search ONLY documents the caller can access:
      - public or internal, OR
      - restricted but granted to caller's department via doc_access
    """
    # accessible doc ids
    acc_all = select(Document.doc_id).where(
        Document.visibility.in_([DocVisibility.public, DocVisibility.internal])
    )
    acc_dept = select(DocAccess.doc_id).where(
        DocAccess.department_id == user.department_id
    )
    acc_union = acc_all.union_all(acc_dept).subquery("acc")
    accessible = select(acc_union.c.doc_id).distinct().subquery("accessible")

    # latest version subquery
    subq_latest = (
        select(
            DocumentVersion.doc_id,
            DocumentVersion.version_no,
            DocumentVersion.storage_key,
            DocumentVersion.file_size,
            DocumentVersion.uploaded_at,
            DocumentVersion.uploaded_by,
        )
        .where(DocumentVersion.is_latest == True)  # noqa: E712
        .subquery()
    )

    tags_agg = func.array_agg(Tag.name).filter(Tag.name.isnot(None)).label("tags")

    stmt = (
        select(
            Document,
            subq_latest.c.version_no,
            subq_latest.c.storage_key,
            subq_latest.c.file_size,
            subq_latest.c.uploaded_at,
            subq_latest.c.uploaded_by,
            tags_agg,
        )
        .join(accessible, accessible.c.doc_id == Document.doc_id)
        .join(subq_latest, Document.doc_id == subq_latest.c.doc_id, isouter=True)
        .join(DocumentTag, DocumentTag.doc_id == Document.doc_id, isouter=True)
        .join(Tag, Tag.tag_id == DocumentTag.tag_id, isouter=True)
        .group_by(
            Document.doc_id,
            subq_latest.c.version_no,
            subq_latest.c.storage_key,
            subq_latest.c.file_size,
            subq_latest.c.uploaded_at,
            subq_latest.c.uploaded_by,
        )
        .order_by(desc(Document.updated_at))
        .limit(limit)
        .offset(offset)
    )

    if q:
        stmt = stmt.where(Document.title.ilike(f"%{q}%"))
    if tags:
        stmt = stmt.having(func.bool_or(Tag.name.in_(tags)))
    if uploader:
        stmt = stmt.where(subq_latest.c.uploaded_by == uploader)

    rows = (await session.execute(stmt)).all()

    results: list[SearchOut] = []
    for doc, vno, key, sz, up_at, up_by, tag_arr in rows:
        results.append(
            SearchOut(
                doc=DocumentOut(
                    doc_id=doc.doc_id,
                    title=doc.title,
                    description=doc.description,
                    visibility=doc.visibility,
                    updated_at=doc.updated_at,
                ),
                tags=tag_arr or [],
                latest_version=(
                    VersionOut(
                        version_no=vno,
                        storage_key=key,
                        file_size=sz,
                        uploaded_at=up_at,
                        uploaded_by=up_by,
                        is_latest=True,
                    )
                    if vno
                    else None
                ),
            )
        )
    return results


@router.get("/{doc_id}/versions", response_model=list[VersionOut])
async def version_history(
    doc_id: int,
    user: AppUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    stmt = (
        select(DocumentVersion)
        .where(DocumentVersion.doc_id == doc_id)
        .order_by(desc(DocumentVersion.version_no))
    )
    rows = (await session.execute(stmt)).scalars().all()
    if not rows:
        raise HTTPException(
            status_code=404, detail="Document not found or no versions"
        )
    return [
        VersionOut(
            version_no=v.version_no,
            storage_key=v.storage_key,
            file_size=v.file_size,
            uploaded_at=v.uploaded_at,
            uploaded_by=v.uploaded_by,
            is_latest=v.is_latest,
        )
        for v in rows
    ]


@router.get("/{doc_id}/download")
async def download(
    doc_id: int,
    version: Optional[int] = None,
    session: AsyncSession = Depends(get_session),
    user: AppUser = Depends(get_current_user),
    r: redis.Redis = Depends(get_redis),
):
    # pick version
    if version is None:
        v = await session.scalar(
            select(DocumentVersion).where(
                and_(
                    DocumentVersion.doc_id == doc_id,
                    DocumentVersion.is_latest == True,  # noqa: E712
                )
            )
        )
    else:
        v = await session.scalar(
            select(DocumentVersion).where(
                and_(
                    DocumentVersion.doc_id == doc_id,
                    DocumentVersion.version_no == version,
                )
            )
        )
    if not v:
        raise HTTPException(status_code=404, detail="Version not found")

    # access check (re-enforce)
    doc = await session.get(Document, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    if doc.visibility == DocVisibility.restricted:
        allowed = await session.scalar(
            exists()
            .where(
                and_(
                    DocAccess.doc_id == doc_id,
                    DocAccess.department_id == user.department_id,
                )
            )
            .select()
        )
        if not allowed:
            raise HTTPException(
                status_code=403, detail="Not permitted for your department"
            )

    # filename for disposition
    fname = v.storage_key.rsplit("/", 1)[-1] or f"doc-{doc_id}-v{v.version_no}"

    # presigned URL
    s3 = get_s3_client()
    url = s3.generate_presigned_url(
        "get_object",
        Params={
            "Bucket": settings.S3_BUCKET,
            "Key": v.storage_key,
            "ResponseContentDisposition": f'attachment; filename="{fname}"',
        },
        ExpiresIn=300,
    )

    # usage cache
    await r.setex(f"recent:doc:{doc_id}", 86400, v.storage_key)  # 24h
    await r.zincrby("hot:docs", 1, str(doc_id))

    return {"url": url}


# ---------------------------- Audit read APIs ----------------------------

@router.get("/{doc_id}/actions", response_model=List[ActionLogOut])
async def list_doc_actions(
    doc_id: int,
    limit: int = 100,
    offset: int = 0,
    session: AsyncSession = Depends(get_session),
    user: AppUser = Depends(get_current_user),
):
    rows = (
        await session.execute(
            select(ActionLog)
            .where(ActionLog.doc_id == doc_id)
            .order_by(desc(ActionLog.time_stamp))
            .limit(limit)
            .offset(offset)
        )
    ).scalars().all()
    return [
        ActionLogOut(
            log_id=a.log_id,
            action_type=a.action_type,
            ip=a.ip,
            time_stamp=a.time_stamp,
            user_id=a.user_id,
            doc_id=a.doc_id,
            version_no=a.version_no,
        )
        for a in rows
    ]


@router.get("/actions", response_model=List[ActionLogOut])
async def list_actions(
    user_id: Optional[int] = Query(None),
    doc_id: Optional[int] = Query(None),
    action_type: Optional[str] = Query(None),
    since: Optional[datetime] = Query(None),
    until: Optional[datetime] = Query(None),
    limit: int = 100,
    offset: int = 0,
    session: AsyncSession = Depends(get_session),
    user: AppUser = Depends(get_current_user),
):
    stmt = select(ActionLog)
    if user_id is not None:
        stmt = stmt.where(ActionLog.user_id == user_id)
    if doc_id is not None:
        stmt = stmt.where(ActionLog.doc_id == doc_id)
    if action_type:
        stmt = stmt.where(ActionLog.action_type == action_type)
    if since:
        stmt = stmt.where(ActionLog.time_stamp >= since)
    if until:
        stmt = stmt.where(ActionLog.time_stamp <= until)

    stmt = stmt.order_by(desc(ActionLog.time_stamp)).limit(limit).offset(offset)
    rows = (await session.execute(stmt)).scalars().all()
    return [
        ActionLogOut(
            log_id=a.log_id,
            action_type=a.action_type,
            ip=a.ip,
            time_stamp=a.time_stamp,
            user_id=a.user_id,
            doc_id=a.doc_id,
            version_no=a.version_no,
        )
        for a in rows
    ]


# ---------------------------- Metadata update / delete ----------------------------

@router.patch("/{doc_id}", response_model=DocumentOut)
async def update_document_metadata(
    doc_id: int,
    payload: DocumentUpdateIn,
    request: Request,
    session: AsyncSession = Depends(get_session),
    user: AppUser = Depends(get_current_user),
):
    doc = await session.get(Document, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    await _require_edit(session, doc_id=doc_id, user=user)

    changed = False
    if payload.title is not None and payload.title.strip() and payload.title != doc.title:
        doc.title = payload.title.strip()
        changed = True
    if payload.description is not None and payload.description != doc.description:
        doc.description = payload.description
        changed = True
    if payload.visibility is not None and payload.visibility != doc.visibility:
        doc.visibility = payload.visibility
        changed = True

    if not changed:
        return DocumentOut(
            doc_id=doc.doc_id,
            title=doc.title,
            description=doc.description,
            visibility=doc.visibility,
            updated_at=doc.updated_at,
        )

    doc.updated_at = datetime.now(timezone.utc)

    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=409,
            detail="Conflict updating document (possibly duplicate title)",
        )

    # audit (best-effort) — tie to latest version
    latest_v = await session.scalar(
        select(DocumentVersion.version_no).where(
            DocumentVersion.doc_id == doc_id, DocumentVersion.is_latest == True  # noqa: E712
        )
    )
    if latest_v is not None:
        try:
            await _log_action(
                session,
                user_id=user.user_id,
                doc_id=doc_id,
                version_no=int(latest_v),
                action_type="meta_update",
                ip=str(request.client.host if request.client else "unknown"),
            )
        except Exception:
            pass

    return DocumentOut(
        doc_id=doc.doc_id,
        title=doc.title,
        description=doc.description,
        visibility=doc.visibility,
        updated_at=doc.updated_at,
    )


@router.delete("/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    doc_id: int,
    session: AsyncSession = Depends(get_session),
    user: AppUser = Depends(get_current_user),
):
    """Hard delete (keeps your current behavior)."""
    doc = await session.get(Document, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    await _require_modify(session, doc_id=doc_id, user=user)

    # If you switch to FK ON DELETE SET NULL on action_log, you can drop this manual delete.
    await session.execute(delete(ActionLog).where(ActionLog.doc_id == doc_id))

    await session.delete(doc)
    await session.commit()

    # Best-effort S3 cleanup (DB is already consistent)
    try:
        s3 = get_s3_client()
        prefix = f"docs/{doc_id}/"
        resp = s3.list_objects_v2(Bucket=settings.S3_BUCKET, Prefix=prefix)
        contents = resp.get("Contents", [])
        if contents:
            s3.delete_objects(
                Bucket=settings.S3_BUCKET,
                Delete={"Objects": [{"Key": obj["Key"]} for obj in contents], "Quiet": True},
            )
    except Exception:
        pass
    return


# ---------------------------- Details (with perms summary) ----------------------------

@router.get("/{doc_id}", response_model=DocumentDetailsOut)
async def get_document_details(
    doc_id: int,
    session: AsyncSession = Depends(get_session),
    user: AppUser = Depends(get_current_user),
):
    doc = await session.get(Document, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    level = await session.scalar(
        select(DocAccess.access_level).where(
            and_(DocAccess.doc_id == doc_id, DocAccess.department_id == user.department_id)
        )
    )
    level = int(level) if level is not None else None

    can_view = (doc.visibility != DocVisibility.restricted) or (level is not None)
    if not can_view:
        raise HTTPException(status_code=403, detail="Not permitted for your department")

    can_edit = (level is not None) and (level < EDIT_THRESHOLD)
    can_modify = (level is not None) and (level < MODIFY_THRESHOLD)

    latest = await session.scalar(
        select(DocumentVersion).where(
            and_(DocumentVersion.doc_id == doc_id, DocumentVersion.is_latest == True)  # noqa: E712
        )
    )
    latest_out = (
        VersionOut(
            version_no=latest.version_no,
            storage_key=latest.storage_key,
            file_size=latest.file_size,
            uploaded_at=latest.uploaded_at,
            uploaded_by=latest.uploaded_by,
            is_latest=latest.is_latest,
        )
        if latest
        else None
    )

    tag_rows = (
        await session.execute(
            select(Tag.name)
            .join(DocumentTag, DocumentTag.tag_id == Tag.tag_id)
            .where(DocumentTag.doc_id == doc_id)
        )
    ).scalars().all()

    return DocumentDetailsOut(
        doc=DocumentOut(
            doc_id=doc.doc_id,
            title=doc.title,
            description=doc.description,
            visibility=doc.visibility,
            updated_at=doc.updated_at,
        ),
        tags=tag_rows or [],
        latest_version=latest_out,
        perms=PermsOut(
            can_view=can_view,
            can_edit=can_edit,
            can_modify=can_modify,
            access_level=level,
        ),
    )


# ---------------------------- Permissions management ----------------------------

@router.get("/{doc_id}/permissions", response_model=list[PermissionOut])
async def list_permissions(
    doc_id: int,
    session: AsyncSession = Depends(get_session),
    user: AppUser = Depends(get_current_user),
):
    # must be able to view the document
    doc = await session.get(Document, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    has_row = await session.scalar(
        select(DocAccess).where(
            DocAccess.doc_id == doc_id, DocAccess.department_id == user.department_id
        )
    )
    if doc.visibility == DocVisibility.restricted and not has_row:
        raise HTTPException(status_code=403, detail="Not permitted for your department")

    rows = (
        await session.execute(
            select(DocAccess.department_id, DocAccess.access_level)
            .where(DocAccess.doc_id == doc_id)
            .order_by(DocAccess.department_id)
        )
    ).all()
    return [
        PermissionOut(department_id=int(dep_id), level=_num_to_level(int(lvl)))
        for dep_id, lvl in rows
    ]


@router.put("/{doc_id}/permissions/departments/{department_id}", response_model=PermissionOut)
async def upsert_permission(
    doc_id: int,
    department_id: int,
    payload: PermissionIn,
    session: AsyncSession = Depends(get_session),
    user: AppUser = Depends(get_current_user),
):
    # doc & dept exist?
    if not await session.get(Document, doc_id):
        raise HTTPException(status_code=404, detail="Document not found")
    if not await session.get(Department, department_id):
        raise HTTPException(status_code=400, detail="Invalid department_id")

    await _require_can_manage_perms(session, doc_id=doc_id, user=user)

    desired = _LEVEL_TO_NUM[payload.level]
    row = await session.scalar(
        select(DocAccess).where(
            DocAccess.doc_id == doc_id, DocAccess.department_id == department_id
        )
    )
    if row:
        row.access_level = desired
    else:
        session.add(
            DocAccess(
                doc_id=doc_id, department_id=department_id, access_level=desired
            )
        )

    await session.commit()
    return PermissionOut(department_id=department_id, level=payload.level)


@router.delete("/{doc_id}/permissions/departments/{department_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_permission(
    doc_id: int,
    department_id: int,
    session: AsyncSession = Depends(get_session),
    user: AppUser = Depends(get_current_user),
):
    if not await session.get(Document, doc_id):
        raise HTTPException(status_code=404, detail="Document not found")

    await _require_can_manage_perms(session, doc_id=doc_id, user=user)

    await session.execute(
        delete(DocAccess).where(
            DocAccess.doc_id == doc_id, DocAccess.department_id == department_id
        )
    )
    await session.commit()
    return


@router.put("/{doc_id}/permissions", response_model=list[PermissionOut])
async def replace_permissions(
    doc_id: int,
    payload: BulkPermissionsIn,
    session: AsyncSession = Depends(get_session),
    user: AppUser = Depends(get_current_user),
):
    if not await session.get(Document, doc_id):
        raise HTTPException(status_code=404, detail="Document not found")

    await _require_can_manage_perms(session, doc_id=doc_id, user=user)

    # validate departments & dedupe (last wins)
    dedup: dict[int, PermLevel] = {}
    for item in payload.departments or []:
        if not await session.get(Department, item.department_id):
            raise HTTPException(
                status_code=400, detail=f"Invalid department_id: {item.department_id}"
            )
        dedup[item.department_id] = item.level

    # replace atomically: delete all then insert new set
    await session.execute(delete(DocAccess).where(DocAccess.doc_id == doc_id))
    for dep_id, lvl in dedup.items():
        session.add(
            DocAccess(
                doc_id=doc_id, department_id=dep_id, access_level=_LEVEL_TO_NUM[lvl]
            )
        )
    await session.commit()

    out = [PermissionOut(department_id=d, level=l) for d, l in sorted(dedup.items())]
    return out


# ---------------------------- (Optional) per-version audit log ----------------------------

@router.get("/{doc_id}/versions/{version_no}/audit-log", response_model=List[ActionLogOut])
async def version_audit_log(
    doc_id: int,
    version_no: int,
    session: AsyncSession = Depends(get_session),
    user: AppUser = Depends(get_current_user),
):
    # basic view permission check (same as details)
    doc = await session.get(Document, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    level = await session.scalar(
        select(DocAccess.access_level).where(
            and_(DocAccess.doc_id == doc_id, DocAccess.department_id == user.department_id)
        )
    )
    can_view = (doc.visibility != DocVisibility.restricted) or (level is not None)
    if not can_view:
        raise HTTPException(status_code=403, detail="Not permitted for your department")

    rows = (
        await session.execute(
            select(ActionLog)
            .where(ActionLog.doc_id == doc_id, ActionLog.version_no == version_no)
            .order_by(desc(ActionLog.time_stamp))
        )
    ).scalars().all()
    return [
        ActionLogOut(
            log_id=a.log_id,
            action_type=a.action_type,
            ip=a.ip,
            time_stamp=a.time_stamp,
            user_id=a.user_id,
            doc_id=a.doc_id,
            version_no=a.version_no,
        )
        for a in rows
    ]
