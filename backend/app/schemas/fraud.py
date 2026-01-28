"""Pydantic schemas for Fraud Intelligence Sharing Module."""

from datetime import datetime
from decimal import Decimal
from typing import Any

from app.models.fraud import (
    AmountBucket,
    FraudChannel,
    FraudEventStatus,
    FraudType,
    MatchSeverity,
    SharingLevel,
)
from pydantic import BaseModel, Field, field_validator

# ============================================================================
# Fraud Event Schemas
# ============================================================================


class FraudEventCreate(BaseModel):
    """Schema for creating a new fraud event."""

    check_item_id: str | None = None
    case_id: str | None = None
    event_date: datetime
    amount: Decimal = Field(..., ge=0)
    fraud_type: FraudType
    channel: FraudChannel
    confidence: int = Field(default=3, ge=1, le=5)
    narrative_private: str | None = None
    narrative_shareable: str | None = None
    sharing_level: SharingLevel = SharingLevel.PRIVATE

    @field_validator("narrative_shareable")
    @classmethod
    def validate_shareable_narrative(cls, v: str | None) -> str | None:
        """Warn about potential PII in shareable narrative."""
        # Actual PII detection is done in the service layer
        return v


class FraudEventUpdate(BaseModel):
    """Schema for updating a fraud event (draft only)."""

    event_date: datetime | None = None
    amount: Decimal | None = Field(default=None, ge=0)
    fraud_type: FraudType | None = None
    channel: FraudChannel | None = None
    confidence: int | None = Field(default=None, ge=1, le=5)
    narrative_private: str | None = None
    narrative_shareable: str | None = None
    sharing_level: SharingLevel | None = None


class FraudEventSubmit(BaseModel):
    """Schema for submitting a fraud event."""

    # Optional override of sharing level at submission time
    sharing_level: SharingLevel | None = None
    # User confirms no PII in shareable narrative
    confirm_no_pii: bool = False


class FraudEventWithdraw(BaseModel):
    """Schema for withdrawing a fraud event."""

    reason: str = Field(..., min_length=10, max_length=500)


class FraudEventResponse(BaseModel):
    """Schema for fraud event response."""

    id: str
    tenant_id: str
    check_item_id: str | None
    case_id: str | None
    event_date: datetime
    amount: Decimal
    amount_bucket: AmountBucket
    fraud_type: FraudType
    channel: FraudChannel
    confidence: int
    narrative_private: str | None
    narrative_shareable: str | None
    sharing_level: int  # Stored as integer (0=PRIVATE, 1=AGGREGATE, 2=NETWORK_MATCH)
    status: FraudEventStatus
    created_by_user_id: str
    created_at: datetime
    updated_at: datetime
    submitted_at: datetime | None
    submitted_by_user_id: str | None
    withdrawn_at: datetime | None
    withdrawn_by_user_id: str | None
    withdrawn_reason: str | None

    # Whether this event has a shared artifact
    has_shared_artifact: bool = False

    class Config:
        from_attributes = True


class FraudEventListResponse(BaseModel):
    """Schema for list of fraud events."""

    id: str
    check_item_id: str | None
    case_id: str | None
    event_date: datetime
    amount: Decimal
    fraud_type: FraudType
    channel: FraudChannel
    confidence: int
    sharing_level: int  # Stored as integer (0=PRIVATE, 1=AGGREGATE, 2=NETWORK_MATCH)
    status: FraudEventStatus
    created_at: datetime

    class Config:
        from_attributes = True


# ============================================================================
# Network Alert Schemas
# ============================================================================


class MatchReasonDetail(BaseModel):
    """Details about a match reason."""

    indicator_type: str  # "routing_hash", "payee_hash", "check_fingerprint"
    match_count: int
    first_seen: str  # YYYY-MM format
    last_seen: str  # YYYY-MM format
    fraud_types: list[str]  # Types of fraud associated with matches
    channels: list[str]  # Channels associated with matches


class NetworkAlertResponse(BaseModel):
    """Schema for network match alert."""

    id: str
    check_item_id: str | None
    case_id: str | None
    severity: str  # 'low', 'medium', 'high'
    total_matches: int
    total_matches_display: str  # Suppressed if below threshold
    distinct_institutions: int
    distinct_institutions_display: str  # Suppressed if below threshold
    earliest_match_date: datetime | None
    latest_match_date: datetime | None
    match_reasons: list[MatchReasonDetail]
    created_at: datetime
    last_checked_at: datetime
    is_dismissed: bool
    dismissed_at: datetime | None
    dismissed_reason: str | None

    class Config:
        from_attributes = True


