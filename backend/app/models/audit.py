"""Audit log models."""

from datetime import datetime
from enum import Enum
from typing import Any
import hashlib
import json

from sqlalchemy import Boolean, DateTime, Enum as SQLEnum, ForeignKey, Index, String, Text
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
    IMAGE_TOKEN_CREATED = "image_token_created"
    IMAGE_TOKEN_USED = "image_token_used"
    IMAGE_TOKEN_EXPIRED = "image_token_expired"

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
    username: Mapped[str | None] = mapped_column(String(50))  # Denormalized for historical reference
    ip_address: Mapped[str | None] = mapped_column(String(45))
    user_agent: Mapped[str | None] = mapped_column(Text)

    # Action - use values_callable to store lowercase enum values (login_failed not LOGIN_FAILED)
    action: Mapped[AuditAction] = mapped_column(
        SQLEnum(AuditAction, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        index=True
    )
    resource_type: Mapped[str] = mapped_column(String(50), nullable=False)  # e.g., "check_item", "user"
    resource_id: Mapped[str | None] = mapped_column(String(255), index=True)  # 255 to accommodate demo image IDs

    # Details - JSONB for structured data and efficient querying
    description: Mapped[str | None] = mapped_column(Text)
    before_value: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    after_value: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    extra_data: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    # Session context
    session_id: Mapped[str | None] = mapped_column(String(36))

    # Demo mode flag - marks synthetic demo audit entries
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)

    # Integrity verification - SHA256 hash of critical fields
    # Used to detect tampering with audit records
    # Format: SHA256(id|tenant_id|timestamp|user_id|action|resource_type|resource_id|before|after|extra|previous_hash)
    integrity_hash: Mapped[str | None] = mapped_column(String(64), index=True)

    # Chain integrity - hash of the previous audit log entry
    # Creates a blockchain-like chain where tampering with any record breaks the chain
    # For the first record in a tenant, this will be "genesis"
    previous_hash: Mapped[str | None] = mapped_column(String(64), index=True)

    def compute_integrity_hash(self, previous_hash: str | None = None) -> str:
        """Compute SHA256 hash of critical audit fields for tamper detection.

        The hash includes all fields that, if modified, would indicate tampering.
        This is computed at insert time and can be verified at any point.

        Args:
            previous_hash: The hash of the previous audit log entry in the chain.
                          If None, uses self.previous_hash (for verification).
                          Pass "genesis" for the first entry in a tenant.
        """
        # Serialize values consistently for hashing
        def serialize(v: Any) -> str:
            if v is None:
                return "null"
            if isinstance(v, datetime):
                return v.isoformat()
            if isinstance(v, dict):
                return json.dumps(v, sort_keys=True, default=str)
            if isinstance(v, Enum):
                return str(v.value)
            return str(v)

        # Use provided previous_hash or fall back to stored value
        prev_hash = previous_hash if previous_hash is not None else self.previous_hash

        # Concatenate critical fields with pipe separator
        # Order matters - must be consistent
        # previous_hash is included to create the chain
        hash_input = "|".join([
            serialize(self.id),
            serialize(self.tenant_id),
            serialize(self.timestamp),
            serialize(self.user_id),
            serialize(self.action),
            serialize(self.resource_type),
            serialize(self.resource_id),
            serialize(self.before_value),
            serialize(self.after_value),
            serialize(self.extra_data),
            serialize(prev_hash),
        ])

        return hashlib.sha256(hash_input.encode("utf-8")).hexdigest()

    def verify_integrity(self) -> bool:
        """Verify that the audit log entry has not been tampered with.

        Returns True if the stored hash matches the computed hash.
        This verifies a single record's integrity.
        """
        if not self.integrity_hash:
            return False  # No hash means integrity cannot be verified
        return self.integrity_hash == self.compute_integrity_hash()

    def verify_chain_link(self, expected_previous_hash: str) -> bool:
        """Verify this entry's link to the previous entry in the chain.

        Args:
            expected_previous_hash: The integrity_hash of the previous entry,
                                   or "genesis" for the first entry.

        Returns:
            True if this entry's previous_hash matches the expected value
            AND this entry's integrity_hash is valid.
        """
        if self.previous_hash != expected_previous_hash:
            return False
        return self.verify_integrity()

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

    # Interaction counts - JSONB for structured data
    interaction_summary: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    # Demo mode flag - marks synthetic demo views
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)

    __table_args__ = (
        Index("ix_item_views_check_user", "check_item_id", "user_id"),
    )
