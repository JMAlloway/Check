"""Rate limiting configuration for pilot-grade security.

Provides multiple rate limiters for different endpoint categories:
- IP-based: For unauthenticated endpoints (login, health)
- User-based: For authenticated API calls
- Tenant-based: For per-tenant quotas to prevent one tenant from DOSing others

Rate Limit Categories:
- AUTH: Login/logout (strict - prevent brute force)
- STANDARD: Normal API calls (moderate)
- SEARCH: List/search endpoints (moderate - can be expensive)
- IMAGE: Image access endpoints (strict - bandwidth intensive)
- EXPORT: Export/report generation (strict - CPU/memory intensive)
- BATCH: Batch operations (strict - can be very expensive)
"""

from typing import Optional

from app.core.config import settings
from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address


def get_user_identifier(request: Request) -> str:
    """
    Get rate limit key based on authenticated user.

    Falls back to IP address if user not authenticated.
    Uses format: user:{user_id} or ip:{ip_address}
    """
    # Try to get user from request state (set by auth middleware)
    user = getattr(request.state, "user", None)
    if user and hasattr(user, "id"):
        return f"user:{user.id}"

    # Fall back to IP address
    return f"ip:{get_remote_address(request)}"


def get_tenant_identifier(request: Request) -> str:
    """
    Get rate limit key based on tenant.

    Falls back to IP address if tenant not available.
    Uses format: tenant:{tenant_id} or ip:{ip_address}
    """
    # Try to get user from request state
    user = getattr(request.state, "user", None)
    if user and hasattr(user, "tenant_id"):
        return f"tenant:{user.tenant_id}"

    # Fall back to IP address
    return f"ip:{get_remote_address(request)}"


def get_user_and_tenant_identifier(request: Request) -> str:
    """
    Get composite rate limit key: user within tenant.

    This allows both per-user AND per-tenant limits.
    Uses format: tenant:{tenant_id}:user:{user_id} or ip:{ip_address}
    """
    user = getattr(request.state, "user", None)
    if user and hasattr(user, "id") and hasattr(user, "tenant_id"):
        return f"tenant:{user.tenant_id}:user:{user.id}"

    return f"ip:{get_remote_address(request)}"


# =============================================================================
# Rate Limiters
# =============================================================================

# IP-based limiter (for unauthenticated endpoints)
limiter = Limiter(key_func=get_remote_address)

# User-based limiter (for authenticated endpoints)
user_limiter = Limiter(key_func=get_user_identifier)

# Tenant-based limiter (for per-tenant quotas)
tenant_limiter = Limiter(key_func=get_tenant_identifier)


# =============================================================================
# Rate Limit Configurations (configurable via settings)
# =============================================================================


class RateLimits:
    """
    Centralized rate limit configurations.

    Format: "X/period" where period is: second, minute, hour, day
    Multiple limits can be combined: "100/minute;1000/hour"
    """

    # Authentication endpoints (strict - prevent brute force)
    AUTH_LOGIN = "5/minute;20/hour"
    AUTH_REFRESH = "30/minute"
    AUTH_LOGOUT = "10/minute"

    # Standard API calls (moderate)
    STANDARD = f"{settings.RATE_LIMIT_PER_MINUTE}/minute"

    # Search/list endpoints (moderate - can return large datasets)
    SEARCH = "60/minute;500/hour"
    SEARCH_HEAVY = "20/minute;100/hour"  # For complex searches

    # Image endpoints (bandwidth intensive)
    IMAGE_VIEW = "120/minute;1000/hour"  # Viewing images
    IMAGE_MINT_TOKEN = "60/minute;500/hour"  # Minting one-time tokens
    IMAGE_MINT_BATCH = "10/minute;50/hour"  # Batch token minting (up to 10 per call)

    # Export/report endpoints (CPU/memory intensive)
    EXPORT_CSV = "5/minute;20/hour"
    REPORT_GENERATE = "10/minute;50/hour"
    REPORT_PDF = "5/minute;30/hour"

    # Batch operations (very expensive)
    BATCH_OPERATION = "5/minute;20/hour"

    # Monitoring/metrics (should be called by Prometheus, not humans)
    MONITORING = "30/minute"

    # Per-tenant quotas (applied in addition to per-user limits)
    # These prevent one tenant from consuming all resources
    TENANT_SEARCH = "300/minute;3000/hour"
    TENANT_IMAGE = "600/minute;5000/hour"
    TENANT_EXPORT = "30/minute;200/hour"

    @classmethod
    def get_limit(cls, category: str) -> str:
        """Get rate limit string for a category."""
        return getattr(cls, category.upper(), cls.STANDARD)


# =============================================================================
# Decorator Helpers
# =============================================================================


def apply_rate_limit(
    category: str = "STANDARD",
    per_user: bool = True,
    per_tenant: bool = False,
):
    """
    Factory for creating rate limit decorators.

    Usage:
        @router.get("/items")
        @apply_rate_limit("SEARCH", per_user=True, per_tenant=True)
        async def list_items(...):
            ...

    Args:
        category: Rate limit category from RateLimits class
        per_user: Apply per-user rate limiting
        per_tenant: Apply additional per-tenant rate limiting
    """
    limit_string = RateLimits.get_limit(category)

    if per_user:
        return user_limiter.limit(limit_string)
    elif per_tenant:
        return tenant_limiter.limit(limit_string)
    else:
        return limiter.limit(limit_string)
