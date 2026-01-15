"""Policy engine models."""

from datetime import datetime
from decimal import Decimal
from enum import Enum

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.base import TimestampMixin, UUIDMixin


class PolicyStatus(str, Enum):
    """Policy status."""

    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"


class RuleType(str, Enum):
    """Type of policy rule."""

    THRESHOLD = "threshold"
    DUAL_CONTROL = "dual_control"
    ESCALATION = "escalation"
    ROUTING = "routing"
    REQUIRE_REASON = "require_reason"


class RuleConditionOperator(str, Enum):
    """Operators for rule conditions."""

    EQUALS = "equals"
    NOT_EQUALS = "not_equals"
    GREATER_THAN = "greater_than"
    LESS_THAN = "less_than"
    GREATER_OR_EQUAL = "greater_or_equal"
    LESS_OR_EQUAL = "less_or_equal"
    IN = "in"
    NOT_IN = "not_in"
    CONTAINS = "contains"
    BETWEEN = "between"


class Policy(Base, UUIDMixin, TimestampMixin):
    """Policy definition.

    Multi-tenant: Each policy belongs to a single tenant.
    The tenant_id column ensures strict data isolation.
    """

    __tablename__ = "policies"

    # CRITICAL: tenant_id for multi-tenant isolation
    # Every policy query MUST filter by tenant_id
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[PolicyStatus] = mapped_column(
        SQLEnum(PolicyStatus, values_callable=lambda x: [e.value for e in x]),
        default=PolicyStatus.DRAFT,
        nullable=False,
    )
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)

    # Scope
    applies_to_account_types: Mapped[str | None] = mapped_column(Text)  # JSON array
    applies_to_branches: Mapped[str | None] = mapped_column(Text)  # JSON array
    applies_to_markets: Mapped[str | None] = mapped_column(Text)  # JSON array

    versions: Mapped[list["PolicyVersion"]] = relationship(
        back_populates="policy",
        cascade="all, delete-orphan",
    )


class PolicyVersion(Base, UUIDMixin, TimestampMixin):
    """Versioned policy for audit trail."""

    __tablename__ = "policy_versions"

    policy_id: Mapped[str] = mapped_column(String(36), ForeignKey("policies.id"), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    effective_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expiry_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_current: Mapped[bool] = mapped_column(Boolean, default=False)

    # Snapshot of rules at this version (JSON for full audit trail)
    rules_snapshot: Mapped[str | None] = mapped_column(Text)  # JSON serialization of rules

    # Approval
    approved_by_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    change_notes: Mapped[str | None] = mapped_column(Text)

    policy: Mapped[Policy] = relationship(back_populates="versions")
    rules: Mapped[list["PolicyRule"]] = relationship(
        back_populates="policy_version",
        cascade="all, delete-orphan",
    )


class PolicyRule(Base, UUIDMixin, TimestampMixin):
    """Individual policy rule."""

    __tablename__ = "policy_rules"

    policy_version_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("policy_versions.id"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    rule_type: Mapped[RuleType] = mapped_column(
        SQLEnum(RuleType, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    priority: Mapped[int] = mapped_column(Integer, default=0)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    # Conditions (JSON structure)
    # Example: {"field": "amount", "operator": "greater_than", "value": 5000}
    conditions: Mapped[str] = mapped_column(Text, nullable=False)

    # Actions (JSON structure)
    # Example: {"action": "require_dual_control", "params": {"approver_role": "senior_approver"}}
    actions: Mapped[str] = mapped_column(Text, nullable=False)

    # Thresholds (for quick access)
    amount_threshold: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    risk_level_threshold: Mapped[str | None] = mapped_column(String(20))

    policy_version: Mapped[PolicyVersion] = relationship(back_populates="rules")
