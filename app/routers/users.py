# app/routers/users.py
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from app.db.session import get_session
from app.db.models import AppUser, Role, Department, DepartmentRole, DocumentVersion, ActionLog
from app.core.deps import get_current_user, require_admin
from app.core.security import hash_password

router = APIRouter(prefix="/users", tags=["users"])

# ---------- Schemas
class UserOut(BaseModel):
    user_id: int
    email: EmailStr
    created_at: Optional[str] = None  # ISO
    role_id: int
    department_id: int

class UserCreateIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=512)
    role_id: int
    department_id: int

class UserUpdateAdminIn(BaseModel):
    email: Optional[EmailStr] = None
    password: Optional[str] = Field(default=None, min_length=8, max_length=512)
    role_id: Optional[int] = None
    department_id: Optional[int] = None

# ---------- Helpers
async def _role_allowed_for_department(session: AsyncSession, *, department_id: int, role_id: int) -> bool:
    """If dept has any mappings, role must be in that set; if none, allow any role."""
    total = await session.scalar(
        select(func.count()).select_from(DepartmentRole).where(DepartmentRole.department_id == department_id)
    )
    if int(total or 0) == 0:
        return True
    exists = await session.scalar(
        select(DepartmentRole).where(
            DepartmentRole.department_id == department_id,
            DepartmentRole.role_id == role_id,
        )
    )
    return exists is not None

def _to_out(u: AppUser) -> UserOut:
    return UserOut(
        user_id=u.user_id,
        email=u.email,
        created_at=u.created_at.isoformat() if u.created_at else None,
        role_id=u.role_id,
        department_id=u.department_id,
    )

# ---------- Me
@router.get("/me", response_model=UserOut)
async def get_me(user: AppUser = Depends(get_current_user)):
    return _to_out(user)

# ---------- Admin: list
@router.get("", response_model=List[UserOut])
async def list_users(
    department_id: Optional[int] = None,
    role_id: Optional[int] = None,
    q: Optional[str] = Query(None, description="search in email"),  # <-- was Field(...)
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
    __: AppUser = Depends(require_admin),
):
    stmt = select(AppUser)
    if department_id is not None:
        stmt = stmt.where(AppUser.department_id == department_id)
    if role_id is not None:
        stmt = stmt.where(AppUser.role_id == role_id)
    if q:
        qlike = f"%{q}%"
        stmt = stmt.where(AppUser.email.ilike(qlike))
    stmt = stmt.order_by(AppUser.user_id).limit(limit).offset(offset)

    rows = (await session.execute(stmt)).scalars().all()
    return [_to_out(u) for u in rows]

# ---------- Admin: get one
@router.get("/{user_id}", response_model=UserOut)
async def get_user_admin(
    user_id: int,
    session: AsyncSession = Depends(get_session),
    __: AppUser = Depends(require_admin),
):
    u = await session.get(AppUser, user_id)
    if not u:
        raise HTTPException(status_code=404, detail="User not found")
    return _to_out(u)

# ---------- Admin: create
@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def create_user_admin(
    payload: UserCreateIn,
    session: AsyncSession = Depends(get_session),
    __: AppUser = Depends(require_admin),
):
    email = str(payload.email).lower()

    if not await session.get(Role, payload.role_id):
        raise HTTPException(status_code=400, detail="Invalid role_id")
    if not await session.get(Department, payload.department_id):
        raise HTTPException(status_code=400, detail="Invalid department_id")
    if not await _role_allowed_for_department(session, department_id=payload.department_id, role_id=payload.role_id):
        raise HTTPException(status_code=409, detail="Role not allowed for department")

    existing = await session.scalar(select(AppUser).where(AppUser.email == email))
    if existing:
        raise HTTPException(status_code=409, detail="Email already exists")

    u = AppUser(
        email=email,
        pass_hash=hash_password(payload.password),
        role_id=payload.role_id,
        department_id=payload.department_id,
    )
    session.add(u)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=400, detail="Could not create user")
    return _to_out(u)

# ---------- Admin: update
@router.patch("/{user_id}", response_model=UserOut)
async def update_user_admin(
    user_id: int,
    payload: UserUpdateAdminIn,
    session: AsyncSession = Depends(get_session),
    __: AppUser = Depends(require_admin),
):
    u = await session.get(AppUser, user_id)
    if not u:
        raise HTTPException(status_code=404, detail="User not found")

    changed = False

    # email
    if payload.email is not None:
        new_email = str(payload.email).lower()
        if new_email != u.email:
            exists = await session.scalar(select(AppUser).where(AppUser.email == new_email))
            if exists:
                raise HTTPException(status_code=409, detail="Email already exists")
            u.email = new_email
            changed = True

    # password reset
    if payload.password:
        u.pass_hash = hash_password(payload.password)
        changed = True

    # role/department (enforce mapping)
    new_role = payload.role_id if payload.role_id is not None else u.role_id
    new_dept = payload.department_id if payload.department_id is not None else u.department_id
    if (payload.role_id is not None) or (payload.department_id is not None):
        if not await session.get(Role, new_role):
            raise HTTPException(status_code=400, detail="Invalid role_id")
        if not await session.get(Department, new_dept):
            raise HTTPException(status_code=400, detail="Invalid department_id")
        if not await _role_allowed_for_department(session, department_id=new_dept, role_id=new_role):
            raise HTTPException(status_code=409, detail="Role not allowed for department")
        u.role_id = new_role
        u.department_id = new_dept
        changed = True

    if not changed:
        return _to_out(u)

    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=400, detail="Could not update user")
    return _to_out(u)

# ---------- Admin: delete
@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user_admin(
    user_id: int,
    session: AsyncSession = Depends(get_session),
    __: AppUser = Depends(require_admin),
):
    u = await session.get(AppUser, user_id)
    if not u:
        raise HTTPException(status_code=404, detail="User not found")

    # guard: referenced by versions or logs?
    dv_count = await session.scalar(
        select(func.count()).select_from(DocumentVersion).where(DocumentVersion.uploaded_by == user_id)
    )
    log_count = await session.scalar(
        select(func.count()).select_from(ActionLog).where(ActionLog.user_id == user_id)
    )
    if int(dv_count or 0) > 0 or int(log_count or 0) > 0:
        raise HTTPException(
            status_code=409,
            detail="User has activity (uploads/logs). Reassign or anonymize before deleting."
        )

    await session.delete(u)
    await session.commit()
    return
