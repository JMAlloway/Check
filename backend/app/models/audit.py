"""Audit log models."""

from datetime import datetime
from enum import Enum
from typing import Any

from sqlalchemy import Boolean, DateTime
from sqlalchemy import Enum as SQLEnum
from sqlalchemy import ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.base import TimestampMixin, UUIDMixin


class AuditAction(str, Enum):
    """
    Audit action types.

    Naming convention:
    - Past tense for completed actions (logged after success)
    - _FAILED suffix for failed attempts
    - _OVERRIDDEN suffix for supervisor overrides
    """

    # Authentication
    LOGIN = "login"
    LOGOUT = "logout"
    LOGIN_FAILED = "login_failed"
    PASSWORD_CHANGE = "password_change"
    MFA_SETUP_STARTED = "mfa_setup_started"
    MFA_ENABLED = "mfa_enabled"
    MFA_DISABLED = "mfa_disabled"
    SESSION_EXPIRED = "session_expired"
    TOKEN_REFRESHED = "token_refreshed"

    # Authorization failures (critical for security monitoring)
    AUTH_PERMISSION_DENIED = "auth_permission_denied"
    AUTH_ROLE_DENIED = "auth_role_denied"
    AUTH_ENTITLEMENT_DENIED = "auth_entitlement_denied"
    AUTH_IP_DENIED = "auth_ip_denied"

    # Check items
    ITEM_VIEWED = "item_viewed"
    ITEM_ASSIGNED = "item_assigned"
    ITEM_REASSIGNED = "item_reassigned"
    ITEM_ESCALATED = "item_escalated"
    ITEM_STATUS_CHANGED = "item_status_changed"
    ITEM_LOCKED = "item_locked"
    ITEM_UNLOCKED = "item_unlocked"

    # Decisions - successes
    DECISION_MADE = "decision_made"
    DECISION_APPROVED = "decision_approved"
    DECISION_REJECTED = "decision_rejected"

    # Decisions - failures (must be logged for audit completeness)
    DECISION_FAILED = "decision_failed"
    DECISION_VALIDATION_FAILED = "decision_validation_failed"
    DECISION_ENTITLEMENT_FAILED = "decision_entitlement_failed"

    # Decisions - overrides and reversals
    DECISION_OVERRIDDEN = "decision_overridden"
    DECISION_REVERSED = "decision_reversed"
    DECISION_AMENDED = "decision_amended"

    # Dual control
    DUAL_CONTROL_REQUIRED = "dual_control_required"
    DUAL_CONTROL_APPROVED = "dual_control_approved"
    DUAL_CONTROL_REJECTED = "dual_control_rejected"
    DUAL_CONTROL_EXPIRED = "dual_control_expired"

    # Images
    IMAGE_VIEWED = "image_viewed"
    IMAGE_ZOOMED = "image_zoomed"
    IMAGE_DOWNLOADED = "image_downloaded"
    IMAGE_ACCESS_DENIED = "image_access_denied"

    # One-time image tokens (for secure image access)
    IMAGE_TOKEN_CREATED = "image_token_created"
    IMAGE_TOKEN_USED = "image_token_used"
    IMAGE_TOKEN_EXPIRED = "image_token_expired"
    IMAGE_TOKEN_REUSE_ATTEMPTED = "image_token_reuse_attempted"

    # Admin
    USER_CREATED = "user_created"
    USER_UPDATED = "user_updated"
    USER_DEACTIVATED = "user_deactivated"
    ROLE_ASSIGNED = "role_assigned"
    ROLE_REMOVED = "role_removed"
    POLICY_CREATED = "policy_created"
    POLICY_UPDATED = "policy_updated"
    POLICY_ACTIVATED = "policy_activated"
    POLICY_DELETED = "policy_deleted"
    QUEUE_CREATED = "queue_created"
    QUEUE_UPDATED = "queue_updated"
    ENTITLEMENT_CREATED = "entitlement_created"
    ENTITLEMENT_UPDATED = "entitlement_updated"
    ENTITLEMENT_REVOKED = "entitlement_revoked"

    # Export
    AUDIT_PACKET_GENERATED = "audit_packet_generated"
    REPORT_EXPORTED = "report_exported"
    REPORT_VIEWED = "report_viewed"
    DATA_EXPORTED = "data_exported"

    # AI inference (critical for explainability)
    AI_INFERENCE_REQUESTED = "ai_inference_requested"
    AI_INFERENCE_COMPLETED = "ai_inference_completed"
    AI_INFERENCE_FAILED = "ai_inference_failed"
    AI_ASSIST_VIEWED = "ai_assist_viewed"
    AI_ASSIST_FEEDBACK = "ai_assist_feedback"
    AI_RECOMMENDATION_ACCEPTED = "ai_recommendation_accepted"
    AI_RECOMMENDATION_REJECTED = "ai_recommendation_rejected"
    AI_RECOMMENDATION_OVERRIDDEN = "ai_recommendation_overridden"

    # Security
    UNAUTHORIZED_ACCESS = "unauthorized_access"
    SUSPICIOUS_ACTIVITY = "suspicious_activity"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"

    # Fraud Intelligence
    FRAUD_EVENT_CREATED = "fraud_event_created"
    FRAUD_EVENT_SUBMITTED = "fraud_event_submitted"
    FRAUD_EVENT_WITHDRAWN = "fraud_event_withdrawn"
    FRAUD_CONFIG_UPDATED = "fraud_config_updated"
    NETWORK_ALERT_DISMISSED = "network_alert_dismissed"
    FRAUD_MATCH_FOUND = "fraud_match_found"
    FRAUD_MATCH_REVIEWED = "fraud_match_reviewed"

    # System events
    SYSTEM_CONFIG_CHANGED = "system_config_changed"
    BATCH_OPERATION_STARTED = "batch_operation_started"
    BATCH_OPERATION_COMPLETED = "batch_operation_completed"
    INTEGRATION_SYNC_STARTED = "integration_sync_started"
    INTEGRATION_SYNC_COMPLETED = "integration_sync_completed"
    INTEGRATION_SYNC_FAILED = "integration_sync_failed"


