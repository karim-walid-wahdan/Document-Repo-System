# app/core/deps.py
from typing import Annotated
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.security import decode_token
from app.core.cache import get_redis
from app.db.session import get_session
from app.db.models import AppUser,Role
import redis.asyncio as redis


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    session: AsyncSession = Depends(get_session),
    r: redis.Redis = Depends(get_redis),
) -> AppUser:
    try:
        payload = decode_token(token)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    jti = payload.get("jti")
    sub = payload.get("sub")
    if not jti or not sub:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    # enforce Redis session (allowlist)
    key = f"auth:jti:{jti}"
    exists = await r.exists(key)
    if not exists:
        raise HTTPException(status_code=401, detail="Session expired")

    user = await session.scalar(select(AppUser).where(AppUser.email == sub))
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user
async def require_admin(
    user: AppUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> AppUser:
    role = await session.scalar(select(Role).where(Role.role_id == user.role_id))
    if not role or role.name.lower() != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")
    return user