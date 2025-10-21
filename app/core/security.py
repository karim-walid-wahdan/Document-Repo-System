# app/core/security.py
from datetime import datetime, timedelta, timezone
import hashlib, hmac, logging, uuid
from jose import jwt, JWTError
from passlib.context import CryptContext
from app.core.settings import settings

logger = logging.getLogger("app.security")

pwd_context = CryptContext(schemes=["bcrypt_sha256", "bcrypt"], deprecated="auto")

def _pw_fingerprint(plain: str) -> str:
    key = settings.JWT_SECRET.encode("utf-8")
    return hmac.new(key, plain.encode("utf-8"), hashlib.sha256).hexdigest()[:12]

def hash_password(plain: str) -> str:
    hashed = pwd_context.hash(plain)
    logger.info("Hashed password fp=%s scheme=%s", _pw_fingerprint(plain), pwd_context.identify(hashed))
    return hashed

def verify_password(plain: str, hashed: str) -> bool:
    try:
        return pwd_context.verify(plain, hashed)
    except Exception:
        logger.exception("Verify failed for fp=%s", _pw_fingerprint(plain))
        return False

def create_access_token(subject: str, *, minutes: int | None = None) -> tuple[str, str, int]:
    exp_minutes = minutes or settings.JWT_EXPIRES_MINUTES
    exp = datetime.now(timezone.utc) + timedelta(minutes=exp_minutes)
    jti = uuid.uuid4().hex
    payload = {"sub": subject, "exp": int(exp.timestamp()), "jti": jti}
    token = jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    return token, jti, exp_minutes * 60

def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    except JWTError as e:
        raise ValueError(f"Invalid token: {e}")  # let dependency map to 401
