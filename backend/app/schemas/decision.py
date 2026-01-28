"""Decision and reason code schemas."""

from datetime import datetime
from decimal import Decimal
from typing import Any

from app.models.decision import DecisionAction, DecisionType
from app.schemas.common import BaseSchema, TimestampSchema
from pydantic import BaseModel, Field

# =============================================================================
# EVIDENCE SNAPSHOT SCHEMAS
# =============================================================================


class ImageReference(BaseModel):
    """Reference to a check image at decision time."""

    id: str
    image_type: str  # "front", "back"
    external_id: str | None = None
    content_hash: str | None = None  # SHA-256 of image content


class CheckContextSnapshot(BaseModel):
    """Frozen check item context values at decision time."""

    amount: str  # Decimal as string for precision
    account_type: str | None = None
    account_tenure_days: int | None = None
    current_balance: str | None = None
    average_balance_30d: str | None = None
    avg_check_amount_30d: str | None = None
    avg_check_amount_90d: str | None = None
    avg_check_amount_365d: str | None = None
    check_frequency_30d: int | None = None
    returned_item_count_90d: int | None = None
    exception_count_90d: int | None = None
    risk_level: str | None = None
    risk_flags: list[str] = []
    upstream_flags: list[str] = []


class PolicyEvaluationSnapshot(BaseModel):
    """Policy evaluation results at decision time."""

    policy_version_id: str | None = None
    policy_name: str | None = None
    rules_triggered: list[dict[str, Any]] = []  # {"rule_id": "...", "name": "...", "result": ...}
    requires_dual_control: bool = False
    risk_score: float | None = None
    recommendation: str | None = None


class AIContextSnapshot(BaseModel):
    """AI/ML context at decision time."""

    ai_assisted: bool = False
    model_id: str | None = None  # e.g., "fraud-detection-v2.3"
    model_version: str | None = None
    ai_risk_score: str | None = None  # Decimal as string
    features_displayed: list[dict[str, Any]] = []  # Features shown to reviewer
    flags_displayed: list[dict[str, Any]] = []  # AI-generated flags shown
    flags_reviewed: list[str] = []  # Flag IDs user explicitly reviewed
    confidence_scores: dict[str, float] = {}  # Per-category confidence


class EvidenceSnapshot(BaseModel):
    """
    Complete evidence snapshot for audit replay.

    Captures the exact state at decision time to enable:
    - Audit replay: recreate exactly what reviewer saw
    - Vendor risk assessment: prove decision was informed
    - Regulatory compliance: demonstrate controls worked
    - Internal audit: verify consistency

    Evidence sealing provides cryptographic integrity:
    - evidence_hash: SHA-256 of canonical snapshot content
    - previous_evidence_hash: Links to previous decision for chain integrity
    - seal_timestamp: When the cryptographic seal was computed
    """

    snapshot_version: str = "1.0"
    captured_at: datetime

    # What the reviewer saw
    check_context: CheckContextSnapshot
    images: list[ImageReference] = []

    # What drove the decision
    policy_evaluation: PolicyEvaluationSnapshot
    ai_context: AIContextSnapshot

    # Decision details
    decision_context: dict[str, Any] = {}  # Additional context

    # Cryptographic seal for tamper-evidence (set after snapshot creation)
    seal_version: str | None = None  # e.g., "sha256-v1"
    evidence_hash: str | None = None  # SHA-256 of canonical snapshot content
    previous_evidence_hash: str | None = None  # Hash chain to previous decision
    seal_timestamp: datetime | None = None  # When seal was computed


class ReasonCodeBase(BaseModel):
    """Reason code base schema."""

    code: str = Field(..., min_length=2, max_length=50)
    description: str = Field(..., min_length=5, max_length=255)
    category: str
    decision_type: str
    requires_notes: bool = False


class ReasonCodeCreate(ReasonCodeBase):
    """Reason code create schema."""

    is_active: bool = True
    display_order: int = 0


class ReasonCodeUpdate(BaseModel):
    """Reason code update schema."""

    description: str | None = None
    is_active: bool | None = None
    display_order: int | None = None
    requires_notes: bool | None = None


class ReasonCodeResponse(ReasonCodeBase, TimestampSchema):
    """Reason code response schema."""

    id: str
    is_active: bool
    display_order: int


class DecisionCreate(BaseModel):
    """Decision create schema."""

    check_item_id: str
    decision_type: DecisionType
    action: DecisionAction
    reason_code_ids: list[str] = []
    notes: str | None = None
    ai_assisted: bool = False
    ai_flags_reviewed: list[str] = []
    attachment_ids: list[str] = []


class DualControlApprovalRequest(BaseModel):
    """Dual control approval request."""

    decision_id: str
    approve: bool
    notes: str | None = None


class DecisionResponse(TimestampSchema):
    """Decision response schema."""

    id: str
    check_item_id: str
    user_id: str
    username: str | None = None  # Denormalized for display
    decision_type: DecisionType
    action: DecisionAction
    reason_codes: list[ReasonCodeResponse] = []
    notes: str | None = None
    ai_assisted: bool
    ai_flags_reviewed: list[str] = []
    attachments: list[str] = []
    policy_version_id: str | None = None
    previous_status: str | None = None
    new_status: str | None = None
    is_dual_control_required: bool
    dual_control_approver_id: str | None = None
    dual_control_approved_at: datetime | None = None

    # Evidence snapshot for audit replay
    evidence_snapshot: EvidenceSnapshot | None = None


class DecisionSummaryResponse(BaseModel):
    """Decision summary for list views."""

    id: str
    decision_type: DecisionType
    action: DecisionAction
    username: str
    created_at: datetime
    reason_codes: list[str] = []  # Just codes for summary
