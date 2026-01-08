"""Fraud Intelligence Sharing Module models."""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any

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
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.base import TimestampMixin, UUIDMixin


class FraudType(str, Enum):
    """Types of fraud events."""

    CHECK_KITING = "check_kiting"
    COUNTERFEIT_CHECK = "counterfeit_check"
    FORGED_SIGNATURE = "forged_signature"
    ALTERED_CHECK = "altered_check"
    ACCOUNT_TAKEOVER = "account_takeover"
    IDENTITY_THEFT = "identity_theft"
    FIRST_PARTY_FRAUD = "first_party_fraud"
    SYNTHETIC_IDENTITY = "synthetic_identity"
    DUPLICATE_DEPOSIT = "duplicate_deposit"
    UNAUTHORIZED_ENDORSEMENT = "unauthorized_endorsement"
    PAYEE_ALTERATION = "payee_alteration"
    AMOUNT_ALTERATION = "amount_alteration"
    FICTITIOUS_PAYEE = "fictitious_payee"
    OTHER = "other"


class FraudChannel(str, Enum):
    """Channel where fraud occurred."""

    BRANCH = "branch"
    ATM = "atm"
    MOBILE = "mobile"
    RDC = "rdc"  # Remote Deposit Capture
    MAIL = "mail"
    ONLINE = "online"
    OTHER = "other"


class AmountBucket(str, Enum):
    """Amount buckets for aggregation (privacy preserving)."""

    UNDER_100 = "under_100"
    FROM_100_TO_500 = "100_to_500"
    FROM_500_TO_1000 = "500_to_1000"
    FROM_1000_TO_5000 = "1000_to_5000"
    FROM_5000_TO_10000 = "5000_to_10000"
    FROM_10000_TO_50000 = "10000_to_50000"
    OVER_50000 = "over_50000"


class SharingLevel(int, Enum):
    """Sharing level for fraud events."""

    PRIVATE = 0  # No sharing; stored internally only
    AGGREGATE = 1  # Contributes to anonymized stats
    NETWORK_MATCH = 2  # Hashed indicators can trigger alerts for other tenants


class FraudEventStatus(str, Enum):
    """Status of a fraud event."""

    DRAFT = "draft"
    SUBMITTED = "submitted"
    WITHDRAWN = "withdrawn"


