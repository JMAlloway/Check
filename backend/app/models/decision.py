"""Decision and reason code models."""

from datetime import datetime
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
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship


class DecisionType(str, Enum):
    """Type of decision."""

    REVIEW_RECOMMENDATION = "review_recommendation"
    APPROVAL_DECISION = "approval_decision"
    ESCALATION = "escalation"


class DecisionAction(str, Enum):
    """Decision action."""

    APPROVE = "approve"
    RETURN = "return"
    REJECT = "reject"
    HOLD = "hold"
    ESCALATE = "escalate"
    NEEDS_MORE_INFO = "needs_more_info"


class ReasonCode(Base, UUIDMixin, TimestampMixin):
    """Configurable reason codes for decisions."""

    __tablename__ = "reason_codes"

    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # e.g., "signature", "amount", "fraud"
    decision_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # "return", "reject", "escalate"
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    display_order: Mapped[int] = mapped_column(Integer, default=0)
    requires_notes: Mapped[bool] = mapped_column(Boolean, default=False)


class Decision(Base, UUIDMixin, TimestampMixin):
    """Decision record for a check item."""

    __tablename__ = "decisions"

    # Tenant isolation - CRITICAL for multi-tenant security
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    check_item_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("check_items.id"), nullable=False
    )
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)

    decision_type: Mapped[DecisionType] = mapped_column(
        SQLEnum(DecisionType, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    action: Mapped[DecisionAction] = mapped_column(
        SQLEnum(DecisionAction, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )

    # Reason codes (can have multiple)
    reason_codes: Mapped[str | None] = mapped_column(Text)  # JSON array of reason code IDs
    notes: Mapped[str | None] = mapped_column(Text)

    # AI assist info
    ai_assisted: Mapped[bool] = mapped_column(Boolean, default=False)
    ai_flags_reviewed: Mapped[str | None] = mapped_column(
        Text
    )  # JSON array of AI flags user reviewed

    # Attachments
    attachments: Mapped[str | None] = mapped_column(Text)  # JSON array of attachment references

    # Policy tracking
    policy_version_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("policy_versions.id")
    )

    # Workflow tracking
    previous_status: Mapped[str | None] = mapped_column(String(50))
    new_status: Mapped[str | None] = mapped_column(String(50))

    # Dual control
    is_dual_control_required: Mapped[bool] = mapped_column(Boolean, default=False)
    dual_control_approver_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"))
    dual_control_approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Evidence Snapshot - CRITICAL for bank-grade audit replay
    # Captures the exact state at decision time:
    # - policy_evaluation: rules triggered, outputs, version
    # - ai_context: model/version, features displayed, risk score
    # - check_context: amount, balances, tenure, risk flags (frozen values)
    # - image_refs: image IDs/hashes for reproducibility
    # - displayed_flags: exact flags shown to reviewer
    evidence_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    # Demo mode flag - marks synthetic demo decisions
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)

    # Explicit foreign_keys needed due to bidirectional FK with check_items.pending_dual_control_decision_id
    check_item: Mapped["CheckItem"] = relationship(
        back_populates="decisions",
        foreign_keys=[check_item_id],
    )
    user: Mapped["User"] = relationship(foreign_keys=[user_id])
    dual_control_approver: Mapped["User"] = relationship(foreign_keys=[dual_control_approver_id])


# Import for type hints
from app.models.check import CheckItem  # noqa: E402
from app.models.user import User  # noqa: E402
