"""
API dependencies for authentication and common functionality.
"""
import time
import uuid
from typing import Optional

from fastapi import Depends, Header, HTTPException, Request, status

from ..audit import get_audit_logger
from ..core.config import get_settings
from ..core.security import JWTClaims, get_jwt_validator, get_path_validator
from ..services import get_image_service


async def get_correlation_id(
    x_correlation_id: Optional[str] = Header(None, alias="X-Correlation-ID")
) -> str:
    """
    Get or generate a correlation ID for request tracing.

    Uses the X-Correlation-ID header if provided, otherwise generates one.
    """
    return x_correlation_id or str(uuid.uuid4())


async def get_request_start_time() -> float:
    """Get the request start time for latency tracking."""
    return time.time()


async def validate_jwt(
    request: Request,
    authorization: Optional[str] = Header(None),
    correlation_id: str = Depends(get_correlation_id)
) -> JWTClaims:
    """
    Validate JWT from Authorization header.

    Expects: Authorization: Bearer <token>

    Returns validated claims or raises HTTPException.
    """
    audit_logger = get_audit_logger()
    validator = get_jwt_validator()

    # Check for Authorization header
    if not authorization:
        await audit_logger.log_auth_failed(
            endpoint=str(request.url.path),
            correlation_id=correlation_id,
            error_message="Missing Authorization header"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error_code": "AUTH_FAILED",
                "message": "Missing Authorization header",
                "correlation_id": correlation_id
            },
            headers={"WWW-Authenticate": "Bearer"}
        )

    # Parse Bearer token
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        await audit_logger.log_auth_failed(
            endpoint=str(request.url.path),
            correlation_id=correlation_id,
            error_message="Invalid Authorization header format"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error_code": "AUTH_FAILED",
                "message": "Invalid Authorization header format. Expected: Bearer <token>",
                "correlation_id": correlation_id
            },
            headers={"WWW-Authenticate": "Bearer"}
        )

    token = parts[1]

    # Validate token
    is_valid, claims, error = validator.validate(token)

    if not is_valid:
        await audit_logger.log_auth_failed(
            endpoint=str(request.url.path),
            correlation_id=correlation_id,
            error_message=error
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error_code": "AUTH_FAILED",
                "message": error,
                "correlation_id": correlation_id
            },
            headers={"WWW-Authenticate": "Bearer"}
        )

    # Check roles
    has_access, role_error = validator.check_roles(claims)
    if not has_access:
        await audit_logger.log_denied(
            endpoint=str(request.url.path),
            correlation_id=correlation_id,
            error_code="FORBIDDEN",
            error_message=role_error,
            org_id=claims.org_id,
            user_id=claims.sub
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error_code": "FORBIDDEN",
                "message": role_error,
                "correlation_id": correlation_id
            }
        )

    return claims


def validate_path(path: str, correlation_id: str, claims: JWTClaims = None) -> None:
    """
    Validate a UNC path against allowed roots.

    Raises HTTPException if path is not allowed.
    """
    import asyncio

    from ..audit import get_audit_logger

    validator = get_path_validator()
    is_valid, error = validator.validate(path)

    if not is_valid:
        # Log blocked path
        audit_logger = get_audit_logger()

        # We need to run async log in sync context
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop:
            # Schedule the coroutine
            asyncio.create_task(audit_logger.log_path_blocked(
                endpoint="/v1/images/by-handle",
                correlation_id=correlation_id,
                path=path,
                org_id=claims.org_id if claims else None,
                user_id=claims.sub if claims else None
            ))

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error_code": "PATH_NOT_ALLOWED",
                "message": "Path not in allowed share roots",
                "correlation_id": correlation_id
            }
        )
