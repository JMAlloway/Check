"""Connector B - Batch Commit Integration Models.

This module implements bank-auditable, regulator-defensible batch commit
integration for routing human-approved check review decisions to downstream
banking systems (e.g., Fiserv Premier).

Core Principles:
- Human decisioning only (no automated approvals)
- Dual control enforced (reviewer + approver)
- Immutable audit trail
- Idempotent file generation
- Reconciliation-first design
"""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.base import TimestampMixin, UUIDMixin


# =============================================================================
# ENUMERATIONS
# =============================================================================

class CommitDecisionType(str, Enum):
    """Decision types for batch commit records."""

    RELEASE = "release"              # Release funds / remove hold
    HOLD = "hold"                    # Place new hold
    EXTEND_HOLD = "extend_hold"      # Extend existing hold
    MODIFY_HOLD = "modify_hold"      # Modify hold amount/reason
    RETURN = "return"                # Return item
    REJECT = "reject"                # Reject item
    ESCALATE = "escalate"            # Escalate to ops/fraud


class HoldReasonCode(str, Enum):
    """Reg CC hold reason codes."""

    # Regulation CC Reason Codes
    NEW_ACCOUNT = "new_account"                      # Account less than 30 days old
    LARGE_DEPOSIT = "large_deposit"                  # Exceeds $5,525 threshold
    REDEPOSIT = "redeposit"                          # Previously returned item
    REPEATED_OVERDRAFT = "repeated_overdraft"        # Account overdrawn repeatedly
    REASONABLE_DOUBT = "reasonable_doubt"            # Reasonable cause to doubt collectibility
    EMERGENCY_CONDITIONS = "emergency_conditions"    # Emergency conditions
    NEXT_DAY_UNAVAILABLE = "next_day_unavailable"    # Next-day items exceeding limit
    OTHER = "other"                                  # Other (requires explanation)


class BatchStatus(str, Enum):
    """Batch lifecycle status."""

    PENDING = "pending"              # Awaiting approval
    APPROVED = "approved"            # Approved, ready for file generation
    GENERATING = "generating"        # File generation in progress
    GENERATED = "generated"          # File generated, awaiting transmission
    TRANSMITTED = "transmitted"      # File sent to bank middleware
    ACKNOWLEDGED = "acknowledged"    # Acknowledgement received
    PARTIALLY_PROCESSED = "partially_processed"  # Some records failed
    COMPLETED = "completed"          # All records processed successfully
    FAILED = "failed"                # Batch failed
    CANCELLED = "cancelled"          # Batch cancelled before processing


class RecordStatus(str, Enum):
    """Individual record status within a batch."""

    PENDING = "pending"              # Awaiting batch processing
    INCLUDED = "included"            # Included in generated file
    TRANSMITTED = "transmitted"      # Sent to bank
    ACCEPTED = "accepted"            # Accepted by core
    REJECTED = "rejected"            # Rejected by core
    FAILED = "failed"                # System failure
    RETRYING = "retrying"            # Retry in progress
    MANUALLY_RESOLVED = "manually_resolved"  # Manually resolved by ops


class FileFormat(str, Enum):
    """Supported output file formats."""

    CSV = "csv"
    FIXED_WIDTH = "fixed_width"
    XML = "xml"
    JSON = "json"  # For modern integrations


class DeliveryMethod(str, Enum):
    """File delivery methods."""

    SFTP = "sftp"
    SHARED_FOLDER = "shared_folder"
    MESSAGE_QUEUE = "message_queue"
    API_CALLBACK = "api_callback"


class ErrorCategory(str, Enum):
    """Error classification for troubleshooting."""

    VALIDATION = "validation"        # Bad data in request
    BUSINESS_RULE = "business_rule"  # Core rejected due to business rule
    SYSTEM = "system"                # Infrastructure failure
    TIMEOUT = "timeout"              # Communication timeout
    AUTH = "auth"                    # Authentication/authorization failure


class AcknowledgementStatus(str, Enum):
    """Status from bank acknowledgement."""

    ACCEPTED = "accepted"
    REJECTED = "rejected"
    PARTIALLY_PROCESSED = "partially_processed"
    PENDING = "pending"


# =============================================================================
# CONFIGURATION MODELS
# =============================================================================

