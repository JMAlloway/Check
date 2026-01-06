"""Authentication schemas."""

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    """Login request schema."""

    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=8)
    mfa_code: str | None = None


class RefreshTokenRequest(BaseModel):
    """Refresh token request schema."""

    refresh_token: str


class Token(BaseModel):
    """Token response schema."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class LoginUserInfo(BaseModel):
    """User info included in login response."""

    id: str
    username: str
    email: str
    full_name: str | None
    is_superuser: bool
    roles: list[str]
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
    """Password change request schema."""

    current_password: str
    new_password: str = Field(..., min_length=8)


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
