"""
Demo Mode Module for Check Review Console.

This module provides synthetic data and mock services for demonstrating
the application without requiring real integrations or PII data.

IMPORTANT: Demo mode must NEVER be enabled in production environments.
"""

from app.core.config import settings

# Environments where real data may be processed. Demo data / synthetic seeding
# must never run in any of these - not just exact "production". Kept in sync
# with config._validate_production_secrets / CORS hardening.
SECURE_ENVIRONMENTS = {"production", "pilot", "staging", "uat"}


def is_demo_mode() -> bool:
    """Check if demo mode is enabled."""
    return settings.DEMO_MODE


def require_demo_mode():
    """Raise an error if demo mode is not enabled."""
    if not is_demo_mode():
        raise RuntimeError("This operation requires demo mode to be enabled")


def require_non_production():
    """Raise an error if running in any environment that may hold real data."""
    if settings.ENVIRONMENT.lower() in SECURE_ENVIRONMENTS:
        raise RuntimeError(
            f"This operation is not allowed in the '{settings.ENVIRONMENT}' environment"
        )
