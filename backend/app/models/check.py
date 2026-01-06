"""Check item and image models."""

from datetime import datetime
from decimal import Decimal
from enum import Enum

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.base import TimestampMixin, UUIDMixin


class CheckStatus(str, Enum):
    """Check item workflow status."""

    NEW = "new"
    IN_REVIEW = "in_review"
    ESCALATED = "escalated"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    RETURNED = "returned"
    CLOSED = "closed"


class RiskLevel(str, Enum):
    """Risk level classification."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AccountType(str, Enum):
    """Account type classification."""

    CONSUMER = "consumer"
    BUSINESS = "business"
    COMMERCIAL = "commercial"
    NON_PROFIT = "non_profit"


class CheckItem(Base, UUIDMixin, TimestampMixin):
    """Check item presented for review."""

    __tablename__ = "check_items"

    # External identifiers
    external_item_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    source_system: Mapped[str] = mapped_column(String(50), nullable=False)  # e.g., "q2", "fiserv"

    # Account information
    account_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    account_number_masked: Mapped[str] = mapped_column(String(20), nullable=False)  # e.g., "****1234"
    account_type: Mapped[AccountType] = mapped_column(SQLEnum(AccountType), nullable=False)
    routing_number: Mapped[str | None] = mapped_column(String(9))

    # Check details
    check_number: Mapped[str | None] = mapped_column(String(20))
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, index=True)
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    payee_name: Mapped[str | None] = mapped_column(String(255))
    memo: Mapped[str | None] = mapped_column(String(255))

    # MICR data
    micr_line: Mapped[str | None] = mapped_column(String(100))
    micr_account: Mapped[str | None] = mapped_column(String(20))
    micr_routing: Mapped[str | None] = mapped_column(String(9))
    micr_check_number: Mapped[str | None] = mapped_column(String(20))

    # Dates
    presented_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    check_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    process_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Workflow
    status: Mapped[CheckStatus] = mapped_column(
        SQLEnum(CheckStatus),
        default=CheckStatus.NEW,
        nullable=False,
        index=True,
    )
    risk_level: Mapped[RiskLevel] = mapped_column(
        SQLEnum(RiskLevel),
        default=RiskLevel.LOW,
        nullable=False,
        index=True,
    )
    priority: Mapped[int] = mapped_column(Integer, default=0, index=True)

    # Assignments
    assigned_reviewer_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"))
    assigned_approver_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"))
    queue_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("queues.id"))

    # SLA tracking
    sla_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sla_breached: Mapped[bool] = mapped_column(Boolean, default=False)

    # Flags and context
    requires_dual_control: Mapped[bool] = mapped_column(Boolean, default=False)
    has_ai_flags: Mapped[bool] = mapped_column(Boolean, default=False)
    ai_risk_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    risk_flags: Mapped[str | None] = mapped_column(Text)  # JSON array of flag codes
    upstream_flags: Mapped[str | None] = mapped_column(Text)  # Flags from source system

    # Account context (denormalized for performance)
    account_tenure_days: Mapped[int | None] = mapped_column(Integer)
    current_balance: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    average_balance_30d: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    avg_check_amount_30d: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    avg_check_amount_90d: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    avg_check_amount_365d: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    check_std_dev_30d: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    max_check_amount_90d: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    check_frequency_30d: Mapped[int | None] = mapped_column(Integer)
    returned_item_count_90d: Mapped[int | None] = mapped_column(Integer)
    exception_count_90d: Mapped[int | None] = mapped_column(Integer)
    relationship_id: Mapped[str | None] = mapped_column(String(50))

    # Policy tracking
    policy_version_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("policy_versions.id"))

    # Relationships
    images: Mapped[list["CheckImage"]] = relationship(back_populates="check_item", cascade="all, delete-orphan")
    decisions: Mapped[list["Decision"]] = relationship(back_populates="check_item", cascade="all, delete-orphan")
    assigned_reviewer: Mapped["User"] = relationship(foreign_keys=[assigned_reviewer_id])
    assigned_approver: Mapped["User"] = relationship(foreign_keys=[assigned_approver_id])

    __table_args__ = (
        Index("ix_check_items_status_priority", "status", "priority"),
        Index("ix_check_items_queue_status", "queue_id", "status"),
        Index("ix_check_items_presented_date", "presented_date"),
    )


class CheckImage(Base, UUIDMixin, TimestampMixin):
    """Check image storage reference."""

    __tablename__ = "check_images"

    check_item_id: Mapped[str] = mapped_column(String(36), ForeignKey("check_items.id"), nullable=False)
    image_type: Mapped[str] = mapped_column(String(20), nullable=False)  # "front", "back"
    external_image_id: Mapped[str | None] = mapped_column(String(100))  # Reference to external storage
    storage_path: Mapped[str | None] = mapped_column(String(500))  # Local/cloud storage path
    content_type: Mapped[str] = mapped_column(String(50), default="image/tiff")
    file_size: Mapped[int | None] = mapped_column(Integer)
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    dpi: Mapped[int | None] = mapped_column(Integer)
    thumbnail_path: Mapped[str | None] = mapped_column(String(500))

    check_item: Mapped[CheckItem] = relationship(back_populates="images")


class CheckHistory(Base, UUIDMixin, TimestampMixin):
    """Historical check data for comparison."""

    __tablename__ = "check_history"

    account_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    check_number: Mapped[str | None] = mapped_column(String(20))
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    check_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    payee_name: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # "cleared", "returned", etc.
    return_reason: Mapped[str | None] = mapped_column(String(100))
    external_item_id: Mapped[str | None] = mapped_column(String(100))
    front_image_ref: Mapped[str | None] = mapped_column(String(255))
    back_image_ref: Mapped[str | None] = mapped_column(String(255))
    signature_hash: Mapped[str | None] = mapped_column(String(64))  # For similarity comparison
    check_stock_hash: Mapped[str | None] = mapped_column(String(64))  # For stock comparison

    __table_args__ = (
        Index("ix_check_history_account_date", "account_id", "check_date"),
    )


# Import for relationship
from app.models.decision import Decision  # noqa: E402
from app.models.user import User  # noqa: E402
