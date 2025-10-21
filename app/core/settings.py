# app/core/settings.py
from __future__ import annotations

from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

# project_root/
#   .env   <-- here
#   app/
#     core/settings.py
ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    # ----- S3 -----
    AWS_ACCESS_KEY_ID: str
    AWS_SECRET_ACCESS_KEY: str
    S3_REGION: str
    S3_ENDPOINT_URL: Optional[str] = None  # allow AWS default if not set

    # ----- Database -----
    # e.g. postgresql+asyncpg://user:pass@host:5432/dbname
    DATABASE_URL: str

    # ----- JWT -----
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRES_MINUTES: int = 60

    # ----- Cache / Redis -----
    # e.g. redis://localhost:6379/0
    REDIS_URL: str

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        extra="ignore",
        case_sensitive=True,
    )


settings = Settings()
