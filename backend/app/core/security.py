"""Security utilities for authentication and authorization."""

import secrets
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
    tenant_id: str | None = None,
) -> tuple[str, str]:
    """Generate a short-lived signed URL for secure resource access.

    Security model:
    - This is a BEARER TOKEN - anyone with the URL can access the resource
    - Security relies on short TTL (default 90s) to limit exposure window
    - user_id is embedded for AUDIT LOGGING only, not access control
    - URLs should not be logged, shared, or exposed in referrer headers
    - Uses dedicated IMAGE_SIGNING_KEY (separate from auth SECRET_KEY)
    - Includes jti (JWT ID) for potential revocation-list checking

    For bank-grade security, consider authenticated blob fetches instead.

    Returns:
        Tuple of (signed_url, jti) - jti can be stored for revocation if needed.
    """
    if expires_in is None:
        expires_in = settings.IMAGE_SIGNED_URL_TTL_SECONDS

    expire = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
    # Generate unique token ID for revocation capability
    jti = secrets.token_urlsafe(16)

    to_encode = {
        "exp": expire,
        "resource": resource_id,
        "sub": user_id,  # For audit logging
        "type": "image_url",  # Distinct from auth tokens
        "jti": jti,  # Unique ID for revocation tracking
    }
    # Include tenant_id if provided for additional validation
    if tenant_id:
        to_encode["tid"] = tenant_id

    # Use dedicated IMAGE_SIGNING_KEY (not the auth SECRET_KEY)
    token = jwt.encode(
        to_encode,
        settings.IMAGE_SIGNING_KEY,
        algorithm=settings.IMAGE_SIGNING_ALGORITHM,
    )
    return f"/api/v1/images/secure/{token}", jti


class SignedUrlPayload:
    """Payload from a verified signed URL (bearer token).

    Note: user_id is for audit logging only - access is NOT restricted to this user.
    """

    def __init__(
        self,
        resource_id: str,
        user_id: str,
        jti: str | None = None,
        tenant_id: str | None = None,
    ):
        self.resource_id = resource_id
        self.user_id = user_id  # For audit logging, not access control
        self.jti = jti  # For revocation checking
        self.tenant_id = tenant_id  # For tenant validation


def decode_image_token(token: str) -> dict[str, Any] | None:
    """Decode and validate an image URL token using dedicated IMAGE_SIGNING_KEY.

    This is separate from decode_token() which uses SECRET_KEY for auth tokens.
    """
    try:
        payload = jwt.decode(
            token,
            settings.IMAGE_SIGNING_KEY,
            algorithms=[settings.IMAGE_SIGNING_ALGORITHM],
        )
        return payload
    except JWTError:
        return None


def verify_signed_url(
    token: str,
    expected_tenant_id: str | None = None,
    revoked_jtis: set[str] | None = None,
) -> SignedUrlPayload | None:
    """Verify a signed URL token and return the payload if valid.

    This validates:
    - Token signature (using dedicated IMAGE_SIGNING_KEY)
    - Token expiration (short TTL)
    - Token type (image_url)
    - Tenant ID (if expected_tenant_id provided)
    - JTI not in revocation list (if revoked_jtis provided)

    This does NOT validate:
    - User authentication (bearer token model)

    Args:
        token: The JWT token from the signed URL
        expected_tenant_id: If provided, validates the token's tenant_id matches
        revoked_jtis: If provided, checks the token's jti is not revoked

    Returns:
        SignedUrlPayload with resource_id, user_id, jti, and tenant_id, or None if invalid.
    """
    # Use dedicated image token decoder (not auth token decoder)
    payload = decode_image_token(token)

    # Support both old "signed_url" type and new "image_url" type during migration
    if payload and payload.get("type") in ("signed_url", "image_url"):
        resource_id = payload.get("resource")
        user_id = payload.get("sub")
        jti = payload.get("jti")
        tenant_id = payload.get("tid")

        if not resource_id or not user_id:
            return None

        # Check tenant_id if expected
        if expected_tenant_id and tenant_id and tenant_id != expected_tenant_id:
            return None

        # Check if jti is revoked
        if revoked_jtis and jti and jti in revoked_jtis:
            return None

        return SignedUrlPayload(
            resource_id=resource_id,
            user_id=user_id,
            jti=jti,
            tenant_id=tenant_id,
        )
    return None