class BankConnectorConfig(Base, UUIDMixin, TimestampMixin):
    """
    Bank-specific configuration for Connector B.

    Each bank/FI can have unique file format, field mappings,
    delivery settings, and integration parameters.
    """

    __tablename__ = "bank_connector_configs"

    # Bank identification
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    bank_id: Mapped[str] = mapped_column(String(50), nullable=False)
    bank_name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # File format configuration
    file_format: Mapped[FileFormat] = mapped_column(
        SQLEnum(FileFormat, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=FileFormat.CSV
    )
    file_encoding: Mapped[str] = mapped_column(String(20), default="UTF-8")
    file_line_ending: Mapped[str] = mapped_column(String(10), default="CRLF")  # CRLF or LF

    # File naming convention (supports placeholders)
    # e.g., "CHECK_COMMIT_{BANK_ID}_{BATCH_ID}_{TIMESTAMP}.csv"
    file_name_pattern: Mapped[str] = mapped_column(
        String(255),
        default="COMMIT_{BANK_ID}_{BATCH_ID}_{YYYYMMDD_HHMMSS}.csv"
    )

    # Field configuration (JSONB for flexibility)
    # Structure: {"fields": [{"name": "...", "position": 1, "length": 10, "format": "..."}]}
    field_config: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)

    # Delivery configuration
    delivery_method: Mapped[DeliveryMethod] = mapped_column(
        SQLEnum(DeliveryMethod, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=DeliveryMethod.SFTP
    )

    # Delivery settings (encrypted in production)
    # SFTP: {"host": "...", "port": 22, "path": "/inbound", "username": "..."}
    # Shared folder: {"path": "\\\\server\\share\\inbound"}
    # Message queue: {"queue_name": "...", "connection_string": "..."}
    delivery_config: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)

    # Acknowledgement settings
    expects_acknowledgement: Mapped[bool] = mapped_column(Boolean, default=True)
    ack_timeout_hours: Mapped[int] = mapped_column(Integer, default=24)
    ack_file_pattern: Mapped[str | None] = mapped_column(String(255))  # Pattern for ack files

    # Security settings
    require_encryption: Mapped[bool] = mapped_column(Boolean, default=True)
    pgp_key_id: Mapped[str | None] = mapped_column(String(100))

    # Operational settings
    max_records_per_file: Mapped[int] = mapped_column(Integer, default=10000)
    include_header_row: Mapped[bool] = mapped_column(Boolean, default=True)
    include_trailer_row: Mapped[bool] = mapped_column(Boolean, default=True)
    include_checksum: Mapped[bool] = mapped_column(Boolean, default=True)

    # Notes field configuration (whether to include free-text notes)
    include_notes: Mapped[bool] = mapped_column(Boolean, default=False)
    max_notes_length: Mapped[int] = mapped_column(Integer, default=500)

    # Audit
    created_by_user_id: Mapped[str] = mapped_column(String(36), nullable=False)
    last_modified_by_user_id: Mapped[str | None] = mapped_column(String(36))

    __table_args__ = (
        UniqueConstraint("tenant_id", "bank_id", name="uq_bank_connector_config_tenant_bank"),
        Index("ix_bank_connector_configs_active", "tenant_id", "is_active"),
    )


# =============================================================================
# BATCH MODELS
# =============================================================================

