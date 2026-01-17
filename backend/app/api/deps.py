"""API dependencies for dependency injection."""

import logging
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.security import decode_token
from app.db.session import AsyncSessionLocal
from app.models.user import User, Role

# Security audit logger - separate from general logging for SIEM integration
auth_logger = logging.getLogger("security.auth")

security = HTTPBearer()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency to get database session.

    NOTE: This does NOT auto-commit. Each write path must explicitly call
    `await db.commit()` to persist changes. This prevents:
    - Accidental partial commits
    - Read-only endpoints modifying state
    - Surprise side effects in complex transactions

    On exception, the session is rolled back automatically.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def get_current_user(
    db: Annotated[AsyncSession, Depends(get_db)],
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
) -> User:
    """Get the current authenticated user."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    token = credentials.credentials
    payload = decode_token(token)

    if payload is None:
        raise credentials_exception

    if payload.get("type") != "access":
        raise credentials_exception

    user_id = payload.get("sub")
    if user_id is None:
        raise credentials_exception

    result = await db.execute(
        select(User)
        .options(selectinload(User.roles).selectinload(Role.permissions))
        .where(User.id == user_id, User.is_active == True)
    )
    user = result.scalar_one_or_none()

    if user is None:
        raise credentials_exception

    return user


async def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Get current user if active."""
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


async def get_current_active_superuser(
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> User:
    """Get current user if active and superuser."""
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Superuser access required",
        )
    return current_user


def _log_auth_failure(
    event_type: str,
    user: User,
    resource: str,
    action: str,
    request: Request | None = None,
    extra: dict | None = None,
) -> None:
    """
    Log authorization failure for security audit.

    These logs should be:
    - Shipped to SIEM for monitoring
    - Retained per compliance requirements
    - Alertable for anomaly detection
    """
    log_data = {
        "event": "authorization_failure",
        "event_type": event_type,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "user_id": user.id,
        "username": user.username,
        "resource": resource,
        "action": action,
        "user_roles": [r.name for r in user.roles] if user.roles else [],
    }

    if request:
        log_data["ip_address"] = request.client.host if request.client else None
        log_data["user_agent"] = request.headers.get("user-agent")
        log_data["path"] = request.url.path
        log_data["method"] = request.method

    if extra:
        log_data.update(extra)

    auth_logger.warning(
        f"AUTH_FAILURE: {event_type} - user={user.username} resource={resource}:{action}",
        extra={"security_event": log_data},
    )


def require_permission(resource: str, action: str):
    """
    Dependency factory for permission checking.

    Logs all authorization failures for security audit.

    Usage:
        @router.get("/items")
        async def list_items(
            current_user: Annotated[User, Depends(require_permission("item", "view"))],
        ):
            ...
    """

    async def permission_checker(
        request: Request,
        current_user: Annotated[User, Depends(get_current_active_user)],
    ) -> User:
        if not current_user.has_permission(resource, action):
            _log_auth_failure(
                event_type="permission_denied",
                user=current_user,
                resource=resource,
                action=action,
                request=request,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: {resource}:{action}",
            )
        return current_user

    return permission_checker


def require_role(role_name: str):
    """
    Dependency factory for role checking.

    Logs all authorization failures for security audit.
    """

    async def role_checker(
        request: Request,
        current_user: Annotated[User, Depends(get_current_active_user)],
    ) -> User:
        if not current_user.has_role(role_name) and not current_user.is_superuser:
            _log_auth_failure(
                event_type="role_required",
                user=current_user,
                resource="role",
                action=role_name,
                request=request,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role required: {role_name}",
            )
        return current_user

    return role_checker


def require_any_permission(*permissions: tuple[str, str]):
    """
    Require at least one of the specified permissions.

    Usage:
        @router.get("/items")
        async def view_items(
            current_user: Annotated[User, Depends(require_any_permission(
                ("item", "view"),
                ("item", "admin"),
            ))],
        ):
            ...
    """

    async def permission_checker(
        request: Request,
        current_user: Annotated[User, Depends(get_current_active_user)],
    ) -> User:
        for resource, action in permissions:
            if current_user.has_permission(resource, action):
                return current_user

        _log_auth_failure(
            event_type="permission_denied",
            user=current_user,
            resource=",".join(f"{r}:{a}" for r, a in permissions),
            action="any",
            request=request,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Permission denied: requires one of {permissions}",
        )

    return permission_checker


