"""User, role, and permission schemas."""

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.schemas.auth import PASSWORD_MIN_LENGTH, validate_password_complexity
from app.schemas.common import BaseSchema, TimestampSchema


class PermissionBase(BaseModel):
    """Permission base schema."""

    name: str
    description: str | None = None
    resource: str
    action: str
    conditions: dict | None = None


class PermissionCreate(PermissionBase):
    """Permission create schema."""

    pass


class PermissionResponse(PermissionBase, TimestampSchema):
    """Permission response schema."""

    id: str


class RoleBase(BaseModel):
    """Role base schema."""

    name: str = Field(..., min_length=2, max_length=50)
    description: str | None = None


class RoleCreate(RoleBase):
    """Role create schema."""

    permission_ids: list[str] = []


class RoleUpdate(BaseModel):
    """Role update schema."""

    name: str | None = None
    description: str | None = None
    permission_ids: list[str] | None = None


class RoleResponse(RoleBase, TimestampSchema):
    """Role response schema."""

    id: str
    is_system: bool
    permissions: list[PermissionResponse] = []


class UserBase(BaseModel):
    """User base schema."""

    email: EmailStr
    username: str = Field(..., min_length=3, max_length=50)
    full_name: str = Field(..., min_length=1, max_length=100)
    department: str | None = None
    branch: str | None = None
    employee_id: str | None = None


class UserCreate(UserBase):
    """User create schema with password complexity requirements."""

    password: str = Field(..., min_length=PASSWORD_MIN_LENGTH)
    role_ids: list[str] = []
    is_active: bool = True

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        """Enforce bank-grade password complexity."""
        return validate_password_complexity(v)


class UserUpdate(BaseModel):
    """User update schema."""

    email: EmailStr | None = None
    full_name: str | None = None
    department: str | None = None
    branch: str | None = None
    employee_id: str | None = None
    is_active: bool | None = None
    role_ids: list[str] | None = None
    allowed_ips: list[str] | None = None


class UserResponse(UserBase, TimestampSchema):
    """User response schema."""

    id: str
    is_active: bool
    is_superuser: bool
    mfa_enabled: bool
    last_login: datetime | None = None
    roles: list[RoleResponse] = []


class UserListResponse(BaseSchema):
    """User list response schema."""

    id: str
    email: str
    username: str
    full_name: str
    is_active: bool
    department: str | None = None
    roles: list[str] = []  # Just role names for list view
    last_login: datetime | None = None


class CurrentUserResponse(UserResponse):
    """Current user response with additional session info."""

    permissions: list[str] = []  # Flattened list of permission names
    session_expires_at: datetime | None = None
