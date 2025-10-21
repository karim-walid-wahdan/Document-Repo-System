# app/core/settings.py
from __future__ import annotations
from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_FILE = Path(__file__).resolve().parents[2] / ".env"

class Settings(BaseSettings):
    # ----- S3 -----
    AWS_ACCESS_KEY_ID: str
    AWS_SECRET_ACCESS_KEY: str
    S3_REGION: str
    S3_ENDPOINT_URL: Optional[str] = None
    S3_BUCKET: str

    # ----- Database -----
    DATABASE_URL: str

    # ----- JWT -----
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRES_MINUTES: int = 60

    # ----- Cache / Redis -----
    REDIS_URL: str

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        extra="ignore",
        case_sensitive=True,
    )

settings = Settings()
