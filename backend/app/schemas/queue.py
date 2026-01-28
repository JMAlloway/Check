"""Queue schemas."""

from datetime import datetime

from app.models.queue import QueueType
from app.schemas.common import BaseSchema, TimestampSchema
from pydantic import BaseModel, Field


class QueueBase(BaseModel):
    """Queue base schema."""

    name: str = Field(..., min_length=2, max_length=100)
    description: str | None = None
    queue_type: QueueType = QueueType.STANDARD
    sla_hours: int = 4
    warning_threshold_minutes: int = 30


class QueueCreate(QueueBase):
    """Queue create schema."""

    routing_criteria: dict | None = None
    allowed_role_ids: list[str] = []
    allowed_user_ids: list[str] = []


class QueueUpdate(BaseModel):
    """Queue update schema."""

    name: str | None = None
    description: str | None = None
    queue_type: QueueType | None = None
    is_active: bool | None = None
    sla_hours: int | None = None
    warning_threshold_minutes: int | None = None
    routing_criteria: dict | None = None
    display_order: int | None = None


class QueueResponse(QueueBase, TimestampSchema):
    """Queue response schema."""

    id: str
    is_active: bool
    display_order: int
    current_item_count: int
    items_processed_today: int


class QueueStatsResponse(BaseModel):
    """Queue statistics response."""

    queue_id: str
    queue_name: str
    total_items: int
    items_by_status: dict[str, int]
    items_by_risk_level: dict[str, int]
    sla_breached_count: int
    avg_processing_time_minutes: float | None = None
    items_processed_today: int
    items_processed_this_hour: int
    oldest_item_age_minutes: int | None = None


class QueueAssignmentBase(BaseModel):
    """Queue assignment base schema."""

    queue_id: str
    user_id: str
    can_review: bool = True
    can_approve: bool = False
    max_concurrent_items: int = 10


class QueueAssignmentCreate(QueueAssignmentBase):
    """Queue assignment create schema."""

    pass


class QueueAssignmentUpdate(BaseModel):
    """Queue assignment update schema."""

    is_active: bool | None = None
    can_review: bool | None = None
    can_approve: bool | None = None
    max_concurrent_items: int | None = None


class QueueAssignmentResponse(QueueAssignmentBase, TimestampSchema):
    """Queue assignment response schema."""

    id: str
    is_active: bool
    assigned_at: datetime
    assigned_by_id: str | None = None
    user_name: str | None = None  # Denormalized
    queue_name: str | None = None  # Denormalized


class QueueItemAssignRequest(BaseModel):
    """Request to assign item to queue/user."""

    check_item_id: str
    queue_id: str | None = None
    reviewer_id: str | None = None
    approver_id: str | None = None
    priority: int | None = None


class BulkAssignRequest(BaseModel):
    """Bulk assignment request."""

    check_item_ids: list[str]
    queue_id: str | None = None
    reviewer_id: str | None = None
