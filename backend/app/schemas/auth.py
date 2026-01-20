"""Authentication schemas."""

import re
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator

# Password complexity requirements for bank-grade security
PASSWORD_MIN_LENGTH = 12
PASSWORD_REQUIREMENTS = """
Password must:
- Be at least 12 characters long
- Contain at least one uppercase letter (A-Z)
- Contain at least one lowercase letter (a-z)
- Contain at least one digit (0-9)
- Contain at least one special character (!@#$%^&*()_+-=[]{}|;:,.<>?)
"""


def validate_password_complexity(password: str) -> str:
    """Validate password meets bank-grade complexity requirements."""
    errors = []

    if len(password) < PASSWORD_MIN_LENGTH:
        errors.append(f"at least {PASSWORD_MIN_LENGTH} characters")

    if not re.search(r"[A-Z]", password):
        errors.append("at least one uppercase letter")

    if not re.search(r"[a-z]", password):
        errors.append("at least one lowercase letter")

    if not re.search(r"\d", password):
        errors.append("at least one digit")

    if not re.search(r"[!@#$%^&*()_+\-=\[\]{}|;:,.<>?]", password):
        errors.append("at least one special character")

    if errors:
        raise ValueError(f"Password must contain: {', '.join(errors)}")

    return password


class LoginRequest(BaseModel):
    """Login request schema."""

    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=8)  # Login allows existing passwords
    mfa_code: str | None = None
    device_fingerprint: str | None = Field(
        None, max_length=255, description="Client device fingerprint for session tracking"
    )


class RefreshTokenRequest(BaseModel):
    """Refresh token request schema."""

    refresh_token: str


class Token(BaseModel):
    """Token response schema."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class LoginRoleInfo(BaseModel):
    """Minimal role info included in login response."""

    id: str
    name: str
    is_system: bool = False


class LoginUserInfo(BaseModel):
    """User info included in login response."""

    id: str
    username: str
    email: str
    full_name: str | None
    is_superuser: bool
    roles: list[LoginRoleInfo]
    permissions: list[str]


class LoginResponse(BaseModel):
    """Login response with tokens and user info."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: LoginUserInfo


class TokenPayload(BaseModel):
    """Token payload schema."""

    sub: str
    exp: datetime
    type: str
    roles: list[str] | None = None
    permissions: list[str] | None = None


class PasswordChangeRequest(BaseModel):
    """Password change request schema with complexity requirements."""

    current_password: str
    new_password: str = Field(..., min_length=PASSWORD_MIN_LENGTH)

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, v: str) -> str:
        """Enforce bank-grade password complexity."""
        return validate_password_complexity(v)


class PasswordResetRequest(BaseModel):
    """Password reset request schema."""

    email: EmailStr


class MFASetupResponse(BaseModel):
    """MFA setup response schema."""

    secret: str
    qr_code_uri: str


class MFAVerifyRequest(BaseModel):
    """MFA verification request schema."""

    code: str = Field(..., min_length=6, max_length=6)
