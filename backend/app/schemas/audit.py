"""Audit schemas."""

from datetime import datetime

from app.models.audit import AuditAction
from app.schemas.common import BaseSchema
from pydantic import BaseModel


class AuditLogResponse(BaseSchema):
    """Audit log response schema."""

    id: str
    timestamp: datetime
    user_id: str | None = None
    username: str | None = None
    ip_address: str | None = None
    action: AuditAction
    resource_type: str
    resource_id: str | None = None
    description: str | None = None
    before_value: dict | None = None
    after_value: dict | None = None
    metadata: dict | None = None


class AuditLogSearchRequest(BaseModel):
    """Audit log search request."""

    user_id: str | None = None
    action: AuditAction | None = None
    resource_type: str | None = None
    resource_id: str | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None


class ItemViewResponse(BaseSchema):
    """Item view response schema."""

    id: str
    check_item_id: str
    user_id: str
    username: str | None = None
    view_started_at: datetime
    view_ended_at: datetime | None = None
    duration_seconds: int | None = None
    front_image_viewed: bool
    back_image_viewed: bool
    zoom_used: bool
    magnifier_used: bool
    history_compared: bool
    ai_assists_viewed: bool


class AuditPacketRequest(BaseModel):
    """Audit packet generation request."""

    check_item_id: str
    include_images: bool = True
    include_history: bool = True
    include_all_decisions: bool = True
    include_view_logs: bool = True
    format: str = "pdf"  # "pdf" or "json"


class AuditPacketResponse(BaseModel):
    """Audit packet generation response."""

    packet_id: str
    check_item_id: str
    generated_at: datetime
    generated_by: str
    format: str
    download_url: str
    expires_at: datetime
