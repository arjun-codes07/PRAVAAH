"""Application configuration module."""

import os
from dotenv import load_dotenv

load_dotenv()


def _normalize_db_url(url: str) -> str:
    """Ensure the DATABASE_URL uses the psycopg3 (psycopg) driver.

    Render and other PaaS providers supply ``postgresql://...`` URLs.
    SQLAlchemy with psycopg3 requires ``postgresql+psycopg://...``.
    """
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+psycopg://", 1)
    elif url.startswith("postgresql://") and "+psycopg" not in url:
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


class Settings:
    DATABASE_URL: str = _normalize_db_url(
        os.environ.get(
            "DATABASE_URL",
            "postgresql+psycopg://pravaah_app:changeme@localhost:5432/pravaah",
        )
    )
    JWT_SECRET: str = os.environ.get("JWT_SECRET", "pravaah_default_secret_key_change_in_prod")
    JWT_ALGORITHM: str = os.environ.get("JWT_ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.environ.get("ACCESS_TOKEN_EXPIRE_MINUTES", "480"))
    
    _cors_raw = os.environ.get("CORS_ORIGINS", "http://localhost:3000,http://localhost:5173")
    CORS_ORIGINS: list[str] = [origin.strip() for origin in _cors_raw.split(",") if origin.strip()]
    
    STALE_DEFAULT_MINUTES: int = int(os.environ.get("STALE_DEFAULT_MINUTES", "60"))

settings = Settings()

