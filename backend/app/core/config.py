"""Application configuration management."""

import json
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

    # Demo Mode - NEVER enable in production
    # Demo mode provides synthetic data for demonstrations without real PII
    DEMO_MODE: bool = False
    DEMO_DATA_COUNT: int = 60  # Number of demo check items to seed

    # API
    API_V1_PREFIX: str = "/api/v1"

    # Security
    SECRET_KEY: str = "change-this-in-production-use-secure-random-key"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15  # Shortened for security (was 30)
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    ALGORITHM: str = "HS256"

    # Cookie Security (for refresh tokens)
    COOKIE_SECURE: bool = True  # Set to False for local dev without HTTPS
    COOKIE_SAMESITE: str = "lax"  # "strict" breaks OAuth flows, "lax" is good balance
    COOKIE_DOMAIN: str | None = None  # None = current domain only
    CSRF_SECRET_KEY: str = "change-this-csrf-secret-in-production"

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
    IMAGE_SIGNED_URL_TTL_SECONDS: int = 3600  # 1 hour - sufficient for review sessions
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

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: Any) -> list[str]:
        """Parse CORS_ORIGINS from JSON string or list."""
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                # If not valid JSON, treat as comma-separated
                return [origin.strip() for origin in v.split(",")]
        return v

    # Rate limiting
    RATE_LIMIT_PER_MINUTE: int = 100

    # Image Connector (Connector A) - JWT token signing
    # RSA private key for signing JWT tokens for image connector requests
    CONNECTOR_JWT_PRIVATE_KEY: str = ""  # Set in production
    CONNECTOR_JWT_ISSUER: str = "check-review-saas"
    CONNECTOR_JWT_DEFAULT_EXPIRY_SECONDS: int = 120

    # Fraud Intelligence Sharing
    # Current pepper for indicator hashing (HMAC secret)
    NETWORK_PEPPER: str = "change-this-network-pepper-in-production"
    NETWORK_PEPPER_VERSION: int = 1  # Increment when rotating pepper
    # Prior pepper (for matching during rotation window) - set to empty string when not rotating
    NETWORK_PEPPER_PRIOR: str = ""
    NETWORK_PEPPER_PRIOR_VERSION: int = 0  # Version of prior pepper (0 = no prior)
    FRAUD_PRIVACY_THRESHOLD: int = 3  # Minimum count before showing aggregate data
    FRAUD_ARTIFACT_RETENTION_MONTHS: int = 24  # Default retention for shared artifacts


def _validate_production_secrets(s: Settings) -> None:
    """
    CRITICAL: Fail hard if production uses default secrets.

    This prevents accidental deployment with insecure defaults.
    Called during settings initialization.
    """
    if s.ENVIRONMENT != "production":
        return

    # Known default/placeholder secrets that MUST be changed
    insecure_defaults = {
        "SECRET_KEY": "change-this-in-production-use-secure-random-key",
        "CSRF_SECRET_KEY": "change-this-csrf-secret-in-production",
        "NETWORK_PEPPER": "change-this-network-pepper-in-production",
    }

    violations = []
    for key, default_value in insecure_defaults.items():
        actual_value = getattr(s, key, None)
        if actual_value == default_value:
            violations.append(key)

    if violations:
        raise RuntimeError(
            f"FATAL: Production deployment blocked - insecure default secrets detected!\n"
            f"The following secrets MUST be changed before deploying to production:\n"
            f"  {', '.join(violations)}\n\n"
            f"Generate secure values with: python -c \"import secrets; print(secrets.token_urlsafe(32))\"\n"
            f"Set these as environment variables or in your production .env file."
        )


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance with validation."""
    s = Settings()
    _validate_production_secrets(s)
    return s


settings = get_settings()
