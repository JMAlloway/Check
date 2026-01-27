"""
Standardized error responses for the Check Review Console API.

This module provides consistent error response formatting across all endpoints,
making it easier for clients to handle errors and for debugging.
"""

from enum import Enum
from typing import Any

from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel


class ErrorCode(str, Enum):
    """Standardized error codes for API responses."""

    # Authentication errors (1xxx)
    INVALID_CREDENTIALS = "AUTH_1001"
    TOKEN_EXPIRED = "AUTH_1002"
    TOKEN_INVALID = "AUTH_1003"
    MFA_REQUIRED = "AUTH_1004"
    MFA_INVALID = "AUTH_1005"
    ACCOUNT_LOCKED = "AUTH_1006"
    ACCOUNT_INACTIVE = "AUTH_1007"
    SESSION_EXPIRED = "AUTH_1008"
    CSRF_VALIDATION_FAILED = "AUTH_1009"

    # Authorization errors (2xxx)
    PERMISSION_DENIED = "AUTHZ_2001"
    INSUFFICIENT_ROLE = "AUTHZ_2002"
    ENTITLEMENT_DENIED = "AUTHZ_2003"
    DUAL_CONTROL_REQUIRED = "AUTHZ_2004"
    SELF_APPROVAL_DENIED = "AUTHZ_2005"

    # Validation errors (3xxx)
    VALIDATION_ERROR = "VAL_3001"
    INVALID_INPUT = "VAL_3002"
    MISSING_REQUIRED_FIELD = "VAL_3003"
    INVALID_FORMAT = "VAL_3004"
    VALUE_OUT_OF_RANGE = "VAL_3005"
    DUPLICATE_ENTRY = "VAL_3006"

    # Resource errors (4xxx)
    RESOURCE_NOT_FOUND = "RES_4001"
    RESOURCE_ALREADY_EXISTS = "RES_4002"
    RESOURCE_LOCKED = "RES_4003"
    RESOURCE_EXPIRED = "RES_4004"
    RESOURCE_CONFLICT = "RES_4005"

    # Business logic errors (5xxx)
    INVALID_STATE_TRANSITION = "BIZ_5001"
    POLICY_VIOLATION = "BIZ_5002"
    AI_FLAGS_NOT_ACKNOWLEDGED = "BIZ_5003"
    WORKFLOW_ERROR = "BIZ_5004"
    LIMIT_EXCEEDED = "BIZ_5005"

    # System errors (6xxx)
    INTERNAL_ERROR = "SYS_6001"
    DATABASE_ERROR = "SYS_6002"
    EXTERNAL_SERVICE_ERROR = "SYS_6003"
    RATE_LIMIT_EXCEEDED = "SYS_6004"
    SERVICE_UNAVAILABLE = "SYS_6005"


class ErrorDetail(BaseModel):
    """Detailed error information."""

    field: str | None = None
    message: str
    code: str | None = None


class APIError(BaseModel):
    """Standardized API error response."""

    error: str
    code: ErrorCode
    message: str
    details: list[ErrorDetail] | None = None
    request_id: str | None = None
    timestamp: str | None = None


class APIException(HTTPException):
    """Extended HTTPException with standardized error codes."""

    def __init__(
        self,
        status_code: int,
        code: ErrorCode,
        message: str,
        details: list[ErrorDetail] | None = None,
        headers: dict[str, str] | None = None,
    ):
        self.code = code
        self.message = message
        self.details = details
        super().__init__(status_code=status_code, detail=message, headers=headers)


# Pre-defined exceptions for common errors
class NotFoundError(APIException):
    """Resource not found error."""

    def __init__(self, resource: str, resource_id: str | None = None):
        message = f"{resource} not found"
        if resource_id:
            message = f"{resource} with id '{resource_id}' not found"
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            code=ErrorCode.RESOURCE_NOT_FOUND,
            message=message,
        )


class UnauthorizedError(APIException):
    """Authentication required error."""

    def __init__(self, message: str = "Authentication required"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code=ErrorCode.INVALID_CREDENTIALS,
            message=message,
            headers={"WWW-Authenticate": "Bearer"},
        )


class ForbiddenError(APIException):
    """Permission denied error."""

    def __init__(self, message: str = "Permission denied"):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            code=ErrorCode.PERMISSION_DENIED,
            message=message,
        )


class ValidationError(APIException):
    """Validation error."""

    def __init__(self, message: str, details: list[ErrorDetail] | None = None):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            code=ErrorCode.VALIDATION_ERROR,
            message=message,
            details=details,
        )


class ConflictError(APIException):
    """Resource conflict error."""

    def __init__(self, message: str):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            code=ErrorCode.RESOURCE_CONFLICT,
            message=message,
        )


class RateLimitError(APIException):
    """Rate limit exceeded error."""

    def __init__(self, retry_after: int | None = None):
        headers = {}
        if retry_after:
            headers["Retry-After"] = str(retry_after)
        super().__init__(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            code=ErrorCode.RATE_LIMIT_EXCEEDED,
            message="Rate limit exceeded. Please try again later.",
            headers=headers if headers else None,
        )


class InternalError(APIException):
    """Internal server error."""

    def __init__(self, message: str = "An internal error occurred"):
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            code=ErrorCode.INTERNAL_ERROR,
            message=message,
        )


def create_error_response(
    code: ErrorCode,
    message: str,
    details: list[ErrorDetail] | None = None,
    request_id: str | None = None,
) -> dict[str, Any]:
    """Create a standardized error response dictionary."""
    from datetime import datetime, timezone

    response = {
        "error": code.name.lower().replace("_", " ").title(),
        "code": code.value,
        "message": message,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    if details:
        response["details"] = [d.model_dump(exclude_none=True) for d in details]

    if request_id:
        response["request_id"] = request_id

    return response


async def api_exception_handler(request: Request, exc: APIException) -> JSONResponse:
    """Handle APIException and return standardized response."""
    request_id = getattr(request.state, "request_id", None)

    return JSONResponse(
        status_code=exc.status_code,
        content=create_error_response(
            code=exc.code,
            message=exc.message,
            details=exc.details,
            request_id=request_id,
        ),
        headers=exc.headers,
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Handle standard HTTPException and convert to standardized response."""
    request_id = getattr(request.state, "request_id", None)

    # Map status codes to error codes
    status_to_code = {
        400: ErrorCode.VALIDATION_ERROR,
        401: ErrorCode.INVALID_CREDENTIALS,
        403: ErrorCode.PERMISSION_DENIED,
        404: ErrorCode.RESOURCE_NOT_FOUND,
        409: ErrorCode.RESOURCE_CONFLICT,
        422: ErrorCode.INVALID_INPUT,
        429: ErrorCode.RATE_LIMIT_EXCEEDED,
        500: ErrorCode.INTERNAL_ERROR,
        503: ErrorCode.SERVICE_UNAVAILABLE,
    }

    code = status_to_code.get(exc.status_code, ErrorCode.INTERNAL_ERROR)
    message = exc.detail if isinstance(exc.detail, str) else "An error occurred"

    return JSONResponse(
        status_code=exc.status_code,
        content=create_error_response(
            code=code,
            message=message,
            request_id=request_id,
        ),
        headers=getattr(exc, "headers", None),
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle unexpected exceptions."""
    import logging

    logger = logging.getLogger(__name__)
    logger.exception("Unhandled exception: %s", exc)

    request_id = getattr(request.state, "request_id", None)

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=create_error_response(
            code=ErrorCode.INTERNAL_ERROR,
            message="An unexpected error occurred",
            request_id=request_id,
        ),
    )