class AuditLog(Base, UUIDMixin):
    """
    Immutable audit log entry.

    IMMUTABILITY ENFORCEMENT:
    - DB-level trigger blocks UPDATE and DELETE operations (see migration 004)
    - Application role should have INSERT/SELECT only permissions
    - No updated_at column - entries are write-once
    - Partitioning by timestamp recommended for retention management
    """

    __tablename__ = "audit_logs"

    # Tenant isolation - CRITICAL for multi-tenant security
    # NULL allowed for system-level events (startup, migrations, etc.)
    tenant_id: Mapped[str | None] = mapped_column(String(36), index=True)

    # Timestamp (not using mixin for immutability)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )

    # Actor
    user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    username: Mapped[str | None] = mapped_column(
        String(50)
    )  # Denormalized for historical reference
    ip_address: Mapped[str | None] = mapped_column(String(45))
    user_agent: Mapped[str | None] = mapped_column(Text)

    # Action - use values_callable to store lowercase enum values (login_failed not LOGIN_FAILED)
    action: Mapped[AuditAction] = mapped_column(
        SQLEnum(AuditAction, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        index=True,
    )
    resource_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # e.g., "check_item", "user"
    resource_id: Mapped[str | None] = mapped_column(
        String(255), index=True
    )  # 255 to accommodate demo image IDs

    # Details - JSONB for structured data and efficient querying
    description: Mapped[str | None] = mapped_column(Text)
    before_value: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    after_value: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    extra_data: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    # Session context
    session_id: Mapped[str | None] = mapped_column(String(36))

    # Demo mode flag - marks synthetic demo audit entries
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)

    __table_args__ = (
        Index("ix_audit_logs_resource", "resource_type", "resource_id"),
        Index("ix_audit_logs_user_action", "user_id", "action"),
        Index("ix_audit_logs_timestamp_action", "timestamp", "action"),
    )


class ItemView(Base, UUIDMixin, TimestampMixin):
    """
    Track detailed item viewing activity.

    IMMUTABILITY ENFORCEMENT:
    - DB-level trigger blocks UPDATE and DELETE operations (see migration 004)
    - View records are append-only for audit compliance
    """

    __tablename__ = "item_views"

    # Tenant isolation - CRITICAL for multi-tenant security
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    check_item_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("check_items.id"), nullable=False
    )
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

    # Interaction counts - JSONB for structured data
    interaction_summary: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    # Demo mode flag - marks synthetic demo views
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)

    __table_args__ = (Index("ix_item_views_check_user", "check_item_id", "user_id"),)
