"""Audit log models."""

from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, Enum as SQLEnum, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.base import TimestampMixin, UUIDMixin


class AuditAction(str, Enum):
    """Audit action types."""

    # Authentication
    LOGIN = "login"
    LOGOUT = "logout"
    LOGIN_FAILED = "login_failed"
    PASSWORD_CHANGE = "password_change"
    MFA_ENABLED = "mfa_enabled"
    MFA_DISABLED = "mfa_disabled"

    # Check items
    ITEM_VIEWED = "item_viewed"
    ITEM_ASSIGNED = "item_assigned"
    ITEM_REASSIGNED = "item_reassigned"
    ITEM_ESCALATED = "item_escalated"
    ITEM_STATUS_CHANGED = "item_status_changed"

    # Decisions
    DECISION_MADE = "decision_made"
    DECISION_APPROVED = "decision_approved"
    DECISION_REJECTED = "decision_rejected"

    # Images
    IMAGE_VIEWED = "image_viewed"
    IMAGE_ZOOMED = "image_zoomed"
    IMAGE_DOWNLOADED = "image_downloaded"

    # Admin
    USER_CREATED = "user_created"
    USER_UPDATED = "user_updated"
    USER_DEACTIVATED = "user_deactivated"
    ROLE_ASSIGNED = "role_assigned"
    ROLE_REMOVED = "role_removed"
    POLICY_CREATED = "policy_created"
    POLICY_UPDATED = "policy_updated"
    POLICY_ACTIVATED = "policy_activated"
    QUEUE_CREATED = "queue_created"
    QUEUE_UPDATED = "queue_updated"

    # Export
    AUDIT_PACKET_GENERATED = "audit_packet_generated"
    REPORT_EXPORTED = "report_exported"

    # AI
    AI_ASSIST_VIEWED = "ai_assist_viewed"
    AI_ASSIST_FEEDBACK = "ai_assist_feedback"


class AuditLog(Base, UUIDMixin):
    """Immutable audit log entry."""

    __tablename__ = "audit_logs"

    # Timestamp (not using mixin for immutability)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )

    # Actor
    user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    username: Mapped[str | None] = mapped_column(String(50))  # Denormalized for historical reference
    ip_address: Mapped[str | None] = mapped_column(String(45))
    user_agent: Mapped[str | None] = mapped_column(Text)

    # Action
    action: Mapped[AuditAction] = mapped_column(SQLEnum(AuditAction), nullable=False, index=True)
    resource_type: Mapped[str] = mapped_column(String(50), nullable=False)  # e.g., "check_item", "user"
    resource_id: Mapped[str | None] = mapped_column(String(36), index=True)

    # Details
    description: Mapped[str | None] = mapped_column(Text)
    before_value: Mapped[str | None] = mapped_column(Text)  # JSON
    after_value: Mapped[str | None] = mapped_column(Text)  # JSON
    metadata: Mapped[str | None] = mapped_column(Text)  # JSON for additional context

    # Session context
    session_id: Mapped[str | None] = mapped_column(String(36))

    __table_args__ = (
        Index("ix_audit_logs_resource", "resource_type", "resource_id"),
        Index("ix_audit_logs_user_action", "user_id", "action"),
        Index("ix_audit_logs_timestamp_action", "timestamp", "action"),
    )


class ItemView(Base, UUIDMixin, TimestampMixin):
    """Track detailed item viewing activity."""

    __tablename__ = "item_views"

    check_item_id: Mapped[str] = mapped_column(String(36), ForeignKey("check_items.id"), nullable=False)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    session_id: Mapped[str | None] = mapped_column(String(36))

    # View details
    view_started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    view_ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_seconds: Mapped[int | None] = mapped_column()

    # Interaction tracking
    front_image_viewed: Mapped[bool] = mapped_column(default=False)
    back_image_viewed: Mapped[bool] = mapped_column(default=False)
    zoom_used: Mapped[bool] = mapped_column(default=False)
    magnifier_used: Mapped[bool] = mapped_column(default=False)
    history_compared: Mapped[bool] = mapped_column(default=False)
    ai_assists_viewed: Mapped[bool] = mapped_column(default=False)
    context_panel_viewed: Mapped[bool] = mapped_column(default=False)

    # Interaction counts (JSON)
    interaction_summary: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        Index("ix_item_views_check_user", "check_item_id", "user_id"),
    )
