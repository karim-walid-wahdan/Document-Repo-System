# app/core/security.py
from datetime import datetime, timedelta
import hashlib, hmac, logging
from jose import jwt
from passlib.context import CryptContext
from app.core.settings import settings

logger = logging.getLogger("app.security")

pwd_context = CryptContext(
    schemes=["bcrypt_sha256", "bcrypt"],
    deprecated="auto",
)

def _pw_fingerprint(plain: str) -> str:
    key = settings.JWT_SECRET.encode("utf-8")
    return hmac.new(key, plain.encode("utf-8"), hashlib.sha256).hexdigest()[:12]

def hash_password(plain: str) -> str:
    b = plain.encode("utf-8")
    try:
        hashed = pwd_context.hash(plain)
        logger.info(
            "Hashed password fp=%s len=%dB scheme=%s",
            _pw_fingerprint(plain),
            len(b),
            pwd_context.identify(hashed),
        )
        return hashed
    except Exception:
        logger.exception("Hashing failed for fp=%s len=%dB", _pw_fingerprint(plain), len(b))
        raise

def verify_password(plain: str, hashed: str) -> bool:
    try:
        ok = pwd_context.verify(plain, hashed)
        logger.debug("Verify fp=%s result=%s", _pw_fingerprint(plain), ok)
        return ok
    except Exception:
        logger.exception("Verify failed for fp=%s", _pw_fingerprint(plain))
        return False

def create_access_token(subject: str, expires_minutes: int | None = None) -> str:
    exp = datetime.utcnow() + timedelta(minutes=expires_minutes or settings.JWT_EXPIRES_MINUTES)
    return jwt.encode({"sub": subject, "exp": exp}, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
