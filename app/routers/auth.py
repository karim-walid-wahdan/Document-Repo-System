# app/routers/auth.py
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.session import get_session
from app.db.models import AppUser
from app.core.security import hash_password, verify_password, create_access_token
from app.core.cache import get_redis
import redis.asyncio as redis

class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=512)
    role_id: int = 2
    department_id: int = 1

class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/register", response_model=TokenOut, status_code=201)
async def register(payload: RegisterIn, session: AsyncSession = Depends(get_session), r: redis.Redis = Depends(get_redis)):
    existing = await session.scalar(select(AppUser).where(AppUser.email == str(payload.email)))
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    user = AppUser(
        email=str(payload.email),
        pass_hash=hash_password(payload.password),
        role_id=payload.role_id,
        department_id=payload.department_id,
    )
    session.add(user)
    await session.commit()
    token, jti, ttl = create_access_token(subject=user.email)
    await r.setex(f"auth:jti:{jti}", ttl, user.email)
    return TokenOut(access_token=token)
class LoginIn(BaseModel):
    email: EmailStr
    password: str
@router.post("/login", response_model=TokenOut)
async def login(payload: LoginIn, session: AsyncSession = Depends(get_session), r: redis.Redis = Depends(get_redis)):
    user = await session.scalar(select(AppUser).where(AppUser.email == str(payload.email)))
    if not user or not verify_password(payload.password, user.pass_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    token, jti, ttl = create_access_token(subject=user.email)
    await r.setex(f"auth:jti:{jti}", ttl, user.email)
    return TokenOut(access_token=token)
@router.post("/logout", status_code=204)
async def logout(token_out: TokenOut, r: redis.Redis = Depends(get_redis)):
    # client sends the current bearer token; remove its jti
    from jose import jwt
    from app.core.settings import settings
    try:
        payload = jwt.decode(token_out.access_token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        jti = payload.get("jti")
        if jti:
            await r.delete(f"auth:jti:{jti}")
    except Exception:
        pass