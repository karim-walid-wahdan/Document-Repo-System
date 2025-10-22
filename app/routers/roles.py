#app/routers/roles.py
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, func
from sqlalchemy.exc import IntegrityError
from app.core.cache import get_redis
from app.services.cache_sync import refresh_departments_with_role,refresh_one_department
from app.db.session import get_session
from app.db.models import Role, AppUser ,DepartmentRole
from app.core.deps import get_current_user, require_admin

router = APIRouter(prefix="/roles", tags=["roles"])

class RoleOut(BaseModel):
    role_id: int
    name: str

class RoleCreateIn(BaseModel):
    name: str = Field(min_length=1, max_length=15)

class RoleUpdateIn(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=15)

@router.get("", response_model=List[RoleOut])
async def list_roles(
    limit: int = 100,
    offset: int = 0,
    session: AsyncSession = Depends(get_session),
    _: AppUser = Depends(get_current_user),
):
    rows = (await session.execute(select(Role).order_by(Role.role_id).limit(limit).offset(offset))).scalars().all()
    return [RoleOut(role_id=r.role_id, name=r.name) for r in rows]

@router.get("/{role_id}", response_model=RoleOut)
async def get_role(
    role_id: int,
    session: AsyncSession = Depends(get_session),
    _: AppUser = Depends(get_current_user),
):
    r = await session.get(Role, role_id)
    if not r:
        raise HTTPException(status_code=404, detail="Role not found")
    return RoleOut(role_id=r.role_id, name=r.name)

@router.post("", response_model=RoleOut, status_code=status.HTTP_201_CREATED)
async def create_role(
    payload: RoleCreateIn,
    session: AsyncSession = Depends(get_session),
    __: AppUser = Depends(require_admin),
):
    r = Role(name=payload.name.strip())
    session.add(r)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=409, detail="Role name already exists")
    return RoleOut(role_id=r.role_id, name=r.name)

@router.patch("/{role_id}", response_model=RoleOut)
async def update_role(
    role_id: int,
    payload: RoleUpdateIn,
    session: AsyncSession = Depends(get_session),
    __: AppUser = Depends(require_admin),
):
    r = await session.get(Role, role_id)
    if not r:
        raise HTTPException(status_code=404, detail="Role not found")
    if payload.name and payload.name.strip() != r.name:
        r.name = payload.name.strip()
        try:
            await session.commit()
        except IntegrityError:
            await session.rollback()
            raise HTTPException(status_code=409, detail="Role name already exists")
    rr = await get_redis()
    await refresh_departments_with_role(session, rr, r.role_id)
    
    return RoleOut(role_id=r.role_id, name=r.name)

@router.delete("/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_role(
    role_id: int,
    session: AsyncSession = Depends(get_session),
    __: AppUser = Depends(require_admin),
):
    # prevent delete if any user still uses this role
    in_use = await session.scalar(select(func.count()).select_from(AppUser).where(AppUser.role_id == role_id))
    if in_use and int(in_use) > 0:
        raise HTTPException(status_code=409, detail="Role is assigned to users; reassign users before deleting")
    dep_ids = (
        await session.execute(
            select(DepartmentRole.department_id).where(DepartmentRole.role_id == role_id)
        )
    ).scalars().all()

    # existing in_use guard for users...
    r_obj = await session.get(Role, role_id)
    if not r_obj:
        raise HTTPException(status_code=404, detail="Role not found")
    await session.delete(r_obj)
    await session.commit()

    rr = await get_redis()
    for dep_id in dep_ids:
        await refresh_one_department(session, rr, int(dep_id))
    return