class CommitBatch(Base, UUIDMixin, TimestampMixin):
    """
    A batch of approved decisions ready for commit to downstream systems.

    Batches are immutable once approved - no records can be added/removed.
    Each batch generates exactly one output file.
    """

    __tablename__ = "commit_batches"

    # Tenant isolation
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    # Batch identification
    batch_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    bank_config_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("bank_connector_configs.id"),
        nullable=False
    )

    # Batch description
    description: Mapped[str | None] = mapped_column(Text)

    # Status tracking
    status: Mapped[BatchStatus] = mapped_column(
        SQLEnum(BatchStatus, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=BatchStatus.PENDING
    )

    # Aggregates (denormalized for performance)
    total_records: Mapped[int] = mapped_column(Integer, default=0)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0.00"))

    # Decision type counts
    release_count: Mapped[int] = mapped_column(Integer, default=0)
    hold_count: Mapped[int] = mapped_column(Integer, default=0)
    return_count: Mapped[int] = mapped_column(Integer, default=0)
    reject_count: Mapped[int] = mapped_column(Integer, default=0)
    escalate_count: Mapped[int] = mapped_column(Integer, default=0)

    # Risk flags (any items requiring special attention)
    has_high_risk_items: Mapped[bool] = mapped_column(Boolean, default=False)
    high_risk_count: Mapped[int] = mapped_column(Integer, default=0)

    # Dual control - REQUIRED
    created_by_user_id: Mapped[str] = mapped_column(String(36), nullable=False)
    reviewer_user_id: Mapped[str | None] = mapped_column(String(36))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    approver_user_id: Mapped[str | None] = mapped_column(String(36))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approval_notes: Mapped[str | None] = mapped_column(Text)

    # File generation
    file_generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    file_name: Mapped[str | None] = mapped_column(String(255))
    file_checksum: Mapped[str | None] = mapped_column(String(128))  # SHA-256
    file_size_bytes: Mapped[int | None] = mapped_column(Integer)
    file_record_count: Mapped[int | None] = mapped_column(Integer)

    # Deterministic batch hash for idempotency
    # Hash of all record decision hashes - if regenerated, must produce same hash
    batch_hash: Mapped[str | None] = mapped_column(String(64), index=True)

    # Transmission tracking
    transmitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    transmission_id: Mapped[str | None] = mapped_column(String(100))  # External reference
    transmission_error: Mapped[str | None] = mapped_column(Text)

    # Acknowledgement tracking
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ack_status: Mapped[AcknowledgementStatus | None] = mapped_column(
        SQLEnum(AcknowledgementStatus, values_callable=lambda x: [e.value for e in x])
    )
    ack_reference: Mapped[str | None] = mapped_column(String(100))

    # Reconciliation
    reconciled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reconciled_by_user_id: Mapped[str | None] = mapped_column(String(36))
    records_accepted: Mapped[int | None] = mapped_column(Integer)
    records_rejected: Mapped[int | None] = mapped_column(Integer)
    records_pending: Mapped[int | None] = mapped_column(Integer)

    # Cancellation
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_by_user_id: Mapped[str | None] = mapped_column(String(36))
    cancellation_reason: Mapped[str | None] = mapped_column(Text)

    # Relationships
    bank_config: Mapped["BankConnectorConfig"] = relationship()
    records: Mapped[list["CommitRecord"]] = relationship(
        back_populates="batch",
        cascade="all, delete-orphan"
    )
    acknowledgements: Mapped[list["BatchAcknowledgement"]] = relationship(
        back_populates="batch",
        cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_commit_batches_tenant_status", "tenant_id", "status"),
        Index("ix_commit_batches_created", "tenant_id", "created_at"),
        Index("ix_commit_batches_batch_number", "batch_number"),
    )


class CommitRecord(Base, UUIDMixin, TimestampMixin):
    """
    Individual record within a commit batch.

    Each record represents one decision to be committed to the core system.
    Records are linked to the original decision for full traceability.
    """

    __tablename__ = "commit_records"

    # Batch linkage
    batch_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("commit_batches.id", ondelete="CASCADE"),
        nullable=False
    )

    # Sequence within batch (for ordered processing)
    sequence_number: Mapped[int] = mapped_column(Integer, nullable=False)

    # Link to original decision (audit trail)
    decision_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("decisions.id"),
        nullable=False
    )
    check_item_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("check_items.id"),
        nullable=False
    )

    # Idempotency - unique hash of this decision record
    # Hash includes: decision_id, check_item_id, decision_type, amount, timestamps
    decision_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)

    # Record status
    status: Mapped[RecordStatus] = mapped_column(
        SQLEnum(RecordStatus, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=RecordStatus.PENDING
    )

    # Decision details (frozen at time of batch creation)
    decision_type: Mapped[CommitDecisionType] = mapped_column(
        SQLEnum(CommitDecisionType, values_callable=lambda x: [e.value for e in x]),
        nullable=False
    )

    # Bank/account identifiers
    bank_id: Mapped[str] = mapped_column(String(50), nullable=False)
    account_number_masked: Mapped[str] = mapped_column(String(20), nullable=False)
    routing_number: Mapped[str | None] = mapped_column(String(9))

    # Transaction details
    item_id: Mapped[str] = mapped_column(String(100), nullable=False)  # Check/processing ID
    transaction_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    # MICR data (if applicable)
    micr_line: Mapped[str | None] = mapped_column(String(100))

    # Hold parameters (for HOLD, EXTEND_HOLD, MODIFY_HOLD)
    hold_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    hold_start_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    hold_expiration_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    hold_reason_code: Mapped[HoldReasonCode | None] = mapped_column(
        SQLEnum(HoldReasonCode, values_callable=lambda x: [e.value for e in x])
    )
    hold_reason_text: Mapped[str | None] = mapped_column(String(255))

    # Decision makers (frozen for audit)
    reviewer_user_id: Mapped[str] = mapped_column(String(36), nullable=False)
    approver_user_id: Mapped[str] = mapped_column(String(36), nullable=False)
    decision_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Notes (if configured to include)
    notes: Mapped[str | None] = mapped_column(Text)

    # Evidence snapshot - CRITICAL for audit replay
    # Contains frozen state at decision time (policy results, AI flags, context values)
    evidence_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    # Processing results
    core_reference_id: Mapped[str | None] = mapped_column(String(100))  # Core system's ID
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Error handling
    error_category: Mapped[ErrorCategory | None] = mapped_column(
        SQLEnum(ErrorCategory, values_callable=lambda x: [e.value for e in x])
    )
    error_code: Mapped[str | None] = mapped_column(String(50))
    error_message: Mapped[str | None] = mapped_column(Text)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    last_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Manual resolution
    manually_resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    manually_resolved_by_user_id: Mapped[str | None] = mapped_column(String(36))
    resolution_notes: Mapped[str | None] = mapped_column(Text)

    # Relationships
    batch: Mapped["CommitBatch"] = relationship(back_populates="records")
    decision: Mapped["Decision"] = relationship()
    check_item: Mapped["CheckItem"] = relationship()

    __table_args__ = (
        Index("ix_commit_records_batch_sequence", "batch_id", "sequence_number"),
        Index("ix_commit_records_status", "status"),
        Index("ix_commit_records_decision", "decision_id"),
        UniqueConstraint("batch_id", "sequence_number", name="uq_commit_records_batch_sequence"),
    )


class BatchAcknowledgement(Base, UUIDMixin, TimestampMixin):
    """
    Acknowledgement received from bank middleware/core.

    Banks return acknowledgements indicating which records were
    accepted, rejected, or pending. This enables closed-loop reconciliation.
    """

    __tablename__ = "batch_acknowledgements"

    # Batch linkage
    batch_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("commit_batches.id", ondelete="CASCADE"),
        nullable=False
    )

    # Acknowledgement file info
    ack_file_name: Mapped[str | None] = mapped_column(String(255))
    ack_file_received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ack_file_checksum: Mapped[str | None] = mapped_column(String(128))

    # Overall status
    status: Mapped[AcknowledgementStatus] = mapped_column(
        SQLEnum(AcknowledgementStatus, values_callable=lambda x: [e.value for e in x]),
        nullable=False
    )

    # External reference from bank
    bank_reference_id: Mapped[str | None] = mapped_column(String(100))
    bank_batch_id: Mapped[str | None] = mapped_column(String(100))

    # Aggregate counts
    total_records: Mapped[int] = mapped_column(Integer, nullable=False)
    accepted_count: Mapped[int] = mapped_column(Integer, default=0)
    rejected_count: Mapped[int] = mapped_column(Integer, default=0)
    pending_count: Mapped[int] = mapped_column(Integer, default=0)

    # Per-record details (JSONB array)
    # Structure: [{"record_id": "...", "status": "...", "core_ref": "...", "error": "..."}]
    record_details: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)

    # Processing info
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    processed_by_user_id: Mapped[str | None] = mapped_column(String(36))
    processing_notes: Mapped[str | None] = mapped_column(Text)

    # Raw acknowledgement data (for debugging/audit)
    raw_ack_data: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    # Relationship
    batch: Mapped["CommitBatch"] = relationship(back_populates="acknowledgements")

    __table_args__ = (
        Index("ix_batch_acknowledgements_batch", "batch_id"),
        Index("ix_batch_acknowledgements_status", "status"),
    )


