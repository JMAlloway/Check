"""Queue and assignment models."""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from app.db.session import Base
from app.models.base import TimestampMixin, UUIDMixin
from sqlalchemy import (
    Boolean,
    DateTime,
)
from sqlalchemy import Enum as SQLEnum
from sqlalchemy import (
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship


class QueueType(str, Enum):
    """Queue type."""

    STANDARD = "standard"
    HIGH_PRIORITY = "high_priority"
    ESCALATION = "escalation"
    SPECIAL_REVIEW = "special_review"


class Queue(Base, UUIDMixin, TimestampMixin):
    """Work queue for check items."""

    __tablename__ = "queues"

    # Tenant isolation - CRITICAL for multi-tenant security
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    queue_type: Mapped[QueueType] = mapped_column(
        SQLEnum(QueueType, values_callable=lambda x: [e.value for e in x]),
        default=QueueType.STANDARD,
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    display_order: Mapped[int] = mapped_column(Integer, default=0)

    # SLA settings
    sla_hours: Mapped[int] = mapped_column(Integer, default=4)
    warning_threshold_minutes: Mapped[int] = mapped_column(Integer, default=30)

    # Routing criteria (JSON)
    routing_criteria: Mapped[str | None] = mapped_column(Text)

    # Access control
    allowed_roles: Mapped[str | None] = mapped_column(Text)  # JSON array of role IDs
    allowed_users: Mapped[str | None] = mapped_column(Text)  # JSON array of user IDs

    # Stats (denormalized for performance)
    current_item_count: Mapped[int] = mapped_column(Integer, default=0)
    items_processed_today: Mapped[int] = mapped_column(Integer, default=0)

    # Demo mode flag - marks synthetic demo queues
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)

    assignments: Mapped[list["QueueAssignment"]] = relationship(
        back_populates="queue",
        cascade="all, delete-orphan",
    )


class QueueAssignment(Base, UUIDMixin, TimestampMixin):
    """User assignment to queues."""

    __tablename__ = "queue_assignments"

    queue_id: Mapped[str] = mapped_column(String(36), ForeignKey("queues.id"), nullable=False)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    can_review: Mapped[bool] = mapped_column(Boolean, default=True)
    can_approve: Mapped[bool] = mapped_column(Boolean, default=False)
    max_concurrent_items: Mapped[int] = mapped_column(Integer, default=10)
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    assigned_by_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"))

    queue: Mapped[Queue] = relationship(back_populates="assignments")
    user: Mapped["User"] = relationship(foreign_keys=[user_id])


class ApprovalEntitlementType(str, Enum):
    """Type of approval entitlement."""

    REVIEW = "review"  # Can make review recommendations
    APPROVE = "approve"  # Can approve (dual control second level)
    OVERRIDE = "override"  # Can override policy (requires justification)


class ApprovalEntitlement(Base, UUIDMixin, TimestampMixin):
    """
    Approval entitlement defining what a user/role can approve.

    This enables fine-grained control over who can approve what:
    - Amount thresholds (min/max)
    - Account types
    - Queue restrictions
    - Business lines

    AUDIT: All entitlement changes should be logged. Entitlements are
    checked at decision time and recorded in evidence_snapshot.
    """

    __tablename__ = "approval_entitlements"

    # Who has this entitlement
    user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    role_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("roles.id"), index=True)

    # Type of entitlement
    entitlement_type: Mapped[ApprovalEntitlementType] = mapped_column(
        SQLEnum(ApprovalEntitlementType, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )

    # Amount limits (NULL = no limit)
    min_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    max_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))

    # Scope restrictions (NULL = all allowed)
    # JSON arrays for flexible filtering
    allowed_account_types: Mapped[list[str] | None] = mapped_column(
        JSONB
    )  # ["consumer", "business"]
    allowed_queue_ids: Mapped[list[str] | None] = mapped_column(JSONB)  # Specific queues
    allowed_risk_levels: Mapped[list[str] | None] = mapped_column(
        JSONB
    )  # ["low", "medium", "high"]

    # Business line / tenant restrictions
    allowed_business_lines: Mapped[list[str] | None] = mapped_column(JSONB)
    tenant_id: Mapped[str | None] = mapped_column(String(36), index=True)

    # Additional conditions (flexible rules)
    conditions: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    effective_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Audit
    granted_by_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"))
    grant_reason: Mapped[str | None] = mapped_column(Text)

    # Relationships
    user: Mapped["User | None"] = relationship(foreign_keys=[user_id])
    role: Mapped["Role | None"] = relationship()
    granted_by: Mapped["User | None"] = relationship(foreign_keys=[granted_by_id])


# Import for type hints
from app.models.user import Role, User  # noqa: E402
