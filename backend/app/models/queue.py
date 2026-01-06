"""Queue and assignment models."""

from datetime import datetime
from enum import Enum

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.base import TimestampMixin, UUIDMixin


class QueueType(str, Enum):
    """Queue type."""

    STANDARD = "standard"
    HIGH_PRIORITY = "high_priority"
    ESCALATION = "escalation"
    SPECIAL_REVIEW = "special_review"


class Queue(Base, UUIDMixin, TimestampMixin):
    """Work queue for check items."""

    __tablename__ = "queues"

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    queue_type: Mapped[QueueType] = mapped_column(
        SQLEnum(QueueType),
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


# Import for type hints
from app.models.user import User  # noqa: E402
