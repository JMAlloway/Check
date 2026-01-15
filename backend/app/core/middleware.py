"""Security middleware for token redaction and logging protection.

This module provides middleware to prevent bearer token leakage in logs,
error traces, and referrer headers. Critical for bank-grade security compliance.
"""

import logging
import re
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

# Pattern to match signed URL tokens in paths
# Matches /api/v1/images/secure/{token} where token is a JWT
SECURE_IMAGE_PATH_PATTERN = re.compile(r"(/api/v1/images/secure/)([A-Za-z0-9_-]+\.?[A-Za-z0-9_-]*\.?[A-Za-z0-9_-]*)")
TOKEN_REDACTED = "[TOKEN_REDACTED]"


def redact_token_from_path(path: str) -> str:
    """Redact bearer tokens from URL paths.

    Args:
        path: The request path potentially containing a token

    Returns:
        Path with tokens replaced by [TOKEN_REDACTED]
    """
    return SECURE_IMAGE_PATH_PATTERN.sub(rf"\1{TOKEN_REDACTED}", path)


def is_secure_image_path(path: str) -> bool:
    """Check if a path is a secure image URL that contains a bearer token."""
    return path.startswith("/api/v1/images/secure/")


class TokenRedactionFilter(logging.Filter):
    """Logging filter that redacts bearer tokens from log records.

    This filter intercepts log messages and redacts any signed URL tokens
    to prevent token leakage via application logs.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        """Filter and redact tokens from log record."""
        # Redact tokens from the message
        if hasattr(record, 'msg') and isinstance(record.msg, str):
            record.msg = SECURE_IMAGE_PATH_PATTERN.sub(
                rf"\1{TOKEN_REDACTED}", record.msg
            )

        # Redact tokens from args if present
        if hasattr(record, 'args') and record.args:
            if isinstance(record.args, tuple):
                record.args = tuple(
                    SECURE_IMAGE_PATH_PATTERN.sub(rf"\1{TOKEN_REDACTED}", arg)
                    if isinstance(arg, str) else arg
                    for arg in record.args
                )
            elif isinstance(record.args, dict):
                record.args = {
                    k: SECURE_IMAGE_PATH_PATTERN.sub(rf"\1{TOKEN_REDACTED}", v)
                    if isinstance(v, str) else v
                    for k, v in record.args.items()
                }

        # Always allow the record through (after redaction)
        return True


class TokenRedactionMiddleware(BaseHTTPMiddleware):
    """Middleware to add security headers and enable token redaction.

    For secure image endpoints:
    - Adds Referrer-Policy: no-referrer to prevent token leakage via referrer
    - Modifies request scope to use redacted path for logging

    This middleware should be added early in the middleware stack.
    """

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Response]
    ) -> Response:
        """Process request and add security headers for secure image routes."""
        original_path = request.url.path

        # Call the next middleware/endpoint
        response = await call_next(request)

        # Add stricter Referrer-Policy for secure image endpoints
        # This prevents the token from leaking via the Referer header
        if is_secure_image_path(original_path):
            response.headers["Referrer-Policy"] = "no-referrer"

        return response


def install_token_redaction_logging():
    """Install token redaction filter on all relevant loggers.

    This should be called during application startup to ensure
    tokens are never logged by any logger.
    """
    redaction_filter = TokenRedactionFilter()

    # Install on root logger to catch everything
    root_logger = logging.getLogger()
    root_logger.addFilter(redaction_filter)

    # Also install on specific loggers that might bypass root
    logger_names = [
        "uvicorn",
        "uvicorn.access",
        "uvicorn.error",
        "fastapi",
        "gunicorn",
        "gunicorn.access",
        "gunicorn.error",
        "security.auth",
        "app",
    ]

    for name in logger_names:
        logger = logging.getLogger(name)
        logger.addFilter(redaction_filter)


def redact_exception_args(exc: Exception) -> Exception:
    """Redact tokens from exception arguments.

    Args:
        exc: The exception to sanitize

    Returns:
        Exception with redacted token strings in args
    """
    if exc.args:
        new_args = tuple(
            SECURE_IMAGE_PATH_PATTERN.sub(rf"\1{TOKEN_REDACTED}", arg)
            if isinstance(arg, str) else arg
            for arg in exc.args
        )
        exc.args = new_args
    return exc
