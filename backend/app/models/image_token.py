"""One-time image access token model.

This model implements secure, one-time-use, tenant-aware image access tokens
that replace JWT-based bearer tokens in URLs.

Security Properties:
- One-time use: Token is marked as used immediately when consumed
- Tenant-aware: Token validates image belongs to same tenant
- Short-lived: Tokens expire after configurable TTL
- Auditable: Full audit trail of who created and used tokens
- No JWT in URL: Token is an opaque UUID, not a decodable JWT
"""

from datetime import datetime, timezone

from app.db.session import Base
from app.models.base import TimestampMixin, UUIDMixin
from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship


class ImageAccessToken(Base, UUIDMixin, TimestampMixin):
    """One-time image access token.

    This table stores tokens that grant temporary, single-use access to
    check images. Tokens are:
    - Tenant-scoped: Can only access images belonging to the same tenant
    - One-time-use: Marked as used when consumed, cannot be reused
    - Time-limited: Expire after configurable TTL
    - Auditable: Track who created and consumed the token

    Security Model:
    - Token ID is a random UUID (not a JWT) - no information leakage
    - Token can only be used once (used_at is set atomically on consumption)
    - Token validates tenant ownership of the image
    - All access is logged for audit trail
    """

    __tablename__ = "image_access_tokens"

    # Tenant isolation - token can only access images from this tenant
    # Note: Index created by migration (ix_image_access_tokens_tenant_id)
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False)

    # Reference to the check image this token grants access to
    # Note: Index created by migration (ix_image_access_tokens_image_id)
    image_id: Mapped[str] = mapped_column(String(36), ForeignKey("check_images.id"), nullable=False)

    # Token lifecycle
    # Note: Index created by migration (ix_image_access_tokens_expires_at)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Audit trail
    created_by_user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=False
    )

    # Optional: track who consumed the token (for audit)
    used_by_ip: Mapped[str | None] = mapped_column(String(45))  # IPv6 length
    used_by_user_agent: Mapped[str | None] = mapped_column(String(500))

    # Token options
    is_thumbnail: Mapped[bool] = mapped_column(Boolean, default=False)

    # Relationships
    image: Mapped["CheckImage"] = relationship()
    created_by: Mapped["User"] = relationship()

    __table_args__ = (
        # Composite index for finding unused tokens for an image
        # Note: single-column indexes are created via index=True on columns
        Index("ix_image_access_tokens_image_unused", "image_id", "used_at"),
    )

    @property
    def is_expired(self) -> bool:
        """Check if token has expired."""
        return datetime.now(timezone.utc) > self.expires_at

    @property
    def is_used(self) -> bool:
        """Check if token has been used."""
        return self.used_at is not None

    @property
    def is_valid(self) -> bool:
        """Check if token is valid (not expired and not used)."""
        return not self.is_expired and not self.is_used


# Import for relationship type hints
from app.models.check import CheckImage  # noqa: E402
from app.models.user import User  # noqa: E402
