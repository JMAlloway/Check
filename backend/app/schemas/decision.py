"""Decision and reason code schemas."""

from datetime import datetime

from pydantic import BaseModel, Field

from app.models.decision import DecisionAction, DecisionType
from app.schemas.common import BaseSchema, TimestampSchema


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


class DecisionSummaryResponse(BaseModel):
    """Decision summary for list views."""

    id: str
    decision_type: DecisionType
    action: DecisionAction
    username: str
    created_at: datetime
    reason_codes: list[str] = []  # Just codes for summary