# =============================================================================
# RECONCILIATION MODELS
# =============================================================================

class ReconciliationReport(Base, UUIDMixin, TimestampMixin):
    """
    Daily reconciliation report tracking all batch activity.

    Provides visibility into:
    - Approved decisions
    - Files generated
    - Records processed/failed
    - Outstanding exceptions
    """

    __tablename__ = "reconciliation_reports"

    # Tenant isolation
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    # Report period
    report_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Approved decisions
    decisions_approved: Mapped[int] = mapped_column(Integer, default=0)
    decisions_amount_total: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=Decimal("0.00"))

    # File generation
    files_generated: Mapped[int] = mapped_column(Integer, default=0)
    files_transmitted: Mapped[int] = mapped_column(Integer, default=0)

    # Record processing
    records_included: Mapped[int] = mapped_column(Integer, default=0)
    records_accepted: Mapped[int] = mapped_column(Integer, default=0)
    records_rejected: Mapped[int] = mapped_column(Integer, default=0)
    records_pending: Mapped[int] = mapped_column(Integer, default=0)

    # Exceptions
    exceptions_new: Mapped[int] = mapped_column(Integer, default=0)
    exceptions_resolved: Mapped[int] = mapped_column(Integer, default=0)
    exceptions_outstanding: Mapped[int] = mapped_column(Integer, default=0)

    # Amounts by decision type
    release_amount: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=Decimal("0.00"))
    hold_amount: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=Decimal("0.00"))
    return_amount: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=Decimal("0.00"))
    reject_amount: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=Decimal("0.00"))

    # Detailed batch list
    batch_ids: Mapped[list[str]] = mapped_column(JSONB, default=list)

    # Report generation
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    generated_by_user_id: Mapped[str | None] = mapped_column(String(36))

    # Approval (for formal sign-off)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved_by_user_id: Mapped[str | None] = mapped_column(String(36))
    approval_notes: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        Index("ix_reconciliation_reports_tenant_date", "tenant_id", "report_date"),
        UniqueConstraint("tenant_id", "report_date", name="uq_reconciliation_report_tenant_date"),
    )


# =============================================================================
# IMPORTS FOR RELATIONSHIPS
# =============================================================================

from app.models.decision import Decision  # noqa: E402
from app.models.check import CheckItem  # noqa: E402