# Type aliases for commonly used dependencies
DBSession = Annotated[AsyncSession, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_active_user)]


# Pre-built permission dependencies for common operations
RequireCheckView = Annotated[User, Depends(require_permission("check_item", "view"))]
RequireCheckReview = Annotated[User, Depends(require_permission("check_item", "review"))]
RequireCheckApprove = Annotated[User, Depends(require_permission("check_item", "approve"))]
RequireAuditView = Annotated[User, Depends(require_permission("audit", "view"))]
RequireAdmin = Annotated[User, Depends(require_role("admin"))]


# =============================================================================
# Tenant Isolation Helpers
# =============================================================================

def get_tenant_id(user: User) -> str:
    """
    Get tenant_id from user with validation.

    CRITICAL: Never use a default/fallback tenant_id - this would allow
    cross-tenant data access. If tenant_id is missing, it's a data integrity
    issue that must fail loudly.

    Args:
        user: Authenticated user object

    Returns:
        The user's tenant_id

    Raises:
        HTTPException: If tenant_id is missing (data integrity error)
    """
    if not user.tenant_id:
        auth_logger.error(
            f"CRITICAL: User {user.id} has no tenant_id - data integrity issue",
            extra={
                "security_event": {
                    "event": "tenant_missing",
                    "user_id": user.id,
                    "username": user.username,
                }
            },
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="User tenant configuration error",
        )
    return user.tenant_id


async def get_resource_with_tenant_check(
    db: AsyncSession,
    model_class,
    resource_id: str,
    tenant_id: str,
    *,
    resource_name: str = "Resource",
    options: list | None = None,
    additional_filters: list | None = None,
):
    """
    Fetch a resource by ID with mandatory tenant isolation.

    This helper enforces tenant isolation for all "get by ID" operations.
    Returns 404 for both "not found" and "wrong tenant" to prevent
    enumeration attacks.

    Args:
        db: Database session
        model_class: SQLAlchemy model class (must have tenant_id column)
        resource_id: The resource ID to fetch
        tenant_id: Current user's tenant_id
        resource_name: Human-readable name for error messages
        options: SQLAlchemy query options (e.g., selectinload)
        additional_filters: Additional WHERE conditions

    Returns:
        The resource if found and owned by tenant

    Raises:
        HTTPException: 404 if not found or wrong tenant
    """
    query = select(model_class).where(
        model_class.id == resource_id,
        model_class.tenant_id == tenant_id,
    )

    if options:
        for opt in options:
            query = query.options(opt)

    if additional_filters:
        for filter_condition in additional_filters:
            query = query.where(filter_condition)

    result = await db.execute(query)
    resource = result.scalar_one_or_none()

    if not resource:
        # Log potential cross-tenant access attempt for security monitoring
        # We don't reveal whether the item exists in another tenant
        auth_logger.info(
            f"Resource not found or tenant mismatch: {resource_name} {resource_id}",
            extra={
                "security_event": {
                    "event": "resource_access_denied",
                    "resource_type": resource_name.lower().replace(" ", "_"),
                    "resource_id": resource_id,
                    "tenant_id": tenant_id,
                }
            },
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{resource_name} not found",
        )

    return resource


def log_cross_tenant_attempt(
    user: User,
    resource_type: str,
    resource_id: str,
    attempted_action: str,
    request: Request | None = None,
) -> None:
    """
    Log a potential cross-tenant access attempt.

    Use this when you detect a user trying to access another tenant's data.
    These logs should be monitored for security threats.

    Args:
        user: The user attempting access
        resource_type: Type of resource (e.g., "check_item", "decision")
        resource_id: ID of the resource
        attempted_action: What the user tried to do
        request: Optional request for IP/user-agent logging
    """
    log_data = {
        "event": "cross_tenant_attempt",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "user_id": user.id,
        "username": user.username,
        "tenant_id": user.tenant_id,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "attempted_action": attempted_action,
    }

    if request:
        log_data["ip_address"] = request.client.host if request.client else None
        log_data["user_agent"] = request.headers.get("user-agent")
        log_data["path"] = request.url.path

    auth_logger.warning(
        f"CROSS_TENANT_ATTEMPT: user={user.username} tried {attempted_action} on {resource_type}/{resource_id}",
        extra={"security_event": log_data},
    )
