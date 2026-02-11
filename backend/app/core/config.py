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

    # Image signing - dedicated key for image URL tokens (separate from auth JWTs)
    # This allows independent rotation and limits blast radius of key compromise
    IMAGE_SIGNING_KEY: str = "change-this-image-signing-key-in-production"
    IMAGE_SIGNING_ALGORITHM: str = "HS256"

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

    # Risk assessment thresholds (amount-based)
    # These thresholds determine risk score contribution based on check amount
    RISK_THRESHOLD_LOW: float = 5000.0  # +10 to risk score
    RISK_THRESHOLD_MEDIUM: float = 10000.0  # +20 to risk score
    RISK_THRESHOLD_HIGH: float = 25000.0  # +30 to risk score
    RISK_THRESHOLD_CRITICAL: float = 50000.0  # +40 to risk score
    RISK_THRESHOLD_EXTREME: float = 100000.0  # +50 to priority score

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
            # Secure cookies in production/pilot/staging/uat (requires HTTPS)
            secure_cookie_envs = {"production", "pilot", "staging", "uat"}
            object.__setattr__(
                self, "COOKIE_SECURE", self.ENVIRONMENT.lower() in secure_cookie_envs
            )

        # Auto-disable docs and metrics in secure environments unless explicitly enabled
        # Check if env vars were explicitly set (not just using defaults)
        import os

        secure_environments = {"production", "pilot", "staging", "uat"}
        if self.ENVIRONMENT.lower() in secure_environments:
            # Only disable if not explicitly set to true in env
            if os.getenv("EXPOSE_DOCS", "").lower() not in ("true", "1", "yes"):
                object.__setattr__(self, "EXPOSE_DOCS", False)
            if os.getenv("EXPOSE_METRICS", "").lower() not in ("true", "1", "yes"):
                object.__setattr__(self, "EXPOSE_METRICS", False)

            # Validate CORS origins in secure environments
            self._validate_cors_origins_secure()

        return self

    def _validate_cors_origins_secure(self) -> None:
        """
        Validate CORS origins for secure environments.

        In production/pilot/staging/uat:
        - No wildcard "*" origins allowed
        - All origins must use HTTPS
        """
        issues = []

        for origin in self.CORS_ORIGINS:
            # Check for wildcard
            if origin == "*":
                issues.append("Wildcard '*' origin not allowed in secure environments")
                continue

            # Check for HTTPS (allow localhost for local testing even in pilot)
            if origin.startswith("http://"):
                # Allow localhost/127.0.0.1 for local development proxies
                if "localhost" in origin or "127.0.0.1" in origin:
                    continue
                issues.append(f"Non-HTTPS origin '{origin}' not allowed in secure environments")

        if issues:
            raise RuntimeError(
                f"CORS configuration invalid for {self.ENVIRONMENT} environment:\n"
                f"  {chr(10).join('- ' + issue for issue in issues)}\n\n"
                f"Current CORS_ORIGINS: {self.CORS_ORIGINS}\n\n"
                f"Fix: Update CORS_ORIGINS to use only HTTPS URLs, e.g.:\n"
                f"  CORS_ORIGINS='[\"https://app.yourbank.com\"]'"
            )

    # Rate limiting
    RATE_LIMIT_PER_MINUTE: int = 100

    # Proxy/Load Balancer Configuration (for correct client IP detection)
    # CRITICAL: Set this to the IP(s) of your reverse proxy/load balancer
    # Without this, audit trails and rate limiting will use proxy IPs, not client IPs
    # Format: comma-separated IPs or CIDR ranges, e.g., "10.0.0.0/8,172.16.0.0/12,192.168.0.0/16"
    # Docker default: "172.16.0.0/12" (Docker network range)
    # Kubernetes: Set to your ingress controller pod CIDR
    TRUSTED_PROXY_IPS: str = "127.0.0.1,::1"  # Default: only localhost trusted

    @field_validator("TRUSTED_PROXY_IPS", mode="before")
    @classmethod
    def parse_trusted_proxy_ips(cls, v: Any) -> str:
        """Parse TRUSTED_PROXY_IPS, stripping whitespace."""
        if isinstance(v, str):
            return v.strip()
        return v or "127.0.0.1,::1"

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

    # HSTS (HTTP Strict Transport Security)
    # Auto-enabled in production/pilot/staging/uat where HTTPS is enforced
    HSTS_MAX_AGE_SECONDS: int = 31536000  # 1 year (recommended minimum for production)
    HSTS_PRELOAD: bool = False  # Set True to enable HSTS preload (requires commitment)

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
    CRITICAL: Fail hard if production/pilot uses weak or placeholder secrets.

    This prevents accidental deployment with insecure defaults.
    Called during settings initialization.

    Applies to: production, pilot (any environment where real data may be processed)

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
    # Environments that require secure secrets (any non-development environment)
    secure_environments = {"production", "pilot", "staging", "uat"}
    if s.ENVIRONMENT.lower() not in secure_environments:
        return

    # Secrets to validate with their minimum required length
    secrets_to_check = {
        "SECRET_KEY": 32,
        "CSRF_SECRET_KEY": 32,
        "NETWORK_PEPPER": 32,
        "CONNECTOR_JWT_PRIVATE_KEY": 100,  # RSA private key minimum length
        "IMAGE_SIGNING_KEY": 32,  # Dedicated key for image URL signing
    }

    # Known default/placeholder secrets that MUST be changed
    insecure_defaults = {
        "SECRET_KEY": "change-this-in-production-use-secure-random-key",
        "CSRF_SECRET_KEY": "change-this-csrf-secret-in-production",
        "NETWORK_PEPPER": "change-this-network-pepper-in-production",
        "CONNECTOR_JWT_PRIVATE_KEY": "",  # Empty is insecure
        "IMAGE_SIGNING_KEY": "change-this-image-signing-key-in-production",
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
            f"FATAL: {s.ENVIRONMENT.upper()} deployment blocked - insecure secrets detected!\n\n"
            f"Environment '{s.ENVIRONMENT}' requires secure secrets (not defaults).\n\n"
            f"Issues found:\n"
            f"  {chr(10).join('- ' + v for v in all_issues)}\n\n"
            f"Requirements for secrets in {s.ENVIRONMENT}:\n"
            f"  - Minimum 32 characters (100+ for RSA keys)\n"
            f"  - No placeholder words (change, secret, password, etc.)\n"
            f"  - Randomly generated with sufficient entropy\n\n"
            f"Generate secure values with:\n"
            f'  python -c "import secrets; print(secrets.token_urlsafe(32))"\n\n'
            f"Set these as environment variables or in your .env.{s.ENVIRONMENT} file.\n"
            f"See docker/.env.pilot.example for reference."
        )


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance with validation."""
    s = Settings()
    _validate_production_secrets(s)
    return s


settings = get_settings()
