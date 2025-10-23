#app/routers/departments.py
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, func
from sqlalchemy.exc import IntegrityError
import redis.asyncio as redis
from app.core.cache import get_redis
from app.services.cache_sync import refresh_one_department
from app.db.session import get_session
from app.db.models import Department, AppUser, Role, DepartmentRole
from app.core.deps import get_current_user, require_admin

router = APIRouter(prefix="/departments", tags=["departments"])

# ----- Schemas
class DepartmentOut(BaseModel):
    department_id: int
    name: str
    location: str

class DepartmentCreateIn(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    location: Optional[str] = Field(default="HQ", max_length=50)

class DepartmentUpdateIn(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=50)
    location: Optional[str] = Field(default=None, max_length=50)

# ----- Read: list all (auth required)
@router.get("", response_model=List[DepartmentOut])
async def list_departments(
    limit: int = 100,
    offset: int = 0,
    session: AsyncSession = Depends(get_session),
    #_: AppUser = Depends(get_current_user),
):
    rows = (
        await session.execute(
            select(Department).order_by(Department.department_id).limit(limit).offset(offset)
        )
    ).scalars().all()
    return [DepartmentOut(department_id=d.department_id, name=d.name, location=d.location) for d in rows]

# ----- Read: one
@router.get("/{department_id}", response_model=DepartmentOut)
async def get_department(
    department_id: int,
    session: AsyncSession = Depends(get_session),
    _: AppUser = Depends(get_current_user),
):
    d = await session.get(Department, department_id)
    if not d:
        raise HTTPException(status_code=404, detail="Department not found")
    return DepartmentOut(department_id=d.department_id, name=d.name, location=d.location)

# ----- Create (admin only)
@router.post("", response_model=DepartmentOut, status_code=status.HTTP_201_CREATED)
async def create_department(
    payload: DepartmentCreateIn,
    session: AsyncSession = Depends(get_session),
    __: AppUser = Depends(require_admin),
):
    d = Department(name=payload.name.strip(), location=(payload.location or "HQ").strip())
    session.add(d)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=409, detail="Department name already exists")
    r = await get_redis()
    await refresh_one_department(session, r, d.department_id)
    return DepartmentOut(department_id=d.department_id, name=d.name, location=d.location)

# ----- Update (admin only)
@router.patch("/{department_id}", response_model=DepartmentOut)
async def update_department(
    department_id: int,
    payload: DepartmentUpdateIn,
    session: AsyncSession = Depends(get_session),
    __: AppUser = Depends(require_admin),
):
    d = await session.get(Department, department_id)
    if not d:
        raise HTTPException(status_code=404, detail="Department not found")

    changed = False
    if payload.name is not None:
        nm = payload.name.strip()
        if nm and nm != d.name:
            d.name = nm
            changed = True
    if payload.location is not None and payload.location.strip() != d.location:
        d.location = payload.location.strip()
        changed = True

    if not changed:
        return DepartmentOut(department_id=d.department_id, name=d.name, location=d.location)

    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=409, detail="Department name already exists")
    r = await get_redis()
    await refresh_one_department(session, r, d.department_id)
    return DepartmentOut(department_id=d.department_id, name=d.name, location=d.location)

# ----- Delete (admin only)
@router.delete("/{department_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_department(
    department_id: int,
    session: AsyncSession = Depends(get_session),
    __: AppUser = Depends(require_admin),
):
    d = await session.get(Department, department_id)
    if not d:
        raise HTTPException(status_code=404, detail="Department not found")

    # prevent delete if users still belong to this department
    in_use = await session.scalar(select(func.count()).select_from(AppUser).where(AppUser.department_id == department_id))
    if in_use and int(in_use) > 0:
        raise HTTPException(status_code=409, detail="Department has users; reassign users before deleting")

    await session.delete(d)
    await session.commit()
    r = await get_redis()
    await refresh_one_department(session, r, department_id)
    return

# ===== Department <-> Role mapping =====

class RoleOut(BaseModel):
    role_id: int
    name: str

@router.get("/{department_id}/roles", response_model=List[RoleOut])
async def list_department_roles(
    department_id: int,
    session: AsyncSession = Depends(get_session),
    #_: AppUser = Depends(get_current_user),
):
    # ensure department exists
    if not await session.get(Department, department_id):
        raise HTTPException(status_code=404, detail="Department not found")

    rows = (
        await session.execute(
            select(Role)
            .join(DepartmentRole, DepartmentRole.role_id == Role.role_id)
            .where(DepartmentRole.department_id == department_id)
            .order_by(Role.role_id)
        )
    ).scalars().all()
    return [RoleOut(role_id=r.role_id, name=r.name) for r in rows]

@router.put("/{department_id}/roles/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
async def assign_role_to_department(
    department_id: int,
    role_id: int,
    session: AsyncSession = Depends(get_session),
    __: AppUser = Depends(require_admin),
):
    if not await session.get(Department, department_id):
        raise HTTPException(status_code=404, detail="Department not found")
    if not await session.get(Role, role_id):
        raise HTTPException(status_code=404, detail="Role not found")

    exists = await session.scalar(
        select(DepartmentRole).where(
            DepartmentRole.department_id == department_id, DepartmentRole.role_id == role_id
        )
    )
    if not exists:
        session.add(DepartmentRole(department_id=department_id, role_id=role_id))
        await session.commit()
        r = await get_redis()
        await refresh_one_department(session, r, department_id)
    return

@router.delete("/{department_id}/roles/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
async def unassign_role_from_department(
    department_id: int,
    role_id: int,
    session: AsyncSession = Depends(get_session),
    __: AppUser = Depends(require_admin),
):
    await session.execute(
        delete(DepartmentRole).where(
            DepartmentRole.department_id == department_id, DepartmentRole.role_id == role_id
        )
    )
    await session.commit()
    r = await get_redis()
    await refresh_one_department(session, r, department_id)
    return
