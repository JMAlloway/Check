"""Application configuration management."""

import json
from functools import lru_cache
from typing import Any

from pydantic import PostgresDsn, field_validator, model_validator
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
    ENVIRONMENT: str = "development"  # Must explicitly set to "production" in prod deployments

    # Demo Mode - NEVER enable in production
    # Demo mode provides synthetic data for demonstrations without real PII
    DEMO_MODE: bool = False

    @field_validator("DEMO_MODE", mode="before")
    @classmethod
    def parse_demo_mode(cls, v: Any) -> bool:
        """Parse DEMO_MODE, stripping whitespace to handle Windows .env files."""
        if isinstance(v, str):
            v = v.strip().lower()
            if v in ("true", "1", "yes", "on"):
                return True
            if v in ("false", "0", "no", "off", ""):
                return False
        return v

    DEMO_DATA_COUNT: int = 60  # Number of demo check items to seed

    # API
    API_V1_PREFIX: str = "/api/v1"

    # Security
    SECRET_KEY: str = "change-this-in-production-use-secure-random-key"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15  # Shortened for security (was 30)
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    ALGORITHM: str = "HS256"

    # Cookie Security (for refresh tokens)
    COOKIE_SECURE: bool | None = (
        None  # Auto-detected from ENVIRONMENT (True in prod, False otherwise)
    )
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

    # Redis (optional - leave empty to disable Redis health checks)
    REDIS_URL: str = ""

    # Session
    SESSION_TIMEOUT_MINUTES: int = 30

    # Image handling
    IMAGE_CACHE_TTL_SECONDS: int = 300
    # Short TTL for signed URLs - treated as bearer tokens, not user-bound
    # Frontend must refresh URLs before expiry for long review sessions
    IMAGE_SIGNED_URL_TTL_SECONDS: int = 90  # 90 seconds - security/usability balance
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

    @model_validator(mode="after")
    def set_computed_defaults(self) -> "Settings":
        """Set computed defaults based on other settings."""
        # Auto-detect COOKIE_SECURE from environment if not explicitly set
        if self.COOKIE_SECURE is None:
            # Secure cookies only in production (requires HTTPS)
            object.__setattr__(self, "COOKIE_SECURE", self.ENVIRONMENT == "production")

        # Auto-disable docs and metrics in production unless explicitly enabled via env var
        # Check if env vars were explicitly set (not just using defaults)
        import os

        if self.ENVIRONMENT == "production":
            # Only disable if not explicitly set to true in env
            if os.getenv("EXPOSE_DOCS", "").lower() not in ("true", "1", "yes"):
                object.__setattr__(self, "EXPOSE_DOCS", False)
            if os.getenv("EXPOSE_METRICS", "").lower() not in ("true", "1", "yes"):
                object.__setattr__(self, "EXPOSE_METRICS", False)

        return self

    # Rate limiting
    RATE_LIMIT_PER_MINUTE: int = 100

    # Endpoint Exposure Control (Security)
    # These should be False in production/pilot unless behind VPN/internal ingress
    EXPOSE_DOCS: bool = True  # OpenAPI docs at /api/v1/docs - auto-disabled in production
    EXPOSE_METRICS: bool = True  # Prometheus metrics at /metrics - auto-disabled in production
    # IP allowlist for metrics endpoint (comma-separated, empty = allow all when exposed)
    # Example: "10.0.0.0/8,172.16.0.0/12,192.168.0.0/16,127.0.0.1"
    METRICS_ALLOWED_IPS: str = ""

    @field_validator("METRICS_ALLOWED_IPS", mode="before")
    @classmethod
    def parse_metrics_allowed_ips(cls, v: Any) -> str:
        """Parse METRICS_ALLOWED_IPS, stripping whitespace."""
        if isinstance(v, str):
            return v.strip()
        return v or ""

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
    CRITICAL: Fail hard if production uses weak or placeholder secrets.

    This prevents accidental deployment with insecure defaults.
    Called during settings initialization.

    Secrets validated:
    - SECRET_KEY: JWT signing key (min 32 chars)
    - CSRF_SECRET_KEY: CSRF token signing (min 32 chars)
    - NETWORK_PEPPER: Fraud indicator hashing (min 32 chars)
    - CONNECTOR_JWT_PRIVATE_KEY: Connector A RS256 signing key (min 100 chars for RSA)

    Validates:
    - Minimum length for adequate entropy
    - No known default values
    - No common placeholder patterns
    """
    if s.ENVIRONMENT != "production":
        return

    # Secrets to validate with their minimum required length
    secrets_to_check = {
        "SECRET_KEY": 32,
        "CSRF_SECRET_KEY": 32,
        "NETWORK_PEPPER": 32,
        "CONNECTOR_JWT_PRIVATE_KEY": 100,  # RSA private key minimum length
    }

    # Known default/placeholder secrets that MUST be changed
    insecure_defaults = {
        "SECRET_KEY": "change-this-in-production-use-secure-random-key",
        "CSRF_SECRET_KEY": "change-this-csrf-secret-in-production",
        "NETWORK_PEPPER": "change-this-network-pepper-in-production",
        "CONNECTOR_JWT_PRIVATE_KEY": "",  # Empty is insecure
    }

    # Common placeholder patterns that indicate non-production secrets
    placeholder_patterns = [
        "change",
        "replace",
        "your-",
        "example",
        "placeholder",
        "secret",
        "password",
        "default",
        "insecure",
        "changeme",
        "todo",
        "fixme",
        "xxx",
        "test",
        "demo",
        "sample",
    ]

    violations = []
    length_violations = []
    pattern_violations = []

    for key, min_length in secrets_to_check.items():
        actual_value = getattr(s, key, None)
        if not actual_value:
            violations.append(f"{key}: not set")
            continue

        # Check for exact default matches
        if actual_value == insecure_defaults.get(key):
            violations.append(f"{key}: using hardcoded default")
            continue

        # Check minimum length for entropy
        if len(actual_value) < min_length:
            length_violations.append(f"{key}: {len(actual_value)} chars (minimum {min_length})")
            continue

        # Check for placeholder patterns (case-insensitive)
        value_lower = actual_value.lower()
        for pattern in placeholder_patterns:
            if pattern in value_lower:
                pattern_violations.append(f"{key}: contains placeholder pattern '{pattern}'")
                break

    all_issues = violations + length_violations + pattern_violations
    if all_issues:
        raise RuntimeError(
            f"FATAL: Production deployment blocked - insecure secrets detected!\n\n"
            f"Issues found:\n"
            f"  {chr(10).join('- ' + v for v in all_issues)}\n\n"
            f"Requirements for production secrets:\n"
            f"  - Minimum 32 characters\n"
            f"  - No placeholder words (change, secret, password, etc.)\n"
            f"  - Randomly generated\n\n"
            f"Generate secure values with:\n"
            f'  python -c "import secrets; print(secrets.token_urlsafe(32))"\n\n'
            f"Set these as environment variables or in your production .env file."
        )


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance with validation."""
    s = Settings()
    _validate_production_secrets(s)
    return s


settings = get_settings()
