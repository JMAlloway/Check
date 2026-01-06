"""Application configuration management."""

from functools import lru_cache
from typing import Any

from pydantic import PostgresDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Application
    APP_NAME: str = "Check Review Console"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    ENVIRONMENT: str = "production"

    # API
    API_V1_PREFIX: str = "/api/v1"

    # Security
    SECRET_KEY: str = "change-this-in-production-use-secure-random-key"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    ALGORITHM: str = "HS256"

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/check_review"

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        if v and not v.startswith("postgresql"):
            raise ValueError("DATABASE_URL must be a PostgreSQL connection string")
        return v

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Session
    SESSION_TIMEOUT_MINUTES: int = 30

    # Image handling
    IMAGE_CACHE_TTL_SECONDS: int = 300
    IMAGE_SIGNED_URL_TTL_SECONDS: int = 60
    MAX_IMAGE_SIZE_MB: int = 10

    # Queue settings
    DEFAULT_SLA_HOURS: int = 4
    HIGH_PRIORITY_THRESHOLD: float = 10000.0
    DUAL_CONTROL_THRESHOLD: float = 5000.0

    # Audit settings
    AUDIT_LOG_RETENTION_YEARS: int = 7

    # Integration settings
    INTEGRATION_TIMEOUT_SECONDS: int = 30
    INTEGRATION_RETRY_ATTEMPTS: int = 3

    # AI settings
    AI_ENABLED: bool = False
    AI_CONFIDENCE_THRESHOLD: float = 0.7

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:5173"]

    # Rate limiting
    RATE_LIMIT_PER_MINUTE: int = 100


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()
