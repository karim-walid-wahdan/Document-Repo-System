#app/routers/auth.py
from fastapi import APIRouter, Depends, HTTPException, status, Response
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import redis.asyncio as redis

from app.db.session import get_session
from app.db.models import AppUser
from app.core.cache import get_redis
from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
)

router = APIRouter(prefix="/auth", tags=["auth"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

# ---------- Schemas
class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=512)
    role_id: int = 2
    department_id: int = 1

class LoginIn(BaseModel):
    email: EmailStr
    password: str

class TokenPairOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class RefreshIn(BaseModel):
    refresh_token: str

# ---------- Helpers
async def _issue_tokens(r: redis.Redis, subject: str) -> TokenPairOut:
    # access
    at, ajti, attl = create_access_token(subject=subject)
    await r.setex(f"auth:jti:{ajti}", attl, subject)
    # refresh (track per-user refresh JTIs for global logout)
    rt, rjti, rttl = create_refresh_token(subject=subject)
    await r.setex(f"auth:rjti:{rjti}", rttl, subject)
    await r.sadd(f"auth:user:{subject}:rset", rjti)
    await r.expire(f"auth:user:{subject}:rset", rttl)  # align set TTL with latest refresh
    return TokenPairOut(access_token=at, refresh_token=rt)

# ---------- Endpoints
@router.post("/register", response_model=TokenPairOut, status_code=201)
async def register(
    payload: RegisterIn,
    session: AsyncSession = Depends(get_session),
    r: redis.Redis = Depends(get_redis),
):
    email = str(payload.email).lower()
    existing = await session.scalar(select(AppUser).where(AppUser.email == email))
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    user = AppUser(
        email=email,
        pass_hash=hash_password(payload.password),
        role_id=payload.role_id,
        department_id=payload.department_id,
    )
    session.add(user)
    try:
        await session.commit()
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=400, detail=f"Registration failed: {e}")

    return await _issue_tokens(r, subject=user.email)

@router.post("/login", response_model=TokenPairOut)
async def login(
    payload: LoginIn,
    session: AsyncSession = Depends(get_session),
    r: redis.Redis = Depends(get_redis),
):
    email = str(payload.email).lower()
    user = await session.scalar(select(AppUser).where(AppUser.email == email))
    if not user or not verify_password(payload.password, user.pass_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    return await _issue_tokens(r, subject=user.email)

@router.post("/refresh", response_model=TokenPairOut)
async def refresh(
    payload: RefreshIn,
    session: AsyncSession = Depends(get_session),
    r: redis.Redis = Depends(get_redis),
):
    # validate refresh token
    try:
        data = decode_token(payload.refresh_token)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    if data.get("typ") != "refresh":
        raise HTTPException(status_code=401, detail="Wrong token type")

    rjti = data.get("jti")
    sub = data.get("sub")
    if not rjti or not sub:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    # ensure refresh session exists (not used/expired)
    exists = await r.exists(f"auth:rjti:{rjti}")
    if not exists:
        raise HTTPException(status_code=401, detail="Refresh session expired")

    # check user still exists
    user = await session.scalar(select(AppUser).where(AppUser.email == sub))
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    # rotate: invalidate old refresh
    pipe = r.pipeline()
    pipe.delete(f"auth:rjti:{rjti}")
    pipe.srem(f"auth:user:{sub}:rset", rjti)
    await pipe.execute()

    # issue new pair
    return await _issue_tokens(r, subject=sub)

@router.post("/logout", status_code=204)
async def logout(
    token: str = Depends(oauth2_scheme),
    r: redis.Redis = Depends(get_redis),
):
    # must be a valid access token
    try:
        payload = decode_token(token)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    jti = payload.get("jti")
    sub = payload.get("sub")
    if not jti or not sub:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")

    # delete access session; if already missing, treat as unauthorized
    deleted = await r.delete(f"auth:jti:{jti}")
    if deleted == 0:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session already logged out or expired")

    # wipe ALL refresh tokens for this user so a fresh login is required
    set_key = f"auth:user:{sub}:rset"
    rjtis = await r.smembers(set_key)
    if rjtis:
        pipe = r.pipeline()
        for rid in rjtis:
            pipe.delete(f"auth:rjti:{rid}")
        pipe.delete(set_key)
        await pipe.execute()

    return Response(status_code=204)
