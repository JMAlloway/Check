"""User, Role, and Permission models."""

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Table, Text, UniqueConstraint, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.base import TimestampMixin, UUIDMixin


# Association tables for many-to-many relationships
user_roles = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", String(36), ForeignKey("users.id"), primary_key=True),
    Column("role_id", String(36), ForeignKey("roles.id"), primary_key=True),
)

role_permissions = Table(
    "role_permissions",
    Base.metadata,
    Column("role_id", String(36), ForeignKey("roles.id"), primary_key=True),
    Column("permission_id", String(36), ForeignKey("permissions.id"), primary_key=True),
)


class Permission(Base, UUIDMixin, TimestampMixin):
    """Permission model for granular access control."""

    __tablename__ = "permissions"

    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    resource: Mapped[str] = mapped_column(String(50), nullable=False)  # e.g., "check_item", "queue"
    action: Mapped[str] = mapped_column(String(50), nullable=False)  # e.g., "view", "approve", "export"
    conditions: Mapped[str | None] = mapped_column(Text)  # JSON conditions like {"amount_max": 10000}

    roles: Mapped[list["Role"]] = relationship(
        secondary=role_permissions,
        back_populates="permissions",
    )


class Role(Base, UUIDMixin, TimestampMixin):
    """Role model for RBAC."""

    __tablename__ = "roles"

    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False)  # System roles cannot be deleted

    permissions: Mapped[list[Permission]] = relationship(
        secondary=role_permissions,
        back_populates="roles",
    )
    users: Mapped[list["User"]] = relationship(
        secondary=user_roles,
        back_populates="roles",
    )


class User(Base, UUIDMixin, TimestampMixin):
    """User model."""

    __tablename__ = "users"

    # Tenant-scoped unique constraints for email and username
    # Users are unique WITHIN a tenant, not globally
    __table_args__ = (
        UniqueConstraint("tenant_id", "email", name="uq_users_tenant_email"),
        UniqueConstraint("tenant_id", "username", name="uq_users_tenant_username"),
        Index("ix_users_tenant_email", "tenant_id", "email"),
        Index("ix_users_tenant_username", "tenant_id", "username"),
    )

    # Multi-tenant support
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    # Note: unique=False here - uniqueness enforced by composite constraint above
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    username: Mapped[str] = mapped_column(String(50), nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(100), nullable=False)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False)
    mfa_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    mfa_secret: Mapped[str | None] = mapped_column(String(255))

    # Organization/team
    department: Mapped[str | None] = mapped_column(String(100))
    branch: Mapped[str | None] = mapped_column(String(100))
    employee_id: Mapped[str | None] = mapped_column(String(50))

    # Security
    last_login: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failed_login_attempts: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    password_changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # IP restrictions - JSONB array of allowed IP addresses/CIDRs
    allowed_ips: Mapped[list[str] | None] = mapped_column(JSONB)

    # Demo mode flag - marks synthetic demo users
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)

    roles: Mapped[list[Role]] = relationship(
        secondary=user_roles,
        back_populates="users",
    )
    sessions: Mapped[list["UserSession"]] = relationship(back_populates="user")

    def has_permission(self, resource: str, action: str) -> bool:
        """Check if user has a specific permission."""
        if self.is_superuser:
            return True
        for role in self.roles:
            for permission in role.permissions:
                if permission.resource == resource and permission.action == action:
                    return True
        return False

    def has_role(self, role_name: str) -> bool:
        """Check if user has a specific role."""
        return any(role.name == role_name for role in self.roles)


class UserSession(Base, UUIDMixin, TimestampMixin):
    """User session tracking for security and audit."""

    __tablename__ = "user_sessions"

    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    ip_address: Mapped[str | None] = mapped_column(String(45))
    user_agent: Mapped[str | None] = mapped_column(Text)
    device_fingerprint: Mapped[str | None] = mapped_column(String(255))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped[User] = relationship(back_populates="sessions")
