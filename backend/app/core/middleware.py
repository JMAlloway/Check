"""Security middleware for token redaction and logging protection.

This module provides middleware to prevent image access token IDs from leaking
in logs, error traces, and referrer headers. Critical for bank-grade security.

Token Security Model:
- Image access tokens are one-time-use UUID tokens stored in the database
- Token IDs must never appear in logs (prevents replay attacks if logs leak)
- Token IDs must never leak via Referer headers (browser security)
"""

import logging
import re
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

# Pattern to match image access token IDs in paths
# Matches /api/v1/images/secure/{token_id} where token_id is a UUID
# UUID format: 8-4-4-4-12 hex chars (e.g., 550e8400-e29b-41d4-a716-446655440000)
# Also matches legacy JWT format for backwards compatibility during transition
SECURE_IMAGE_PATH_PATTERN = re.compile(
    r"(/api/v1/images/secure/)"
    r"([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"  # UUID
    r"|[A-Za-z0-9_-]+\.?[A-Za-z0-9_-]*\.?[A-Za-z0-9_-]*)"  # Legacy JWT fallback
)
TOKEN_REDACTED = "[TOKEN_REDACTED]"


def redact_token_from_path(path: str) -> str:
    """Redact image access token IDs from URL paths.

    Args:
        path: The request path potentially containing a token ID

    Returns:
        Path with token IDs replaced by [TOKEN_REDACTED]
    """
    return SECURE_IMAGE_PATH_PATTERN.sub(rf"\1{TOKEN_REDACTED}", path)


def is_secure_image_path(path: str) -> bool:
    """Check if a path is a secure image URL that contains a token ID."""
    return path.startswith("/api/v1/images/secure/")


class TokenRedactionFilter(logging.Filter):
    """Logging filter that redacts image access token IDs from log records.

    This filter intercepts log messages and redacts any token IDs from
    secure image URLs to prevent token leakage via application logs.
    Token IDs are one-time-use UUIDs - if they leak, an attacker could
    replay them before the legitimate user.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        """Filter and redact tokens from log record."""
        # Redact tokens from the message
        if hasattr(record, "msg") and isinstance(record.msg, str):
            record.msg = SECURE_IMAGE_PATH_PATTERN.sub(rf"\1{TOKEN_REDACTED}", record.msg)

        # Redact tokens from args if present
        if hasattr(record, "args") and record.args:
            if isinstance(record.args, tuple):
                record.args = tuple(
                    (
                        SECURE_IMAGE_PATH_PATTERN.sub(rf"\1{TOKEN_REDACTED}", arg)
                        if isinstance(arg, str)
                        else arg
                    )
                    for arg in record.args
                )
            elif isinstance(record.args, dict):
                record.args = {
                    k: (
                        SECURE_IMAGE_PATH_PATTERN.sub(rf"\1{TOKEN_REDACTED}", v)
                        if isinstance(v, str)
                        else v
                    )
                    for k, v in record.args.items()
                }

        # Always allow the record through (after redaction)
        return True


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware to add standard security headers to all API responses.

    Headers added:
    - X-Content-Type-Options: nosniff - Prevents MIME sniffing
    - X-Frame-Options: DENY - Prevents clickjacking
    - X-XSS-Protection: 0 - Disabled (CSP is preferred, and this can introduce vulnerabilities)
    - Referrer-Policy: strict-origin-when-cross-origin - Limits referrer information
    - Content-Security-Policy: default-src 'self' - Restricts resource loading
    - Permissions-Policy: Restricts browser features
    - Cache-Control: For API responses, prevent caching of sensitive data

    Note: These are applied to ALL responses. Image endpoints have additional headers.
    """

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Response]
    ) -> Response:
        """Process request and add security headers."""
        response = await call_next(request)

        # Standard security headers for all API responses
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        # X-XSS-Protection disabled - can cause vulnerabilities, CSP is preferred
        response.headers["X-XSS-Protection"] = "0"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Permissions-Policy to disable unnecessary browser features
        response.headers["Permissions-Policy"] = (
            "accelerometer=(), camera=(), geolocation=(), gyroscope=(), "
            "magnetometer=(), microphone=(), payment=(), usb=()"
        )

        # Content-Security-Policy for API responses
        # Note: This is restrictive - frontend serves its own CSP
        if request.url.path.startswith("/api/"):
            response.headers["Content-Security-Policy"] = (
                "default-src 'none'; frame-ancestors 'none'"
            )
            # Prevent caching of API responses with sensitive data
            if "Cache-Control" not in response.headers:
                response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, private"

        return response


class TokenRedactionMiddleware(BaseHTTPMiddleware):
    """Middleware to add security headers for secure image endpoints.

    For secure image endpoints (/api/v1/images/secure/{token_id}):
    - Adds Referrer-Policy: no-referrer to prevent token ID leakage via referrer
    - Token IDs are one-time-use, so leaking them enables replay attacks

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
    """Redact image access token IDs from exception arguments.

    Args:
        exc: The exception to sanitize

    Returns:
        Exception with redacted token ID strings in args
    """
    if exc.args:
        new_args = tuple(
            (
                SECURE_IMAGE_PATH_PATTERN.sub(rf"\1{TOKEN_REDACTED}", arg)
                if isinstance(arg, str)
                else arg
            )
            for arg in exc.args
        )
        exc.args = new_args
    return exc
