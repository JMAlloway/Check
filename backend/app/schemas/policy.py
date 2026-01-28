"""Policy schemas."""

from datetime import datetime
from decimal import Decimal

from app.models.policy import PolicyStatus, RuleConditionOperator, RuleType
from app.schemas.common import BaseSchema, TimestampSchema
from pydantic import BaseModel, Field


class RuleCondition(BaseModel):
    """Rule condition schema."""

    field: str
    operator: RuleConditionOperator
    value: str | int | float | list | None = None
    value_type: str = "string"  # "string", "number", "boolean", "array"


class RuleAction(BaseModel):
    """Rule action schema."""

    action: str  # "require_dual_control", "escalate", "route_to_queue", "require_reason"
    params: dict | None = None


class PolicyRuleBase(BaseModel):
    """Policy rule base schema."""

    name: str = Field(..., min_length=2, max_length=100)
    description: str | None = None
    rule_type: RuleType
    priority: int = 0
    is_enabled: bool = True
    conditions: list[RuleCondition]
    actions: list[RuleAction]
    amount_threshold: Decimal | None = None
    risk_level_threshold: str | None = None


class PolicyRuleCreate(PolicyRuleBase):
    """Policy rule create schema."""

    pass


class PolicyRuleUpdate(BaseModel):
    """Policy rule update schema."""

    name: str | None = None
    description: str | None = None
    priority: int | None = None
    is_enabled: bool | None = None
    conditions: list[RuleCondition] | None = None
    actions: list[RuleAction] | None = None


class PolicyRuleResponse(PolicyRuleBase, TimestampSchema):
    """Policy rule response schema."""

    id: str
    policy_version_id: str


class PolicyVersionBase(BaseModel):
    """Policy version base schema."""

    effective_date: datetime
    expiry_date: datetime | None = None
    change_notes: str | None = None


class PolicyVersionCreate(PolicyVersionBase):
    """Policy version create schema."""

    rules: list[PolicyRuleCreate] = []


class PolicyVersionResponse(PolicyVersionBase, TimestampSchema):
    """Policy version response schema."""

    id: str
    policy_id: str
    version_number: int
    is_current: bool
    approved_by_id: str | None = None
    approved_at: datetime | None = None
    rules: list[PolicyRuleResponse] = []


class PolicyBase(BaseModel):
    """Policy base schema."""

    name: str = Field(..., min_length=2, max_length=100)
    description: str | None = None
    applies_to_account_types: list[str] | None = None
    applies_to_branches: list[str] | None = None
    applies_to_markets: list[str] | None = None


class PolicyCreate(PolicyBase):
    """Policy create schema."""

    initial_version: PolicyVersionCreate | None = None


class PolicyUpdate(BaseModel):
    """Policy update schema."""

    name: str | None = None
    description: str | None = None
    status: PolicyStatus | None = None
    applies_to_account_types: list[str] | None = None
    applies_to_branches: list[str] | None = None
    applies_to_markets: list[str] | None = None


class PolicyResponse(PolicyBase, TimestampSchema):
    """Policy response schema."""

    id: str
    status: PolicyStatus
    is_default: bool
    versions: list[PolicyVersionResponse] = []
    current_version: PolicyVersionResponse | None = None


class PolicyListResponse(BaseSchema):
    """Policy list response (compact)."""

    id: str
    name: str
    description: str | None = None
    status: PolicyStatus
    is_default: bool
    current_version_number: int | None = None
    rules_count: int = 0


class PolicyEvaluationResult(BaseModel):
    """Result of policy evaluation for an item."""

    policy_id: str
    policy_version_id: str
    rules_triggered: list[str] = []  # Rule IDs
    requires_dual_control: bool = False
    risk_level: str | None = None
    routing_queue_id: str | None = None
    required_reason_categories: list[str] = []
    flags: list[str] = []
