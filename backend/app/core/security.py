"""Security utilities for authentication and authorization."""

from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against a hash."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a password."""
    return pwd_context.hash(password)


def create_access_token(
    subject: str | int,
    expires_delta: timedelta | None = None,
    additional_claims: dict[str, Any] | None = None,
) -> str:
    """Create a JWT access token."""
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )

    to_encode = {"exp": expire, "sub": str(subject), "type": "access"}
    if additional_claims:
        to_encode.update(additional_claims)

    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def create_refresh_token(subject: str | int) -> str:
    """Create a JWT refresh token."""
    expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode = {"exp": expire, "sub": str(subject), "type": "refresh"}
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def decode_token(token: str) -> dict[str, Any] | None:
    """Decode and validate a JWT token."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except JWTError:
        return None


def generate_signed_url(
    resource_id: str,
    user_id: str,
    expires_in: int | None = None,
) -> str:
    """Generate a short-lived signed URL for secure resource access.

    Security model:
    - This is a BEARER TOKEN - anyone with the URL can access the resource
    - Security relies on short TTL (default 90s) to limit exposure window
    - user_id is embedded for AUDIT LOGGING only, not access control
    - URLs should not be logged, shared, or exposed in referrer headers

    For bank-grade security, consider authenticated blob fetches instead.
    """
    if expires_in is None:
        expires_in = settings.IMAGE_SIGNED_URL_TTL_SECONDS

    expire = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
    to_encode = {
        "exp": expire,
        "resource": resource_id,
        "sub": user_id,  # Bind to user
        "type": "signed_url",
    }
    token = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return f"/api/v1/images/secure/{token}"


class SignedUrlPayload:
    """Payload from a verified signed URL (bearer token).

    Note: user_id is for audit logging only - access is NOT restricted to this user.
    """
    def __init__(self, resource_id: str, user_id: str):
        self.resource_id = resource_id
        self.user_id = user_id  # For audit logging, not access control


def verify_signed_url(token: str) -> SignedUrlPayload | None:
    """Verify a signed URL token and return the payload if valid.

    This validates:
    - Token signature (JWT)
    - Token expiration (short TTL)
    - Token type (signed_url)

    This does NOT validate:
    - User authentication (bearer token model)

    Returns:
        SignedUrlPayload with resource_id and user_id, or None if invalid/expired.
    """
    payload = decode_token(token)
    if payload and payload.get("type") == "signed_url":
        resource_id = payload.get("resource")
        user_id = payload.get("sub")
        if resource_id and user_id:
            return SignedUrlPayload(resource_id=resource_id, user_id=user_id)
    return None
