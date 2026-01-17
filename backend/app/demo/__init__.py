"""
Demo Mode Module for Check Review Console.

This module provides synthetic data and mock services for demonstrating
the application without requiring real integrations or PII data.

IMPORTANT: Demo mode must NEVER be enabled in production environments.
"""

from app.core.config import settings


def is_demo_mode() -> bool:
    """Check if demo mode is enabled."""
    return settings.DEMO_MODE


def require_demo_mode():
    """Raise an error if demo mode is not enabled."""
    if not is_demo_mode():
        raise RuntimeError("This operation requires demo mode to be enabled")


def require_non_production():
    """Raise an error if running in production."""
    if settings.ENVIRONMENT == "production":
        raise RuntimeError("This operation is not allowed in production")