class MatchSeverity(str, Enum):
    """Severity of network match alerts."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


def get_amount_bucket(amount: Decimal) -> AmountBucket:
    """Determine amount bucket for a given amount."""
    if amount < 100:
        return AmountBucket.UNDER_100
    elif amount < 500:
        return AmountBucket.FROM_100_TO_500
    elif amount < 1000:
        return AmountBucket.FROM_500_TO_1000
    elif amount < 5000:
        return AmountBucket.FROM_1000_TO_5000
    elif amount < 10000:
        return AmountBucket.FROM_5000_TO_10000
    elif amount < 50000:
        return AmountBucket.FROM_10000_TO_50000
    else:
        return AmountBucket.OVER_50000


class FraudEvent(Base, UUIDMixin, TimestampMixin):
    """
    Tenant-private fraud event record.

    Contains full details including PII that is never shared directly.
    """

    __tablename__ = "fraud_events"

    # Tenant isolation
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    # Links to check/case (at least one should be set)
    check_item_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("check_items.id", ondelete="SET NULL"),
        index=True
    )
    case_id: Mapped[str | None] = mapped_column(String(36), index=True)  # For future case management

    # Event details
    event_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    amount_bucket: Mapped[AmountBucket] = mapped_column(
        SQLEnum(AmountBucket, name='amount_bucket', values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )

    # Classification
    fraud_type: Mapped[FraudType] = mapped_column(
        SQLEnum(FraudType, name='fraud_type', values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    channel: Mapped[FraudChannel] = mapped_column(
        SQLEnum(FraudChannel, name='fraud_channel', values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    confidence: Mapped[int] = mapped_column(Integer, nullable=False, default=3)  # 1-5 scale

    # Narratives - private narrative is never shared
    narrative_private: Mapped[str | None] = mapped_column(Text)
    # Shareable narrative - only included if explicitly marked safe and admin allows
    narrative_shareable: Mapped[str | None] = mapped_column(Text)

    # Sharing configuration - stored as Integer in DB (0=PRIVATE, 1=AGGREGATE, 2=NETWORK_MATCH)
    sharing_level: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0
    )
    status: Mapped[FraudEventStatus] = mapped_column(
        SQLEnum(FraudEventStatus, name='fraud_event_status', values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=FraudEventStatus.DRAFT
    )

    # Metadata
    created_by_user_id: Mapped[str] = mapped_column(String(36), nullable=False)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    submitted_by_user_id: Mapped[str | None] = mapped_column(String(36))
    withdrawn_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    withdrawn_by_user_id: Mapped[str | None] = mapped_column(String(36))
    withdrawn_reason: Mapped[str | None] = mapped_column(Text)

    # Relationships
    check_item = relationship("CheckItem", back_populates="fraud_events")
    shared_artifact = relationship("FraudSharedArtifact", back_populates="fraud_event", uselist=False)

    __table_args__ = (
        Index("ix_fraud_events_tenant_status", "tenant_id", "status"),
        Index("ix_fraud_events_tenant_type", "tenant_id", "fraud_type"),
        Index("ix_fraud_events_event_date", "event_date"),
    )


class FraudSharedArtifact(Base, UUIDMixin, TimestampMixin):
    """
    Network-shareable artifact derived from a fraud event.

    Contains only hashed indicators and aggregate-safe data.
    Never contains raw PII.
    """

    __tablename__ = "fraud_shared_artifacts"

    # Source tracking (tenant_id stored but never exposed to other tenants)
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    fraud_event_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("fraud_events.id", ondelete="CASCADE"),
        unique=True,
        nullable=True  # Nullable for artifacts from external institutions
    )

    # Sharing level determines how this artifact can be used (Integer: 0=PRIVATE, 1=AGGREGATE, 2=NETWORK_MATCH)
    sharing_level: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    # Time-based (coarsened for privacy)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    occurred_month: Mapped[str] = mapped_column(String(7), nullable=False)  # YYYY-MM format

    # Categorization (safe to share)
    fraud_type: Mapped[FraudType] = mapped_column(
        SQLEnum(FraudType, name='fraud_type', values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    channel: Mapped[FraudChannel] = mapped_column(
        SQLEnum(FraudChannel, name='fraud_channel', values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    amount_bucket: Mapped[AmountBucket] = mapped_column(
        SQLEnum(AmountBucket, name='amount_bucket', values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )

    # Hashed indicators for matching (only populated if sharing_level = 2)
    # JSON structure: {"routing_hash": "...", "payee_hash": "...", "check_fingerprint": "..."}
    indicators_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    # Pepper version for rotation support (allows matching against current + prior pepper)
    pepper_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    # Whether this artifact is active for matching
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    fraud_event = relationship("FraudEvent", back_populates="shared_artifact")

    __table_args__ = (
        Index("ix_fraud_shared_artifacts_active", "is_active", "sharing_level"),
        Index("ix_fraud_shared_artifacts_occurred_month", "occurred_month"),
        Index("ix_fraud_shared_artifacts_fraud_type", "fraud_type"),
    )


class NetworkMatchAlert(Base, UUIDMixin, TimestampMixin):
    """
    Alert generated when a check/case matches network fraud indicators.

    Stored per-tenant, per-check/case. Shows that other institutions
    have reported similar fraud patterns without revealing their identity.
    """

    __tablename__ = "network_match_alerts"

    # The tenant viewing this alert
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    # What this alert is for
    check_item_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("check_items.id", ondelete="CASCADE"),
        index=True
    )
    case_id: Mapped[str | None] = mapped_column(String(36), index=True)

    # Match details - stores artifact IDs that matched (never shown to user directly)
    matched_artifact_ids: Mapped[list[str]] = mapped_column(ARRAY(String(36)), nullable=False)

    # Match reasons (aggregated, safe to show)
    # JSON structure: {"routing_hash": {"count": 3, "first_seen": "2024-01", "last_seen": "2024-06"}, ...}
    match_reasons: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)

    # Severity based on match strength
    severity: Mapped[MatchSeverity] = mapped_column(
        SQLEnum(MatchSeverity, name='match_severity', values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )

    # Match statistics (aggregated, no PII)
    total_matches: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    distinct_institutions: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    earliest_match_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    latest_match_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Dismissal tracking
    dismissed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    dismissed_by_user_id: Mapped[str | None] = mapped_column(String(36))
    dismissed_reason: Mapped[str | None] = mapped_column(Text)

    # Status
    last_checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Relationship
    check_item = relationship("CheckItem", back_populates="network_alerts")

    __table_args__ = (
        Index("ix_network_match_alerts_tenant_check", "tenant_id", "check_item_id"),
        Index("ix_network_match_alerts_severity", "severity", "dismissed_at"),
    )


class TenantFraudConfig(Base, UUIDMixin, TimestampMixin):
    """
    Tenant-level configuration for fraud intelligence sharing.
    """

    __tablename__ = "tenant_fraud_configs"

    tenant_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False, index=True)

    # Default sharing level for new fraud event submissions (Integer: 0=PRIVATE, 1=AGGREGATE, 2=NETWORK_MATCH)
    default_sharing_level: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0
    )

    # Whether shareable narratives are allowed at all
    allow_narrative_sharing: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Whether to hash and share account-related indicators (higher risk)
    allow_account_indicator_sharing: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Data retention in months for shared artifacts
    shared_artifact_retention_months: Mapped[int] = mapped_column(Integer, default=24, nullable=False)

    # Whether this tenant wants to receive network match alerts
    receive_network_alerts: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Minimum match severity to alert on
    minimum_alert_severity: Mapped[MatchSeverity] = mapped_column(
        SQLEnum(MatchSeverity, name='match_severity', values_callable=lambda x: [e.value for e in x]),
        default=MatchSeverity.LOW,
        nullable=False
    )

    # Admin who last modified
    last_modified_by_user_id: Mapped[str | None] = mapped_column(String(36))
