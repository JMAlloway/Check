"""Check item and image models."""

from datetime import datetime
from decimal import Decimal
from enum import Enum

from sqlalchemy import (
    Boolean,
    DateTime,
)
from sqlalchemy import Enum as SQLEnum
from sqlalchemy import (
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.base import TimestampMixin, UUIDMixin


class CheckStatus(str, Enum):
    """
    Check item workflow status.

    Workflow:
    1. NEW -> IN_REVIEW (assigned to reviewer)
    2. IN_REVIEW -> PENDING_DUAL_CONTROL (reviewer makes recommendation, awaits approval)
                 -> APPROVED/REJECTED/RETURNED (if no dual control required)
                 -> ESCALATED (needs senior review)
    3. PENDING_DUAL_CONTROL -> APPROVED/REJECTED/RETURNED (approver decides)
                            -> ESCALATED (approver escalates)
    4. ESCALATED -> PENDING_DUAL_CONTROL or terminal state
    5. Terminal states: APPROVED, REJECTED, RETURNED, CLOSED
    """

    NEW = "new"
    IN_REVIEW = "in_review"
    ESCALATED = "escalated"
    PENDING_DUAL_CONTROL = "pending_dual_control"  # Awaiting second-level approval
    PENDING_APPROVAL = "pending_approval"  # Legacy: use PENDING_DUAL_CONTROL
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


class ItemType(str, Enum):
    """
    Check item type - critical for processing workflow.

    ON_US: Check drawn on our bank's customer account.
           The maker (writer) is our customer. We are the paying bank.
           Example: Our customer writes a check that gets deposited elsewhere.

    TRANSIT: Check from another bank being deposited into our customer's account.
             The depositor is our customer. We are the collecting bank.
             Example: Our customer deposits a check from another bank.
    """

    ON_US = "on_us"
    TRANSIT = "transit"


class CheckItem(Base, UUIDMixin, TimestampMixin):
    """Check item presented for review."""

    __tablename__ = "check_items"

    # Tenant isolation
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    # External identifiers (unique per tenant, not globally)
    external_item_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    source_system: Mapped[str] = mapped_column(String(50), nullable=False)  # e.g., "q2", "fiserv"

    # Item type - critical for processing workflow
    item_type: Mapped[ItemType] = mapped_column(
        SQLEnum(ItemType, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=ItemType.TRANSIT,
        index=True,
        comment="on_us=check drawn on our customer, transit=check deposited by our customer",
    )

    # Account information
    account_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    account_number_masked: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # e.g., "****1234"
    account_type: Mapped[AccountType] = mapped_column(
        SQLEnum(AccountType, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
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
    presented_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    check_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    process_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Workflow
    status: Mapped[CheckStatus] = mapped_column(
        SQLEnum(CheckStatus, values_callable=lambda x: [e.value for e in x]),
        default=CheckStatus.NEW,
        nullable=False,
        index=True,
    )
    risk_level: Mapped[RiskLevel] = mapped_column(
        SQLEnum(RiskLevel, values_callable=lambda x: [e.value for e in x]),
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

    # Dual control tracking
    requires_dual_control: Mapped[bool] = mapped_column(Boolean, default=False)
    pending_dual_control_decision_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("decisions.id"),
        nullable=True,
        index=True,
    )
    dual_control_reason: Mapped[str | None] = mapped_column(
        String(100)
    )  # e.g., "amount_threshold", "policy_rule"

    # Flags and context
    has_ai_flags: Mapped[bool] = mapped_column(Boolean, default=False)
    ai_risk_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    risk_flags: Mapped[str | None] = mapped_column(Text)  # JSON array of flag codes
    upstream_flags: Mapped[str | None] = mapped_column(Text)  # Flags from source system

    # AI Analysis Tracking - ADVISORY ONLY
    # CRITICAL: AI output is NEVER authoritative. These fields track AI analysis
    # for audit purposes. Decisions are always made by humans.
    ai_model_id: Mapped[str | None] = mapped_column(String(100))  # e.g., "check-risk-analyzer"
    ai_model_version: Mapped[str | None] = mapped_column(String(50))  # e.g., "1.0.0"
    ai_analyzed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ai_recommendation: Mapped[str | None] = mapped_column(
        String(50)
    )  # ADVISORY: "likely_legitimate", "needs_review", etc.
    ai_confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))  # 0.0000 to 1.0000
    ai_explanation: Mapped[str | None] = mapped_column(Text)  # Human-readable explanation
    ai_risk_factors: Mapped[str | None] = mapped_column(Text)  # JSON array of risk factors

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

    # Enhanced account context for comprehensive policy rules
    # Overdraft history (separate from generic returns)
    overdraft_count_30d: Mapped[int | None] = mapped_column(Integer)
    overdraft_count_90d: Mapped[int | None] = mapped_column(Integer)
    nsf_count_90d: Mapped[int | None] = mapped_column(Integer)  # Non-sufficient funds
    last_overdraft_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Transaction velocity (more granular windows)
    check_count_7d: Mapped[int | None] = mapped_column(Integer)
    check_count_14d: Mapped[int | None] = mapped_column(Integer)
    total_check_amount_7d: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    total_check_amount_14d: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))

    # Customer/relationship context
    relationship_tenure_years: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    is_payroll_account: Mapped[bool | None] = mapped_column(Boolean)
    has_direct_deposit: Mapped[bool | None] = mapped_column(Boolean)
    deposit_regularity_score: Mapped[int | None] = mapped_column(Integer)  # 0-100

    # Check number sequence tracking
    last_check_number_used: Mapped[int | None] = mapped_column(Integer)
    check_number_gap: Mapped[int | None] = mapped_column(Integer)  # Gap from last used
    is_duplicate_check_number: Mapped[bool | None] = mapped_column(Boolean)
    is_out_of_sequence: Mapped[bool | None] = mapped_column(Boolean)

    # Check age/staleness
    check_age_days: Mapped[int | None] = mapped_column(Integer)  # Days since check_date
    is_stale_dated: Mapped[bool | None] = mapped_column(Boolean)  # > 180 days old
    is_post_dated: Mapped[bool | None] = mapped_column(Boolean)  # Future dated

    # Image quality and alteration signals
    has_micr_anomaly: Mapped[bool | None] = mapped_column(Boolean)
    micr_confidence_score: Mapped[int | None] = mapped_column(Integer)  # 0-100
    has_alteration_flag: Mapped[bool | None] = mapped_column(Boolean)
    signature_match_score: Mapped[int | None] = mapped_column(Integer)  # 0-100

    # Prior review history
    prior_review_count: Mapped[int | None] = mapped_column(Integer)  # Times account reviewed
    prior_approval_count: Mapped[int | None] = mapped_column(Integer)
    prior_rejection_count: Mapped[int | None] = mapped_column(Integer)
    last_review_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Policy tracking
    policy_version_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("policy_versions.id")
    )

    # Demo mode flag - marks synthetic demo data
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, index=True)

    # Relationships
    images: Mapped[list["CheckImage"]] = relationship(
        back_populates="check_item", cascade="all, delete-orphan"
    )
    decisions: Mapped[list["Decision"]] = relationship(
        back_populates="check_item",
        cascade="all, delete-orphan",
        foreign_keys="[Decision.check_item_id]",
    )
    pending_dual_control_decision: Mapped["Decision | None"] = relationship(
        foreign_keys=[pending_dual_control_decision_id],
        post_update=True,  # Avoids circular dependency on insert
    )
    assigned_reviewer: Mapped["User"] = relationship(foreign_keys=[assigned_reviewer_id])
    assigned_approver: Mapped["User"] = relationship(foreign_keys=[assigned_approver_id])
    fraud_events: Mapped[list["FraudEvent"]] = relationship(back_populates="check_item")
    network_alerts: Mapped[list["NetworkMatchAlert"]] = relationship(
        back_populates="check_item", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_check_items_status_priority", "status", "priority"),
        Index("ix_check_items_queue_status", "queue_id", "status"),
        # Per-tenant uniqueness for external IDs (Bank A and Bank B can have same external_item_id)
        UniqueConstraint("tenant_id", "external_item_id", name="uq_check_items_tenant_external_id"),
        # Note: presented_date index is created via index=True on the column
    )


class CheckImage(Base, UUIDMixin, TimestampMixin):
    """Check image storage reference."""

    __tablename__ = "check_images"

    check_item_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("check_items.id"), nullable=False
    )
    image_type: Mapped[str] = mapped_column(String(20), nullable=False)  # "front", "back"
    external_image_id: Mapped[str | None] = mapped_column(
        String(100)
    )  # Reference to external storage
    storage_path: Mapped[str | None] = mapped_column(String(500))  # Local/cloud storage path
    content_type: Mapped[str] = mapped_column(String(50), default="image/tiff")
    file_size: Mapped[int | None] = mapped_column(Integer)
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    dpi: Mapped[int | None] = mapped_column(Integer)
    thumbnail_path: Mapped[str | None] = mapped_column(String(500))

    # Demo mode flag
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)

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

    # Demo mode flag
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)

    __table_args__ = (Index("ix_check_history_account_date", "account_id", "check_date"),)


# Import for relationship
from app.models.decision import Decision  # noqa: E402
from app.models.fraud import FraudEvent, NetworkMatchAlert  # noqa: E402
from app.models.user import User  # noqa: E402
