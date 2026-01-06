"""Check item and image schemas."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.models.check import AccountType, CheckStatus, RiskLevel
from app.schemas.common import BaseSchema, TimestampSchema


class CheckImageResponse(BaseSchema):
    """Check image response schema."""

    id: str
    image_type: str
    content_type: str
    file_size: int | None = None
    width: int | None = None
    height: int | None = None
    image_url: str | None = None  # Signed URL for secure access
    thumbnail_url: str | None = None


class AccountContextResponse(BaseModel):
    """Account context information."""

    account_tenure_days: int | None = None
    current_balance: Decimal | None = None
    average_balance_30d: Decimal | None = None
    avg_check_amount_30d: Decimal | None = None
    avg_check_amount_90d: Decimal | None = None
    avg_check_amount_365d: Decimal | None = None
    check_std_dev_30d: Decimal | None = None
    max_check_amount_90d: Decimal | None = None
    check_frequency_30d: int | None = None
    returned_item_count_90d: int | None = None
    exception_count_90d: int | None = None
    amount_vs_avg_ratio: float | None = None  # Computed: amount / avg_check_amount_30d


class AIFlagResponse(BaseModel):
    """AI/rule-based flag response."""

    code: str
    description: str
    category: str  # "amount", "signature", "micr", "stock", "behavior"
    severity: str  # "info", "warning", "alert"
    confidence: float | None = None
    explanation: str | None = None


class CheckItemBase(BaseModel):
    """Check item base schema."""

    account_number_masked: str
    account_type: AccountType
    check_number: str | None = None
    amount: Decimal = Field(..., ge=0, decimal_places=2)
    payee_name: str | None = None
    memo: str | None = None
    check_date: datetime | None = None


class CheckItemCreate(CheckItemBase):
    """Check item create schema (for testing/mock)."""

    external_item_id: str
    source_system: str = "mock"
    account_id: str
    presented_date: datetime
    micr_line: str | None = None


class CheckItemUpdate(BaseModel):
    """Check item update schema."""

    status: CheckStatus | None = None
    risk_level: RiskLevel | None = None
    priority: int | None = None
    assigned_reviewer_id: str | None = None
    assigned_approver_id: str | None = None
    queue_id: str | None = None
    notes: str | None = None


class CheckItemResponse(CheckItemBase, TimestampSchema):
    """Check item full response schema."""

    id: str
    external_item_id: str
    source_system: str
    account_id: str
    routing_number: str | None = None
    micr_line: str | None = None
    presented_date: datetime
    process_date: datetime | None = None
    status: CheckStatus
    risk_level: RiskLevel
    priority: int
    requires_dual_control: bool
    has_ai_flags: bool
    sla_due_at: datetime | None = None
    sla_breached: bool
    assigned_reviewer_id: str | None = None
    assigned_approver_id: str | None = None
    queue_id: str | None = None
    policy_version_id: str | None = None
    images: list[CheckImageResponse] = []
    account_context: AccountContextResponse | None = None
    ai_flags: list[AIFlagResponse] = []


class CheckItemListResponse(BaseSchema):
    """Check item list response (compact)."""

    id: str
    external_item_id: str
    account_number_masked: str
    account_type: AccountType
    amount: Decimal
    check_number: str | None = None
    payee_name: str | None = None
    presented_date: datetime
    status: CheckStatus
    risk_level: RiskLevel
    priority: int
    requires_dual_control: bool
    has_ai_flags: bool
    sla_due_at: datetime | None = None
    sla_breached: bool
    assigned_reviewer_id: str | None = None
    thumbnail_url: str | None = None


class CheckHistoryResponse(BaseSchema):
    """Check history response schema."""

    id: str
    account_id: str
    check_number: str | None = None
    amount: Decimal
    check_date: datetime
    payee_name: str | None = None
    status: str
    return_reason: str | None = None
    front_image_url: str | None = None
    back_image_url: str | None = None


class CheckComparisonRequest(BaseModel):
    """Request for side-by-side check comparison."""

    current_item_id: str
    historical_item_id: str


class CheckSearchRequest(BaseModel):
    """Check item search request."""

    account_number: str | None = None
    item_id: str | None = None
    amount_min: Decimal | None = None
    amount_max: Decimal | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None
    status: list[CheckStatus] | None = None
    risk_level: list[RiskLevel] | None = None
    queue_id: str | None = None
    assigned_to: str | None = None
    has_ai_flags: bool | None = None
    sla_breached: bool | None = None
