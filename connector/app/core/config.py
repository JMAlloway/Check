"""
Bank-Side Connector Configuration

Supports two modes:
- DEMO: Uses local filesystem to simulate UNC shares
- BANK: Uses real UNC paths with service account access (NOT YET IMPLEMENTED)
"""
import logging
import os
from enum import Enum
from pathlib import Path
from typing import List, Optional
from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings

logger = logging.getLogger("connector.config")


class ConnectorMode(str, Enum):
    DEMO = "DEMO"
    BANK = "BANK"


class Settings(BaseSettings):
    """Connector service settings."""

    # Service identification
    MODE: ConnectorMode = ConnectorMode.DEMO
    CONNECTOR_ID: str = "connector-demo-001"
    CONNECTOR_VERSION: str = "1.0.0"

    # Network settings
    HOST: str = "0.0.0.0"
    PORT: int = 8443
    TLS_CERT_PATH: Optional[str] = None
    TLS_KEY_PATH: Optional[str] = None

    # Demo mode settings
    DEMO_REPO_ROOT: str = "./demo_repo"
    ITEM_INDEX_PATH: str = "./demo_repo/item_index.json"

    # Allowed UNC share roots (production)
    # In demo mode, these are translated to local paths under DEMO_REPO_ROOT
    ALLOWED_SHARE_ROOTS: List[str] = [
        "\\\\tn-director-pro\\Checks\\Transit\\",
        "\\\\tn-director-pro\\Checks\\OnUs\\"
    ]

    # JWT Authentication (RS256)
    # Public key used to verify tokens from SaaS
    JWT_PUBLIC_KEY: str = ""
    JWT_PUBLIC_KEY_PATH: Optional[str] = None
    JWT_ALGORITHM: str = "RS256"
    JWT_ISSUER: str = "check-review-saas"

    # Replay protection
    JWT_REPLAY_CACHE_TTL_SECONDS: int = 300  # 5 minutes

    # Image handling
    MAX_IMAGE_MB: int = 50
    CACHE_TTL_SECONDS: int = 60
    CACHE_MAX_ITEMS: int = 100

    # Rate limiting
    RATE_LIMIT_REQUESTS_PER_MINUTE: int = 100
    RATE_LIMIT_BURST: int = 20

    # Audit logging
    LOG_DIR: str = "./logs"
    LOG_LEVEL: str = "INFO"
    AUDIT_LOG_FILE: str = "connector_audit.jsonl"

    # Required roles for image access
    IMAGE_ACCESS_ROLES: List[str] = ["image_viewer", "check_reviewer", "admin"]

    model_config = {
        "env_prefix": "CONNECTOR_",
        "env_file": ".env",
        "extra": "ignore"
    }

    @field_validator("JWT_PUBLIC_KEY", mode="before")
    @classmethod
    def load_jwt_public_key(cls, v: str, info) -> str:
        """Load JWT public key from file if path is provided."""
        if v:
            return v
        # Try to load from file path
        key_path = info.data.get("JWT_PUBLIC_KEY_PATH") if info.data else None
        if key_path and Path(key_path).exists():
            return Path(key_path).read_text()
        return v

    @field_validator("ALLOWED_SHARE_ROOTS", mode="before")
    @classmethod
    def parse_share_roots(cls, v):
        """Parse share roots from comma-separated string or list."""
        if isinstance(v, str):
            return [r.strip() for r in v.split(",") if r.strip()]
        return v

    @model_validator(mode="after")
    def validate_bank_mode_not_implemented(self) -> "Settings":
        """
        BANK mode is not yet implemented - fall back to DEMO with warning.

        Bank adapters (BankItemResolver, BankStorageProvider) are stubs that
        raise NotImplementedError. Until real implementations exist, we force
        DEMO mode to prevent runtime crashes.
        """
        if self.MODE == ConnectorMode.BANK:
            # Log prominent warning - this will appear at startup
            warning_msg = """
================================================================================
WARNING: CONNECTOR_MODE=BANK requested but BANK mode is NOT YET IMPLEMENTED!
================================================================================

Bank adapters are currently stubs that would crash on first use.
Falling back to DEMO mode to allow the connector to function.

To resolve this:
  1. For pilot/demo deployments: Set CONNECTOR_MODE=DEMO explicitly
  2. For production: Implement real adapters in connector/app/adapters/bank/

The connector will now run in DEMO mode using local demo fixtures.
================================================================================
"""
            # Use print to ensure visibility even if logging isn't configured yet
            print(warning_msg)
            logger.warning(
                "BANK mode not implemented - forcing DEMO mode. "
                "Set CONNECTOR_MODE=DEMO to suppress this warning."
            )

            # Force DEMO mode
            object.__setattr__(self, "MODE", ConnectorMode.DEMO)
            object.__setattr__(self, "_bank_mode_fallback", True)

        return self

    def get_demo_path(self, unc_path: str) -> Path:
        """
        Translate UNC path to demo filesystem path.

        Example:
            \\\\tn-director-pro\\Checks\\Transit\\V406\\580\\12374628.IMG
            -> ./demo_repo/Checks/Transit/V406/580/12374628.IMG
        """
        # Normalize path separators
        normalized = unc_path.replace("\\", "/")

        # Find which root matches
        for root in self.ALLOWED_SHARE_ROOTS:
            normalized_root = root.replace("\\", "/").rstrip("/")
            # Extract server and share name, then get the relative portion
            # \\server\share\path... -> path...
            parts = normalized_root.split("/")
            if len(parts) >= 4:
                # Skip //server/share prefix, keep rest
                relative_root = "/".join(parts[4:]) if len(parts) > 4 else ""
            else:
                relative_root = ""

            # Check if our path starts with this root
            if normalized.startswith(normalized_root):
                # Get the path after the root
                relative_path = normalized[len(normalized_root):].lstrip("/")
                # Construct demo path
                if relative_root:
                    demo_path = Path(self.DEMO_REPO_ROOT) / relative_root / relative_path
                else:
                    demo_path = Path(self.DEMO_REPO_ROOT) / relative_path
                return demo_path

        # Fallback: try to extract Checks/... portion
        for marker in ["Checks/Transit/", "Checks/OnUs/"]:
            if marker in normalized:
                idx = normalized.index("Checks/")
                relative_path = normalized[idx:]
                return Path(self.DEMO_REPO_ROOT) / relative_path

        raise ValueError(f"Cannot translate UNC path: {unc_path}")


# Global settings instance
settings = Settings()


def get_settings() -> Settings:
    """Get current settings instance."""
    return settings