class NetworkAlertSummary(BaseModel):
    """Summary of network alerts for a check/case."""

    has_alerts: bool
    total_alerts: int
    highest_severity: str | None  # 'low', 'medium', 'high'
    alerts: list[NetworkAlertResponse]


class NetworkAlertDismiss(BaseModel):
    """Schema for dismissing a network alert."""

    reason: str | None = Field(default=None, max_length=500)


# ============================================================================
# Network Trends Schemas
# ============================================================================


class TrendDataPoint(BaseModel):
    """Single data point in a trend."""

    period: str  # YYYY-MM or YYYY-WW
    count: int
    # If count < threshold, shows "<N" for privacy
    count_display: str


class FraudTrendByType(BaseModel):
    """Fraud events by type over time."""

    fraud_type: FraudType
    your_bank: list[TrendDataPoint]
    network: list[TrendDataPoint]


class FraudTrendByChannel(BaseModel):
    """Fraud events by channel over time."""

    channel: FraudChannel
    your_bank: list[TrendDataPoint]
    network: list[TrendDataPoint]


class FraudTrendByAmountBucket(BaseModel):
    """Fraud events by amount bucket."""

    amount_bucket: AmountBucket
    your_bank_count: int
    your_bank_display: str
    network_count: int
    network_display: str


class NetworkTrendsResponse(BaseModel):
    """Aggregated network trends response."""

    period_start: datetime
    period_end: datetime

    # Summary stats
    your_bank_total: int
    network_total: int

    # By fraud type
    by_type: list[FraudTrendByType]

    # By channel
    by_channel: list[FraudTrendByChannel]

    # By amount bucket
    by_amount: list[FraudTrendByAmountBucket]

    # Privacy threshold used
    privacy_threshold: int


class NetworkTrendsRequest(BaseModel):
    """Request parameters for network trends."""

    range: str = Field(default="6m", pattern=r"^(1m|3m|6m|12m|24m)$")
    granularity: str = Field(default="month", pattern=r"^(week|month|quarter)$")


# ============================================================================
# Tenant Configuration Schemas
# ============================================================================


class TenantFraudConfigResponse(BaseModel):
    """Tenant fraud configuration response."""

    tenant_id: str
    default_sharing_level: int  # Stored as integer (0=PRIVATE, 1=AGGREGATE, 2=NETWORK_MATCH)
    allow_narrative_sharing: bool
    allow_account_indicator_sharing: bool
    shared_artifact_retention_months: int
    receive_network_alerts: bool
    minimum_alert_severity: str  # 'low', 'medium', 'high'
    updated_at: datetime

    class Config:
        from_attributes = True


class TenantFraudConfigUpdate(BaseModel):
    """Schema for updating tenant fraud configuration."""

    default_sharing_level: SharingLevel | None = None
    allow_narrative_sharing: bool | None = None
    allow_account_indicator_sharing: bool | None = None
    shared_artifact_retention_months: int | None = Field(default=None, ge=6, le=84)
    receive_network_alerts: bool | None = None
    minimum_alert_severity: str | None = None  # 'low', 'medium', 'high'


# ============================================================================
# PII Detection Schemas
# ============================================================================


class PIIDetectionResult(BaseModel):
    """Result of PII detection in text."""

    has_potential_pii: bool
    warnings: list[str]
    detected_patterns: list[str]


class PIICheckRequest(BaseModel):
    """Request to check text for PII."""

    text: str
    strict: bool = False  # If true, more aggressive detection


# ============================================================================
# Shared Artifact Schemas (internal use)
# ============================================================================


class SharedArtifactIndicators(BaseModel):
    """Hashed indicators stored in shared artifact."""

    routing_hash: str | None = None
    payee_hash: str | None = None
    check_fingerprint: str | None = None
    # Additional optional indicators
    micr_routing_hash: str | None = None


class SharedArtifactResponse(BaseModel):
    """Internal schema for shared artifact (not exposed to other tenants)."""

    id: str
    fraud_event_id: str
    sharing_level: int  # Stored as integer (0=PRIVATE, 1=AGGREGATE, 2=NETWORK_MATCH)
    occurred_at: datetime
    occurred_month: str
    fraud_type: FraudType
    channel: FraudChannel
    amount_bucket: AmountBucket
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True
