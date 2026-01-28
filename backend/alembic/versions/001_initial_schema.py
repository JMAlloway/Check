"""Initial schema with all base tables.

Revision ID: 001_initial
Revises:
Create Date: 2026-01-06

This migration creates all base tables with complete column definitions
matching the SQLAlchemy models. Later migrations should only add new
tables or modify existing structures - not add missing columns.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create initial schema tables."""

    # ==========================================================================
    # CREATE ENUMS
    # ==========================================================================

    # Check workflow enums
    check_status_enum = postgresql.ENUM(
        "new",
        "in_review",
        "escalated",
        "pending_dual_control",
        "pending_approval",
        "approved",
        "rejected",
        "returned",
        "closed",
        name="checkstatus",
        create_type=False,
    )
    check_status_enum.create(op.get_bind(), checkfirst=True)

    risk_level_enum = postgresql.ENUM(
        "low", "medium", "high", "critical", name="risklevel", create_type=False
    )
    risk_level_enum.create(op.get_bind(), checkfirst=True)

    account_type_enum = postgresql.ENUM(
        "consumer", "business", "commercial", "non_profit", name="accounttype", create_type=False
    )
    account_type_enum.create(op.get_bind(), checkfirst=True)

    # Decision enums
    decision_type_enum = postgresql.ENUM(
        "review_recommendation",
        "approval_decision",
        "escalation",
        name="decisiontype",
        create_type=False,
    )
    decision_type_enum.create(op.get_bind(), checkfirst=True)

    decision_action_enum = postgresql.ENUM(
        "approve",
        "return",
        "reject",
        "hold",
        "escalate",
        "needs_more_info",
        name="decisionaction",
        create_type=False,
    )
    decision_action_enum.create(op.get_bind(), checkfirst=True)

    # Queue enums
    queue_type_enum = postgresql.ENUM(
        "standard",
        "high_priority",
        "escalation",
        "special_review",
        name="queuetype",
        create_type=False,
    )
    queue_type_enum.create(op.get_bind(), checkfirst=True)

    # Policy enums
    policy_status_enum = postgresql.ENUM(
        "draft", "active", "archived", name="policystatus", create_type=False
    )
    policy_status_enum.create(op.get_bind(), checkfirst=True)

    rule_type_enum = postgresql.ENUM(
        "threshold",
        "dual_control",
        "escalation",
        "routing",
        "require_reason",
        name="ruletype",
        create_type=False,
    )
    rule_type_enum.create(op.get_bind(), checkfirst=True)

    # Audit action enum
    audit_action_enum = postgresql.ENUM(
        # Authentication
        "login",
        "logout",
        "login_failed",
        "password_change",
        "mfa_enabled",
        "mfa_disabled",
        "session_expired",
        "token_refreshed",
        # Authorization failures
        "auth_permission_denied",
        "auth_role_denied",
        "auth_entitlement_denied",
        "auth_ip_denied",
        # Check items
        "item_viewed",
        "item_assigned",
        "item_reassigned",
        "item_escalated",
        "item_status_changed",
        "item_locked",
        "item_unlocked",
        # Decisions - successes
        "decision_made",
        "decision_approved",
        "decision_rejected",
        # Decisions - failures
        "decision_failed",
        "decision_validation_failed",
        "decision_entitlement_failed",
        # Decisions - overrides
        "decision_overridden",
        "decision_reversed",
        "decision_amended",
        # Dual control
        "dual_control_required",
        "dual_control_approved",
        "dual_control_rejected",
        "dual_control_expired",
        # Images
        "image_viewed",
        "image_zoomed",
        "image_downloaded",
        "image_access_denied",
        # Admin
        "user_created",
        "user_updated",
        "user_deactivated",
        "role_assigned",
        "role_removed",
        "policy_created",
        "policy_updated",
        "policy_activated",
        "queue_created",
        "queue_updated",
        "entitlement_created",
        "entitlement_updated",
        "entitlement_revoked",
        # Export
        "audit_packet_generated",
        "report_exported",
        "report_viewed",
        "data_exported",
        # AI inference
        "ai_inference_requested",
        "ai_inference_completed",
        "ai_inference_failed",
        "ai_assist_viewed",
        "ai_assist_feedback",
        "ai_recommendation_accepted",
        "ai_recommendation_rejected",
        "ai_recommendation_overridden",
        # Security
        "unauthorized_access",
        "suspicious_activity",
        "rate_limit_exceeded",
        # Fraud Intelligence
        "fraud_event_created",
        "fraud_event_submitted",
        "fraud_event_withdrawn",
        "fraud_config_updated",
        "network_alert_dismissed",
        "fraud_match_found",
        "fraud_match_reviewed",
        # System events
        "system_config_changed",
        "batch_operation_started",
        "batch_operation_completed",
        "integration_sync_started",
        "integration_sync_completed",
        "integration_sync_failed",
        name="auditaction",
        create_type=False,
    )
    audit_action_enum.create(op.get_bind(), checkfirst=True)

    # Approval entitlement type enum
    approval_entitlement_type_enum = postgresql.ENUM(
        "review", "approve", "override", name="approvalentitlementtype", create_type=False
    )
    approval_entitlement_type_enum.create(op.get_bind(), checkfirst=True)

    # ==========================================================================
    # PERMISSIONS TABLE
    # ==========================================================================
    op.create_table(
        "permissions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
        sa.Column("resource", sa.String(50), nullable=False),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("conditions", sa.Text),  # JSON conditions
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )

    # ==========================================================================
    # ROLES TABLE
    # ==========================================================================
    op.create_table(
        "roles",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(50), nullable=False, unique=True),
        sa.Column("description", sa.Text),
        sa.Column("is_system", sa.Boolean, default=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )

    # ==========================================================================
    # ROLE_PERMISSIONS (many-to-many)
    # ==========================================================================
    op.create_table(
        "role_permissions",
        sa.Column(
            "role_id",
            sa.String(36),
            sa.ForeignKey("roles.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "permission_id",
            sa.String(36),
            sa.ForeignKey("permissions.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )

    # ==========================================================================
    # USERS TABLE
    # ==========================================================================
    op.create_table(
        "users",
        sa.Column("id", sa.String(36), primary_key=True),
        # Multi-tenant
        sa.Column("tenant_id", sa.String(36), nullable=False),
        # Basic info
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("username", sa.String(50), nullable=False, unique=True),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(100), nullable=False),
        # Status
        sa.Column("is_active", sa.Boolean, default=True),
        sa.Column("is_superuser", sa.Boolean, default=False),
        # MFA
        sa.Column("mfa_enabled", sa.Boolean, default=False),
        sa.Column("mfa_secret", sa.String(255)),
        # Organization
        sa.Column("department", sa.String(100)),
        sa.Column("branch", sa.String(100)),
        sa.Column("employee_id", sa.String(50)),
        # Security
        sa.Column("last_login", sa.DateTime(timezone=True)),
        sa.Column("failed_login_attempts", sa.Integer, default=0),
        sa.Column("locked_until", sa.DateTime(timezone=True)),
        sa.Column("password_changed_at", sa.DateTime(timezone=True)),
        # IP restrictions - JSONB array of allowed IP addresses/CIDRs
        sa.Column("allowed_ips", postgresql.JSONB),
        # Timestamps
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )
    op.create_index("ix_users_tenant_id", "users", ["tenant_id"])
    op.create_index("ix_users_email", "users", ["email"])
    op.create_index("ix_users_username", "users", ["username"])

    # ==========================================================================
    # USER_ROLES (many-to-many)
    # ==========================================================================
    op.create_table(
        "user_roles",
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "role_id",
            sa.String(36),
            sa.ForeignKey("roles.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )

    # ==========================================================================
    # USER_SESSIONS TABLE
    # ==========================================================================
    op.create_table(
        "user_sessions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("token_hash", sa.String(255), nullable=False, unique=True),
        sa.Column("ip_address", sa.String(45)),
        sa.Column("user_agent", sa.Text),
        sa.Column("device_fingerprint", sa.String(255)),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_active", sa.Boolean, default=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )
    op.create_index("ix_user_sessions_user_id", "user_sessions", ["user_id"])
    op.create_index("ix_user_sessions_token_hash", "user_sessions", ["token_hash"])

    # ==========================================================================
    # QUEUES TABLE
    # ==========================================================================
    op.create_table(
        "queues",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("queue_type", queue_type_enum, nullable=False, server_default="standard"),
        sa.Column("is_active", sa.Boolean, default=True),
        sa.Column("display_order", sa.Integer, default=0),
        # SLA settings
        sa.Column("sla_hours", sa.Integer, default=4),
        sa.Column("warning_threshold_minutes", sa.Integer, default=30),
        # Routing criteria
        sa.Column("routing_criteria", sa.Text),  # JSON
        # Access control
        sa.Column("allowed_roles", sa.Text),  # JSON array of role IDs
        sa.Column("allowed_users", sa.Text),  # JSON array of user IDs
        # Stats (denormalized)
        sa.Column("current_item_count", sa.Integer, default=0),
        sa.Column("items_processed_today", sa.Integer, default=0),
        # Multi-tenant
        sa.Column("tenant_id", sa.String(36)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )

    # ==========================================================================
    # POLICIES TABLE
    # ==========================================================================
    op.create_table(
        "policies",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("status", policy_status_enum, nullable=False, server_default="draft"),
        sa.Column("is_default", sa.Boolean, default=False),
        # Scope
        sa.Column("applies_to_account_types", sa.Text),  # JSON array
        sa.Column("applies_to_branches", sa.Text),  # JSON array
        sa.Column("applies_to_markets", sa.Text),  # JSON array
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )

    # ==========================================================================
    # POLICY_VERSIONS TABLE
    # ==========================================================================
    op.create_table(
        "policy_versions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "policy_id",
            sa.String(36),
            sa.ForeignKey("policies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version_number", sa.Integer, nullable=False),
        sa.Column("effective_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expiry_date", sa.DateTime(timezone=True)),
        sa.Column("is_current", sa.Boolean, default=False),
        # Snapshot of rules
        sa.Column("rules_snapshot", sa.Text),  # JSON
        # Approval
        sa.Column("approved_by_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("approved_at", sa.DateTime(timezone=True)),
        sa.Column("change_notes", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )

    # ==========================================================================
    # POLICY_RULES TABLE
    # ==========================================================================
    op.create_table(
        "policy_rules",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "policy_version_id",
            sa.String(36),
            sa.ForeignKey("policy_versions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("rule_type", rule_type_enum, nullable=False),
        sa.Column("priority", sa.Integer, default=0),
        sa.Column("is_enabled", sa.Boolean, default=True),
        # Conditions and actions (JSON)
        sa.Column("conditions", sa.Text, nullable=False),
        sa.Column("actions", sa.Text, nullable=False),
        # Quick-access thresholds
        sa.Column("amount_threshold", sa.Numeric(12, 2)),
        sa.Column("risk_level_threshold", sa.String(20)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )

    # ==========================================================================
    # CHECK_ITEMS TABLE
    # ==========================================================================
    op.create_table(
        "check_items",
        sa.Column("id", sa.String(36), primary_key=True),
        # External identifiers
        sa.Column("external_item_id", sa.String(100), unique=True, nullable=False),
        sa.Column("source_system", sa.String(50), nullable=False),
        # Account information
        sa.Column("account_id", sa.String(50), nullable=False),
        sa.Column("account_number_masked", sa.String(20), nullable=False),
        sa.Column("account_type", account_type_enum, nullable=False),
        sa.Column("routing_number", sa.String(9)),
        # Check details
        sa.Column("check_number", sa.String(20)),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(3), default="USD"),
        sa.Column("payee_name", sa.String(255)),
        sa.Column("memo", sa.String(255)),
        # MICR data
        sa.Column("micr_line", sa.String(100)),
        sa.Column("micr_account", sa.String(20)),
        sa.Column("micr_routing", sa.String(9)),
        sa.Column("micr_check_number", sa.String(20)),
        # Dates
        sa.Column("presented_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("check_date", sa.DateTime(timezone=True)),
        sa.Column("process_date", sa.DateTime(timezone=True)),
        # Workflow
        sa.Column("status", check_status_enum, nullable=False, server_default="new"),
        sa.Column("risk_level", risk_level_enum, nullable=False, server_default="low"),
        sa.Column("priority", sa.Integer, default=0),
        # Assignments
        sa.Column(
            "assigned_reviewer_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL")
        ),
        sa.Column(
            "assigned_approver_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL")
        ),
        sa.Column("queue_id", sa.String(36), sa.ForeignKey("queues.id", ondelete="SET NULL")),
        # SLA tracking
        sa.Column("sla_due_at", sa.DateTime(timezone=True)),
        sa.Column("sla_breached", sa.Boolean, default=False),
        # Dual control tracking
        sa.Column("requires_dual_control", sa.Boolean, default=False),
        sa.Column(
            "pending_dual_control_decision_id", sa.String(36), nullable=True
        ),  # FK added later to avoid circular ref
        sa.Column("dual_control_reason", sa.String(100)),
        # Flags and context
        sa.Column("has_ai_flags", sa.Boolean, default=False),
        sa.Column("ai_risk_score", sa.Numeric(5, 4)),
        sa.Column("risk_flags", sa.Text),  # JSON array
        sa.Column("upstream_flags", sa.Text),  # Flags from source system
        # AI Analysis Tracking - ADVISORY ONLY
        sa.Column("ai_model_id", sa.String(100)),
        sa.Column("ai_model_version", sa.String(50)),
        sa.Column("ai_analyzed_at", sa.DateTime(timezone=True)),
        sa.Column("ai_recommendation", sa.String(50)),  # ADVISORY
        sa.Column("ai_confidence", sa.Numeric(5, 4)),
        sa.Column("ai_explanation", sa.Text),
        sa.Column("ai_risk_factors", sa.Text),  # JSON array
        # Account context (denormalized for performance)
        sa.Column("account_tenure_days", sa.Integer),
        sa.Column("current_balance", sa.Numeric(14, 2)),
        sa.Column("average_balance_30d", sa.Numeric(14, 2)),
        sa.Column("avg_check_amount_30d", sa.Numeric(12, 2)),
        sa.Column("avg_check_amount_90d", sa.Numeric(12, 2)),
        sa.Column("avg_check_amount_365d", sa.Numeric(12, 2)),
        sa.Column("check_std_dev_30d", sa.Numeric(12, 2)),
        sa.Column("max_check_amount_90d", sa.Numeric(12, 2)),
        sa.Column("check_frequency_30d", sa.Integer),
        sa.Column("returned_item_count_90d", sa.Integer),
        sa.Column("exception_count_90d", sa.Integer),
        sa.Column("relationship_id", sa.String(50)),
        # Policy tracking
        sa.Column(
            "policy_version_id",
            sa.String(36),
            sa.ForeignKey("policy_versions.id", ondelete="SET NULL"),
        ),
        # Multi-tenant
        sa.Column("tenant_id", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )
    op.create_index("ix_check_items_tenant_id", "check_items", ["tenant_id"])
    op.create_index("ix_check_items_status", "check_items", ["status"])
    op.create_index("ix_check_items_account_id", "check_items", ["account_id"])
    op.create_index("ix_check_items_external_item_id", "check_items", ["external_item_id"])
    op.create_index("ix_check_items_presented_date", "check_items", ["presented_date"])
    op.create_index("ix_check_items_amount", "check_items", ["amount"])
    op.create_index("ix_check_items_risk_level", "check_items", ["risk_level"])
    op.create_index("ix_check_items_priority", "check_items", ["priority"])
    op.create_index("ix_check_items_status_priority", "check_items", ["status", "priority"])
    op.create_index("ix_check_items_queue_status", "check_items", ["queue_id", "status"])
    op.create_index(
        "ix_check_items_ai_analyzed",
        "check_items",
        ["ai_analyzed_at"],
        postgresql_where=sa.text("ai_analyzed_at IS NOT NULL"),
    )

    # ==========================================================================
    # CHECK_IMAGES TABLE
    # ==========================================================================
    op.create_table(
        "check_images",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "check_item_id",
            sa.String(36),
            sa.ForeignKey("check_items.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("image_type", sa.String(20), nullable=False),  # "front", "back"
        sa.Column("external_image_id", sa.String(100)),
        sa.Column("storage_path", sa.String(500)),
        sa.Column("content_type", sa.String(50), default="image/tiff"),
        sa.Column("file_size", sa.Integer),
        sa.Column("width", sa.Integer),
        sa.Column("height", sa.Integer),
        sa.Column("dpi", sa.Integer),
        sa.Column("thumbnail_path", sa.String(500)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )

    # ==========================================================================
    # CHECK_HISTORY TABLE
    # ==========================================================================
    op.create_table(
        "check_history",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("account_id", sa.String(50), nullable=False),
        sa.Column("check_number", sa.String(20)),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("check_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payee_name", sa.String(255)),
        sa.Column("status", sa.String(20), nullable=False),  # "cleared", "returned", etc.
        sa.Column("return_reason", sa.String(100)),
        sa.Column("external_item_id", sa.String(100)),
        sa.Column("front_image_ref", sa.String(255)),
        sa.Column("back_image_ref", sa.String(255)),
        sa.Column("signature_hash", sa.String(64)),
        sa.Column("check_stock_hash", sa.String(64)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )
    op.create_index("ix_check_history_account_id", "check_history", ["account_id"])
    op.create_index("ix_check_history_account_date", "check_history", ["account_id", "check_date"])

    # ==========================================================================
    # REASON_CODES TABLE
    # ==========================================================================
    op.create_table(
        "reason_codes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("code", sa.String(50), nullable=False, unique=True),
        sa.Column("description", sa.String(255), nullable=False),
        sa.Column("category", sa.String(50), nullable=False),
        sa.Column("decision_type", sa.String(50), nullable=False),  # "return", "reject", "escalate"
        sa.Column("is_active", sa.Boolean, default=True),
        sa.Column("display_order", sa.Integer, default=0),
        sa.Column("requires_notes", sa.Boolean, default=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )

    # ==========================================================================
    # DECISIONS TABLE
    # ==========================================================================
    op.create_table(
        "decisions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "check_item_id",
            sa.String(36),
            sa.ForeignKey("check_items.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=False
        ),
        # Decision details
        sa.Column("decision_type", decision_type_enum, nullable=False),
        sa.Column("action", decision_action_enum, nullable=False),
        # Reason codes and notes
        sa.Column("reason_codes", sa.Text),  # JSON array of reason code IDs
        sa.Column("notes", sa.Text),
        # AI assist info
        sa.Column("ai_assisted", sa.Boolean, default=False),
        sa.Column("ai_flags_reviewed", sa.Text),  # JSON array
        # Attachments
        sa.Column("attachments", sa.Text),  # JSON array
        # Policy tracking
        sa.Column(
            "policy_version_id",
            sa.String(36),
            sa.ForeignKey("policy_versions.id", ondelete="SET NULL"),
        ),
        # Workflow tracking
        sa.Column("previous_status", sa.String(50)),
        sa.Column("new_status", sa.String(50)),
        # Dual control
        sa.Column("is_dual_control_required", sa.Boolean, default=False),
        sa.Column(
            "dual_control_approver_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.Column("dual_control_approved_at", sa.DateTime(timezone=True)),
        # Evidence Snapshot - CRITICAL for bank-grade audit replay
        sa.Column("evidence_snapshot", postgresql.JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )

    # Now add the FK from check_items to decisions (avoiding circular ref during table creation)
    op.create_foreign_key(
        "fk_check_items_pending_decision",
        "check_items",
        "decisions",
        ["pending_dual_control_decision_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_check_items_pending_dual_control", "check_items", ["pending_dual_control_decision_id"]
    )

    # ==========================================================================
    # DECISION_REASON_CODES (many-to-many)
    # ==========================================================================
    op.create_table(
        "decision_reason_codes",
        sa.Column(
            "decision_id",
            sa.String(36),
            sa.ForeignKey("decisions.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "reason_code_id",
            sa.String(36),
            sa.ForeignKey("reason_codes.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )

    # ==========================================================================
    # AUDIT_LOGS TABLE (Immutable - triggers added in 004)
    # ==========================================================================
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.String(36), primary_key=True),
        # Timestamp (no updated_at - immutable)
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        # Actor
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id")),
        sa.Column("username", sa.String(50)),  # Denormalized
        sa.Column("ip_address", sa.String(45)),
        sa.Column("user_agent", sa.Text),
        # Action
        sa.Column("action", audit_action_enum, nullable=False),
        sa.Column("resource_type", sa.String(50), nullable=False),
        sa.Column("resource_id", sa.String(36)),
        # Details - JSONB for structured data
        sa.Column("description", sa.Text),
        sa.Column("before_value", postgresql.JSONB),
        sa.Column("after_value", postgresql.JSONB),
        sa.Column("extra_data", postgresql.JSONB),
        # Session context
        sa.Column("session_id", sa.String(36)),
    )
    op.create_index("ix_audit_logs_timestamp", "audit_logs", ["timestamp"])
    op.create_index("ix_audit_logs_user_id", "audit_logs", ["user_id"])
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])
    op.create_index("ix_audit_logs_resource_id", "audit_logs", ["resource_id"])
    op.create_index("ix_audit_logs_resource", "audit_logs", ["resource_type", "resource_id"])
    op.create_index("ix_audit_logs_user_action", "audit_logs", ["user_id", "action"])
    op.create_index("ix_audit_logs_timestamp_action", "audit_logs", ["timestamp", "action"])

    # ==========================================================================
    # ITEM_VIEWS TABLE (Immutable - triggers added in 004)
    # ==========================================================================
    op.create_table(
        "item_views",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("check_item_id", sa.String(36), sa.ForeignKey("check_items.id"), nullable=False),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("session_id", sa.String(36)),
        # View details
        sa.Column("view_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("view_ended_at", sa.DateTime(timezone=True)),
        sa.Column("duration_seconds", sa.Integer),
        # Interaction tracking
        sa.Column("front_image_viewed", sa.Boolean, default=False),
        sa.Column("back_image_viewed", sa.Boolean, default=False),
        sa.Column("zoom_used", sa.Boolean, default=False),
        sa.Column("magnifier_used", sa.Boolean, default=False),
        sa.Column("history_compared", sa.Boolean, default=False),
        sa.Column("ai_assists_viewed", sa.Boolean, default=False),
        sa.Column("context_panel_viewed", sa.Boolean, default=False),
        # Interaction summary - JSONB
        sa.Column("interaction_summary", postgresql.JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )
    op.create_index("ix_item_views_check_user", "item_views", ["check_item_id", "user_id"])

    # ==========================================================================
    # QUEUE_ASSIGNMENTS TABLE
    # ==========================================================================
    op.create_table(
        "queue_assignments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "queue_id",
            sa.String(36),
            sa.ForeignKey("queues.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("is_active", sa.Boolean, default=True),
        sa.Column("can_review", sa.Boolean, default=True),
        sa.Column("can_approve", sa.Boolean, default=False),
        sa.Column("max_concurrent_items", sa.Integer, default=10),
        sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("assigned_by_id", sa.String(36), sa.ForeignKey("users.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )

    # ==========================================================================
    # APPROVAL_ENTITLEMENTS TABLE
    # ==========================================================================
    op.create_table(
        "approval_entitlements",
        sa.Column("id", sa.String(36), primary_key=True),
        # Who has this entitlement
        sa.Column(
            "user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=True
        ),
        sa.Column(
            "role_id", sa.String(36), sa.ForeignKey("roles.id", ondelete="CASCADE"), nullable=True
        ),
        # Type of entitlement
        sa.Column("entitlement_type", approval_entitlement_type_enum, nullable=False),
        # Amount limits (NULL = no limit)
        sa.Column("min_amount", sa.Numeric(12, 2)),
        sa.Column("max_amount", sa.Numeric(12, 2)),
        # Scope restrictions (JSONB arrays, NULL = all allowed)
        sa.Column("allowed_account_types", postgresql.JSONB),
        sa.Column("allowed_queue_ids", postgresql.JSONB),
        sa.Column("allowed_risk_levels", postgresql.JSONB),
        sa.Column("allowed_business_lines", postgresql.JSONB),
        # Multi-tenant
        sa.Column("tenant_id", sa.String(36)),
        # Flexible conditions
        sa.Column("conditions", postgresql.JSONB),
        # Status
        sa.Column("is_active", sa.Boolean, default=True, nullable=False),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("effective_until", sa.DateTime(timezone=True)),
        # Audit
        sa.Column("granted_by_id", sa.String(36), sa.ForeignKey("users.id")),
        sa.Column("grant_reason", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )
    op.create_index("ix_approval_entitlements_user_id", "approval_entitlements", ["user_id"])
    op.create_index("ix_approval_entitlements_role_id", "approval_entitlements", ["role_id"])
    op.create_index("ix_approval_entitlements_tenant_id", "approval_entitlements", ["tenant_id"])
    op.create_index(
        "ix_approval_entitlements_active_type",
        "approval_entitlements",
        ["is_active", "entitlement_type"],
    )


def downgrade() -> None:
    """Drop all tables."""
    # Drop in reverse order of creation (respecting foreign keys)
    op.drop_table("approval_entitlements")
    op.drop_table("queue_assignments")
    op.drop_table("item_views")
    op.drop_table("audit_logs")
    op.drop_table("decision_reason_codes")
    op.drop_index("ix_check_items_pending_dual_control", table_name="check_items")
    op.drop_constraint("fk_check_items_pending_decision", "check_items", type_="foreignkey")
    op.drop_table("decisions")
    op.drop_table("reason_codes")
    op.drop_table("check_history")
    op.drop_table("check_images")
    op.drop_table("check_items")
    op.drop_table("policy_rules")
    op.drop_table("policy_versions")
    op.drop_table("policies")
    op.drop_table("queues")
    op.drop_table("user_sessions")
    op.drop_table("user_roles")
    op.drop_table("users")
    op.drop_table("role_permissions")
    op.drop_table("roles")
    op.drop_table("permissions")

    # Drop enums
    op.execute("DROP TYPE IF EXISTS approvalentitlementtype")
    op.execute("DROP TYPE IF EXISTS auditaction")
    op.execute("DROP TYPE IF EXISTS ruletype")
    op.execute("DROP TYPE IF EXISTS policystatus")
    op.execute("DROP TYPE IF EXISTS queuetype")
    op.execute("DROP TYPE IF EXISTS decisionaction")
    op.execute("DROP TYPE IF EXISTS decisiontype")
    op.execute("DROP TYPE IF EXISTS accounttype")
    op.execute("DROP TYPE IF EXISTS risklevel")
    op.execute("DROP TYPE IF EXISTS checkstatus")
