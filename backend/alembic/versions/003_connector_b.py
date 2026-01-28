"""Connector B - Batch Commit Integration

Revision ID: 003_connector_b
Revises: 002_fraud_intelligence
Create Date: 2024-01-15

This migration adds tables for Connector B, a file-based batch commit
integration for routing human-approved check review decisions to
downstream banking systems.

Core Principles:
- Human decisioning only (no automated approvals)
- Dual control enforced (reviewer + approver)
- Immutable audit trail
- Idempotent file generation
- Reconciliation-first design
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "003_connector_b"
down_revision = "002_fraud"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ==========================================================================
    # EVIDENCE_SNAPSHOT NOTE
    # ==========================================================================
    # Note: decisions.evidence_snapshot is now created in 001_initial_schema
    # No need to add it here.
    # ==========================================================================

    # ==========================================================================
    # BANK CONNECTOR CONFIGURATION
    # ==========================================================================
    op.create_table(
        "bank_connector_configs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
        # Bank identification
        sa.Column("tenant_id", sa.String(36), nullable=False, index=True),
        sa.Column("bank_id", sa.String(50), nullable=False),
        sa.Column("bank_name", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean(), default=True),
        # File format configuration
        sa.Column(
            "file_format",
            sa.Enum("csv", "fixed_width", "xml", "json", name="fileformat"),
            nullable=False,
            server_default="csv",
        ),
        sa.Column("file_encoding", sa.String(20), default="UTF-8"),
        sa.Column("file_line_ending", sa.String(10), default="CRLF"),
        sa.Column("file_name_pattern", sa.String(255), nullable=False),
        # Field configuration (JSONB)
        sa.Column("field_config", postgresql.JSONB(), nullable=False),
        # Delivery configuration
        sa.Column(
            "delivery_method",
            sa.Enum(
                "sftp", "shared_folder", "message_queue", "api_callback", name="deliverymethod"
            ),
            nullable=False,
            server_default="sftp",
        ),
        sa.Column("delivery_config", postgresql.JSONB(), nullable=False),
        # Acknowledgement settings
        sa.Column("expects_acknowledgement", sa.Boolean(), default=True),
        sa.Column("ack_timeout_hours", sa.Integer(), default=24),
        sa.Column("ack_file_pattern", sa.String(255)),
        # Security settings
        sa.Column("require_encryption", sa.Boolean(), default=True),
        sa.Column("pgp_key_id", sa.String(100)),
        # Operational settings
        sa.Column("max_records_per_file", sa.Integer(), default=10000),
        sa.Column("include_header_row", sa.Boolean(), default=True),
        sa.Column("include_trailer_row", sa.Boolean(), default=True),
        sa.Column("include_checksum", sa.Boolean(), default=True),
        # Notes configuration
        sa.Column("include_notes", sa.Boolean(), default=False),
        sa.Column("max_notes_length", sa.Integer(), default=500),
        # Audit
        sa.Column("created_by_user_id", sa.String(36), nullable=False),
        sa.Column("last_modified_by_user_id", sa.String(36)),
        sa.UniqueConstraint("tenant_id", "bank_id", name="uq_bank_connector_config_tenant_bank"),
    )
    op.create_index(
        "ix_bank_connector_configs_active", "bank_connector_configs", ["tenant_id", "is_active"]
    )

    # ==========================================================================
    # COMMIT BATCHES
    # ==========================================================================
    op.create_table(
        "commit_batches",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
        # Tenant isolation
        sa.Column("tenant_id", sa.String(36), nullable=False, index=True),
        # Batch identification
        sa.Column("batch_number", sa.String(50), unique=True, nullable=False),
        sa.Column(
            "bank_config_id",
            sa.String(36),
            sa.ForeignKey("bank_connector_configs.id"),
            nullable=False,
        ),
        sa.Column("description", sa.Text()),
        # Status tracking
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "approved",
                "generating",
                "generated",
                "transmitted",
                "acknowledged",
                "partially_processed",
                "completed",
                "failed",
                "cancelled",
                name="batchstatus",
            ),
            nullable=False,
            server_default="pending",
        ),
        # Aggregates
        sa.Column("total_records", sa.Integer(), default=0),
        sa.Column("total_amount", sa.Numeric(14, 2), default=0),
        # Decision type counts
        sa.Column("release_count", sa.Integer(), default=0),
        sa.Column("hold_count", sa.Integer(), default=0),
        sa.Column("return_count", sa.Integer(), default=0),
        sa.Column("reject_count", sa.Integer(), default=0),
        sa.Column("escalate_count", sa.Integer(), default=0),
        # Risk flags
        sa.Column("has_high_risk_items", sa.Boolean(), default=False),
        sa.Column("high_risk_count", sa.Integer(), default=0),
        # Dual control - REQUIRED
        sa.Column("created_by_user_id", sa.String(36), nullable=False),
        sa.Column("reviewer_user_id", sa.String(36)),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("approver_user_id", sa.String(36)),
        sa.Column("approved_at", sa.DateTime(timezone=True)),
        sa.Column("approval_notes", sa.Text()),
        # File generation
        sa.Column("file_generated_at", sa.DateTime(timezone=True)),
        sa.Column("file_name", sa.String(255)),
        sa.Column("file_checksum", sa.String(128)),
        sa.Column("file_size_bytes", sa.Integer()),
        sa.Column("file_record_count", sa.Integer()),
        sa.Column("batch_hash", sa.String(64), index=True),
        # Transmission tracking
        sa.Column("transmitted_at", sa.DateTime(timezone=True)),
        sa.Column("transmission_id", sa.String(100)),
        sa.Column("transmission_error", sa.Text()),
        # Acknowledgement tracking
        sa.Column("acknowledged_at", sa.DateTime(timezone=True)),
        sa.Column(
            "ack_status",
            sa.Enum(
                "accepted",
                "rejected",
                "partially_processed",
                "pending",
                name="acknowledgementstatus",
            ),
        ),
        sa.Column("ack_reference", sa.String(100)),
        # Reconciliation
        sa.Column("reconciled_at", sa.DateTime(timezone=True)),
        sa.Column("reconciled_by_user_id", sa.String(36)),
        sa.Column("records_accepted", sa.Integer()),
        sa.Column("records_rejected", sa.Integer()),
        sa.Column("records_pending", sa.Integer()),
        # Cancellation
        sa.Column("cancelled_at", sa.DateTime(timezone=True)),
        sa.Column("cancelled_by_user_id", sa.String(36)),
        sa.Column("cancellation_reason", sa.Text()),
    )
    op.create_index("ix_commit_batches_tenant_status", "commit_batches", ["tenant_id", "status"])
    op.create_index("ix_commit_batches_created", "commit_batches", ["tenant_id", "created_at"])
    op.create_index("ix_commit_batches_batch_number", "commit_batches", ["batch_number"])

    # ==========================================================================
    # COMMIT RECORDS
    # ==========================================================================
    op.create_table(
        "commit_records",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
        # Batch linkage
        sa.Column(
            "batch_id",
            sa.String(36),
            sa.ForeignKey("commit_batches.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("sequence_number", sa.Integer(), nullable=False),
        # Link to original decision (audit trail)
        sa.Column("decision_id", sa.String(36), sa.ForeignKey("decisions.id"), nullable=False),
        sa.Column("check_item_id", sa.String(36), sa.ForeignKey("check_items.id"), nullable=False),
        # Idempotency
        sa.Column("decision_hash", sa.String(64), unique=True, nullable=False),
        # Record status
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "included",
                "transmitted",
                "accepted",
                "rejected",
                "failed",
                "retrying",
                "manually_resolved",
                name="recordstatus",
            ),
            nullable=False,
            server_default="pending",
        ),
        # Decision details
        sa.Column(
            "decision_type",
            sa.Enum(
                "release",
                "hold",
                "extend_hold",
                "modify_hold",
                "return",
                "reject",
                "escalate",
                name="commitdecisiontype",
            ),
            nullable=False,
        ),
        # Bank/account identifiers
        sa.Column("bank_id", sa.String(50), nullable=False),
        sa.Column("account_number_masked", sa.String(20), nullable=False),
        sa.Column("routing_number", sa.String(9)),
        # Transaction details
        sa.Column("item_id", sa.String(100), nullable=False),
        sa.Column("transaction_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("micr_line", sa.String(100)),
        # Hold parameters
        sa.Column("hold_amount", sa.Numeric(12, 2)),
        sa.Column("hold_start_date", sa.DateTime(timezone=True)),
        sa.Column("hold_expiration_date", sa.DateTime(timezone=True)),
        sa.Column(
            "hold_reason_code",
            sa.Enum(
                "new_account",
                "large_deposit",
                "redeposit",
                "repeated_overdraft",
                "reasonable_doubt",
                "emergency_conditions",
                "next_day_unavailable",
                "other",
                name="holdreasoncode",
            ),
        ),
        sa.Column("hold_reason_text", sa.String(255)),
        # Decision makers (frozen for audit)
        sa.Column("reviewer_user_id", sa.String(36), nullable=False),
        sa.Column("approver_user_id", sa.String(36), nullable=False),
        sa.Column("decision_timestamp", sa.DateTime(timezone=True), nullable=False),
        # Notes
        sa.Column("notes", sa.Text()),
        # Evidence snapshot - CRITICAL for audit replay
        sa.Column("evidence_snapshot", postgresql.JSONB()),
        # Processing results
        sa.Column("core_reference_id", sa.String(100)),
        sa.Column("processed_at", sa.DateTime(timezone=True)),
        # Error handling
        sa.Column(
            "error_category",
            sa.Enum(
                "validation", "business_rule", "system", "timeout", "auth", name="errorcategory"
            ),
        ),
        sa.Column("error_code", sa.String(50)),
        sa.Column("error_message", sa.Text()),
        sa.Column("retry_count", sa.Integer(), default=0),
        sa.Column("last_retry_at", sa.DateTime(timezone=True)),
        # Manual resolution
        sa.Column("manually_resolved_at", sa.DateTime(timezone=True)),
        sa.Column("manually_resolved_by_user_id", sa.String(36)),
        sa.Column("resolution_notes", sa.Text()),
        sa.UniqueConstraint("batch_id", "sequence_number", name="uq_commit_records_batch_sequence"),
    )
    op.create_index(
        "ix_commit_records_batch_sequence", "commit_records", ["batch_id", "sequence_number"]
    )
    op.create_index("ix_commit_records_status", "commit_records", ["status"])
    op.create_index("ix_commit_records_decision", "commit_records", ["decision_id"])

    # ==========================================================================
    # BATCH ACKNOWLEDGEMENTS
    # ==========================================================================
    op.create_table(
        "batch_acknowledgements",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
        # Batch linkage
        sa.Column(
            "batch_id",
            sa.String(36),
            sa.ForeignKey("commit_batches.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # Acknowledgement file info
        sa.Column("ack_file_name", sa.String(255)),
        sa.Column("ack_file_received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ack_file_checksum", sa.String(128)),
        # Overall status
        sa.Column(
            "status",
            sa.Enum(
                "accepted",
                "rejected",
                "partially_processed",
                "pending",
                name="acknowledgementstatus",
                create_type=False,
            ),
            nullable=False,
        ),
        # External reference from bank
        sa.Column("bank_reference_id", sa.String(100)),
        sa.Column("bank_batch_id", sa.String(100)),
        # Aggregate counts
        sa.Column("total_records", sa.Integer(), nullable=False),
        sa.Column("accepted_count", sa.Integer(), default=0),
        sa.Column("rejected_count", sa.Integer(), default=0),
        sa.Column("pending_count", sa.Integer(), default=0),
        # Per-record details (JSONB array)
        sa.Column("record_details", postgresql.JSONB(), nullable=False),
        # Processing info
        sa.Column("processed_at", sa.DateTime(timezone=True)),
        sa.Column("processed_by_user_id", sa.String(36)),
        sa.Column("processing_notes", sa.Text()),
        # Raw acknowledgement data
        sa.Column("raw_ack_data", postgresql.JSONB()),
    )
    op.create_index("ix_batch_acknowledgements_batch", "batch_acknowledgements", ["batch_id"])
    op.create_index("ix_batch_acknowledgements_status", "batch_acknowledgements", ["status"])

    # ==========================================================================
    # RECONCILIATION REPORTS
    # ==========================================================================
    op.create_table(
        "reconciliation_reports",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
        # Tenant isolation
        sa.Column("tenant_id", sa.String(36), nullable=False, index=True),
        # Report period
        sa.Column("report_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        # Approved decisions
        sa.Column("decisions_approved", sa.Integer(), default=0),
        sa.Column("decisions_amount_total", sa.Numeric(16, 2), default=0),
        # File generation
        sa.Column("files_generated", sa.Integer(), default=0),
        sa.Column("files_transmitted", sa.Integer(), default=0),
        # Record processing
        sa.Column("records_included", sa.Integer(), default=0),
        sa.Column("records_accepted", sa.Integer(), default=0),
        sa.Column("records_rejected", sa.Integer(), default=0),
        sa.Column("records_pending", sa.Integer(), default=0),
        # Exceptions
        sa.Column("exceptions_new", sa.Integer(), default=0),
        sa.Column("exceptions_resolved", sa.Integer(), default=0),
        sa.Column("exceptions_outstanding", sa.Integer(), default=0),
        # Amounts by decision type
        sa.Column("release_amount", sa.Numeric(16, 2), default=0),
        sa.Column("hold_amount", sa.Numeric(16, 2), default=0),
        sa.Column("return_amount", sa.Numeric(16, 2), default=0),
        sa.Column("reject_amount", sa.Numeric(16, 2), default=0),
        # Detailed batch list
        sa.Column("batch_ids", postgresql.JSONB(), default=list),
        # Report generation
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("generated_by_user_id", sa.String(36)),
        # Approval
        sa.Column("approved_at", sa.DateTime(timezone=True)),
        sa.Column("approved_by_user_id", sa.String(36)),
        sa.Column("approval_notes", sa.Text()),
        sa.UniqueConstraint(
            "tenant_id", "report_date", name="uq_reconciliation_report_tenant_date"
        ),
    )
    op.create_index(
        "ix_reconciliation_reports_tenant_date",
        "reconciliation_reports",
        ["tenant_id", "report_date"],
    )


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_table("reconciliation_reports")
    op.drop_table("batch_acknowledgements")
    op.drop_table("commit_records")
    op.drop_table("commit_batches")
    op.drop_table("bank_connector_configs")

    # Drop enums
    op.execute("DROP TYPE IF EXISTS errorcategory")
    op.execute("DROP TYPE IF EXISTS holdreasoncode")
    op.execute("DROP TYPE IF EXISTS commitdecisiontype")
    op.execute("DROP TYPE IF EXISTS recordstatus")
    op.execute("DROP TYPE IF EXISTS acknowledgementstatus")
    op.execute("DROP TYPE IF EXISTS batchstatus")
    op.execute("DROP TYPE IF EXISTS deliverymethod")
    op.execute("DROP TYPE IF EXISTS fileformat")

    # Note: decisions.evidence_snapshot is managed by 001_initial_schema, not dropped here
    # Note: users.tenant_id is managed by 001_initial_schema, not dropped here
