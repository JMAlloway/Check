"""Connector B - Batch Commit Schemas.

Pydantic schemas for:
- Bank connector configuration
- Batch creation and management
- File generation
- Acknowledgement processing
- Reconciliation reporting
"""

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.models.connector import (
    CommitDecisionType,
    HoldReasonCode,
    BatchStatus,
    RecordStatus,
    FileFormat,
    DeliveryMethod,
    ErrorCategory,
    AcknowledgementStatus,
)
from app.schemas.common import BaseSchema, TimestampSchema


# =============================================================================
# BANK CONFIGURATION SCHEMAS
# =============================================================================

class FieldConfigItem(BaseModel):
    """Configuration for a single field in the output file."""

    name: str = Field(..., description="Field name in output")
    source: str = Field(..., description="Source field name from record")
    position: int = Field(..., ge=1, description="Position in output (1-based)")
    length: int | None = Field(None, ge=1, description="Fixed width length (for fixed-width format)")
    align: str = Field("left", pattern="^(left|right)$", description="Alignment for fixed-width")
    pad: str = Field(" ", max_length=1, description="Padding character")
    format: str | None = Field(None, description="Format string (e.g., date format)")


class FieldConfig(BaseModel):
    """Complete field configuration."""

    fields: list[FieldConfigItem] = Field(..., min_length=1)


class DeliveryConfigSFTP(BaseModel):
    """SFTP delivery configuration."""

    host: str
    port: int = Field(22, ge=1, le=65535)
    path: str = Field("/", description="Remote directory path")
    username: str
    # password/key stored separately in secure vault


class DeliveryConfigSharedFolder(BaseModel):
    """Shared folder delivery configuration."""

    path: str = Field(..., description="UNC or local path")


class DeliveryConfigMessageQueue(BaseModel):
    """Message queue delivery configuration."""

    queue_name: str
    connection_string: str | None = None  # Stored separately


class BankConnectorConfigCreate(BaseModel):
    """Schema for creating bank connector configuration."""

    bank_id: str = Field(..., min_length=1, max_length=50)
    bank_name: str = Field(..., min_length=1, max_length=255)

    # File format
    file_format: FileFormat = FileFormat.CSV
    file_encoding: str = Field("UTF-8", max_length=20)
    file_line_ending: str = Field("CRLF", pattern="^(CRLF|LF)$")
    file_name_pattern: str = Field(
        "COMMIT_{BANK_ID}_{BATCH_ID}_{YYYYMMDD_HHMMSS}.csv",
        max_length=255
    )

    # Field configuration
    field_config: FieldConfig

    # Delivery
    delivery_method: DeliveryMethod = DeliveryMethod.SFTP
    delivery_config: dict[str, Any]

    # Acknowledgement
    expects_acknowledgement: bool = True
    ack_timeout_hours: int = Field(24, ge=1, le=168)
    ack_file_pattern: str | None = None

    # Security
    require_encryption: bool = True
    pgp_key_id: str | None = None

    # Operational
    max_records_per_file: int = Field(10000, ge=1, le=100000)
    include_header_row: bool = True
    include_trailer_row: bool = True
    include_checksum: bool = True

    # Notes
    include_notes: bool = False
    max_notes_length: int = Field(500, ge=0, le=2000)


class BankConnectorConfigUpdate(BaseModel):
    """Schema for updating bank connector configuration."""

    bank_name: str | None = None
    file_format: FileFormat | None = None
    file_encoding: str | None = None
    file_name_pattern: str | None = None
    field_config: FieldConfig | None = None
    delivery_method: DeliveryMethod | None = None
    delivery_config: dict[str, Any] | None = None
    expects_acknowledgement: bool | None = None
    ack_timeout_hours: int | None = None
    require_encryption: bool | None = None
    max_records_per_file: int | None = None
    include_notes: bool | None = None
    is_active: bool | None = None


class BankConnectorConfigResponse(TimestampSchema):
    """Schema for bank connector configuration response."""

    id: str
    tenant_id: str
    bank_id: str
    bank_name: str
    is_active: bool

    file_format: FileFormat
    file_encoding: str
    file_line_ending: str
    file_name_pattern: str
    field_config: dict[str, Any]

    delivery_method: DeliveryMethod
    # Note: delivery_config excluded for security (contains credentials)

    expects_acknowledgement: bool
    ack_timeout_hours: int
    ack_file_pattern: str | None

    require_encryption: bool
    max_records_per_file: int
    include_header_row: bool
    include_trailer_row: bool
    include_checksum: bool
    include_notes: bool
    max_notes_length: int

    created_by_user_id: str


# =============================================================================
# BATCH SCHEMAS
# =============================================================================

class BatchCreateRequest(BaseModel):
    """Request to create a new commit batch."""

    bank_config_id: str = Field(..., description="Bank configuration to use")
    decision_ids: list[str] = Field(
        ...,
        min_length=1,
        max_length=10000,
        description="List of decision IDs to include"
    )
    description: str | None = Field(None, max_length=500)


class BatchApprovalRequest(BaseModel):
    """Request to approve a batch."""

    approval_notes: str | None = Field(None, max_length=1000)


class BatchCancelRequest(BaseModel):
    """Request to cancel a batch."""

    reason: str = Field(..., min_length=10, max_length=1000)


class BatchSummary(BaseModel):
    """Summary of a batch for list views."""

    id: str
    batch_number: str
    status: BatchStatus
    total_records: int
    total_amount: Decimal
    release_count: int
    hold_count: int
    return_count: int
    reject_count: int
    escalate_count: int
    has_high_risk_items: bool
    high_risk_count: int
    created_at: datetime
    created_by_user_id: str
    approved_at: datetime | None
    approver_user_id: str | None
    file_generated_at: datetime | None
    transmitted_at: datetime | None
    ack_status: AcknowledgementStatus | None


class RecordSummary(BaseModel):
    """Summary of a commit record."""

    id: str
    sequence_number: int
    decision_id: str
    check_item_id: str
    item_id: str
    decision_hash: str
    status: RecordStatus
    decision_type: CommitDecisionType
    account_number_masked: str
    transaction_amount: Decimal
    reviewer_user_id: str
    approver_user_id: str
    decision_timestamp: datetime

    # Hold info (if applicable)
    hold_amount: Decimal | None
    hold_expiration_date: datetime | None
    hold_reason_code: HoldReasonCode | None

    # Error info (if failed)
    error_category: ErrorCategory | None
    error_code: str | None
    error_message: str | None

    # Resolution (if resolved)
    manually_resolved_at: datetime | None
    resolution_notes: str | None


class BatchResponse(TimestampSchema):
    """Full batch response with records."""

    id: str
    tenant_id: str
    batch_number: str
    bank_config_id: str
    description: str | None
    status: BatchStatus

    # Aggregates
    total_records: int
    total_amount: Decimal
    release_count: int
    hold_count: int
    return_count: int
    reject_count: int
    escalate_count: int
    has_high_risk_items: bool
    high_risk_count: int

    # Dual control
    created_by_user_id: str
    reviewer_user_id: str | None
    reviewed_at: datetime | None
    approver_user_id: str | None
    approved_at: datetime | None
    approval_notes: str | None

    # File generation
    file_generated_at: datetime | None
    file_name: str | None
    file_checksum: str | None
    file_size_bytes: int | None
    file_record_count: int | None
    batch_hash: str | None

    # Transmission
    transmitted_at: datetime | None
    transmission_id: str | None
    transmission_error: str | None

    # Acknowledgement
    acknowledged_at: datetime | None
    ack_status: AcknowledgementStatus | None
    ack_reference: str | None
    records_accepted: int | None
    records_rejected: int | None
    records_pending: int | None

    # Cancellation
    cancelled_at: datetime | None
    cancelled_by_user_id: str | None
    cancellation_reason: str | None

    # Records (included on detail view)
    records: list[RecordSummary] | None = None


class BatchFileResponse(BaseModel):
    """Response for file generation."""

    batch_id: str
    batch_number: str
    file_name: str
    file_checksum: str
    file_size_bytes: int
    record_count: int
    generated_at: datetime
    # File content returned separately as download


# =============================================================================
# ACKNOWLEDGEMENT SCHEMAS
# =============================================================================

class AcknowledgementRecordDetail(BaseModel):
    """Per-record acknowledgement detail."""

    decision_hash: str
    status: str = Field(..., pattern="^(accepted|rejected|pending)$")
    core_ref: str | None = None
    error_category: str | None = None
    error_code: str | None = None
    error: str | None = None


class AcknowledgementRequest(BaseModel):
    """Incoming acknowledgement from bank."""

    status: AcknowledgementStatus
    bank_reference_id: str | None = None
    bank_batch_id: str | None = None
    records: list[AcknowledgementRecordDetail]


class AcknowledgementResponse(TimestampSchema):
    """Acknowledgement response."""

    id: str
    batch_id: str
    ack_file_name: str | None
    ack_file_received_at: datetime
    status: AcknowledgementStatus
    bank_reference_id: str | None
    bank_batch_id: str | None
    total_records: int
    accepted_count: int
    rejected_count: int
    pending_count: int
    processed_at: datetime | None
    processed_by_user_id: str | None


# =============================================================================
# RECONCILIATION SCHEMAS
# =============================================================================

class ReconciliationReportRequest(BaseModel):
    """Request to generate reconciliation report."""

    report_date: datetime


class ReconciliationReportResponse(TimestampSchema):
    """Reconciliation report response."""

    id: str
    tenant_id: str
    report_date: datetime
    period_start: datetime
    period_end: datetime

    # Approved decisions
    decisions_approved: int
    decisions_amount_total: Decimal

    # File generation
    files_generated: int
    files_transmitted: int

    # Record processing
    records_included: int
    records_accepted: int
    records_rejected: int
    records_pending: int

    # Exceptions
    exceptions_new: int
    exceptions_resolved: int
    exceptions_outstanding: int

    # Amounts by type
    release_amount: Decimal
    hold_amount: Decimal
    return_amount: Decimal
    reject_amount: Decimal

    # Batches included
    batch_ids: list[str]

    # Report metadata
    generated_at: datetime
    generated_by_user_id: str | None
    approved_at: datetime | None
    approved_by_user_id: str | None


class RecordResolutionRequest(BaseModel):
    """Request to manually resolve a failed record."""

    resolution_notes: str = Field(..., min_length=10, max_length=2000)


# =============================================================================
# DASHBOARD SCHEMAS
# =============================================================================

class ConnectorDashboard(BaseModel):
    """Dashboard summary for connector status."""

    # Pending work
    batches_pending_approval: int
    batches_awaiting_acknowledgement: int
    records_failed_unresolved: int

    # Today's activity
    batches_created_today: int
    batches_transmitted_today: int
    records_processed_today: int
    records_accepted_today: int
    records_rejected_today: int

    # Amounts today
    total_amount_today: Decimal
    release_amount_today: Decimal
    hold_amount_today: Decimal
    return_amount_today: Decimal

    # SLA status
    batches_past_ack_deadline: int


class BatchConfirmationDialog(BaseModel):
    """Data for batch confirmation dialog."""

    batch_id: str
    batch_number: str
    total_records: int
    total_amount: Decimal

    # Breakdown
    release_count: int
    release_amount: Decimal
    hold_count: int
    hold_amount: Decimal
    return_count: int
    return_amount: Decimal
    reject_count: int
    reject_amount: Decimal
    escalate_count: int

    # Risk flags
    has_high_risk_items: bool
    high_risk_count: int
    high_risk_items: list[dict[str, Any]] | None = None

    # Confirmation requirements
    requires_dual_control: bool = True
    warnings: list[str] = []


# =============================================================================
# DEFAULT FIELD CONFIGURATIONS
# =============================================================================

# Standard CSV configuration for common bank integrations
DEFAULT_CSV_FIELD_CONFIG = FieldConfig(
    fields=[
        FieldConfigItem(name="bank_id", source="bank_id", position=1),
        FieldConfigItem(name="batch_id", source="batch_id", position=2),
        FieldConfigItem(name="sequence_number", source="sequence_number", position=3),
        FieldConfigItem(name="item_id", source="item_id", position=4),
        FieldConfigItem(name="decision_hash", source="decision_hash", position=5),
        FieldConfigItem(name="account_number", source="account_number", position=6),
        FieldConfigItem(name="routing_number", source="routing_number", position=7),
        FieldConfigItem(name="transaction_amount", source="transaction_amount", position=8),
        FieldConfigItem(name="decision_type", source="decision_type", position=9),
        FieldConfigItem(name="hold_amount", source="hold_amount", position=10),
        FieldConfigItem(name="hold_start_date", source="hold_start_date", position=11),
        FieldConfigItem(name="hold_expiration_date", source="hold_expiration_date", position=12),
        FieldConfigItem(name="hold_reason_code", source="hold_reason_code", position=13),
        FieldConfigItem(name="reviewer_user_id", source="reviewer_user_id", position=14),
        FieldConfigItem(name="approver_user_id", source="approver_user_id", position=15),
        FieldConfigItem(name="decision_timestamp", source="decision_timestamp", position=16),
        FieldConfigItem(name="decision_reference_id", source="decision_reference_id", position=17),
    ]
)

# Fixed-width for legacy integrations
DEFAULT_FIXED_WIDTH_FIELD_CONFIG = FieldConfig(
    fields=[
        FieldConfigItem(name="record_type", source="record_type", position=1, length=1, pad="0"),
        FieldConfigItem(name="bank_id", source="bank_id", position=2, length=10),
        FieldConfigItem(name="batch_id", source="batch_id", position=3, length=20),
        FieldConfigItem(name="sequence_number", source="sequence_number", position=4, length=6, align="right", pad="0"),
        FieldConfigItem(name="item_id", source="item_id", position=5, length=30),
        FieldConfigItem(name="account_number", source="account_number", position=6, length=20),
        FieldConfigItem(name="routing_number", source="routing_number", position=7, length=9),
        FieldConfigItem(name="transaction_amount", source="transaction_amount", position=8, length=12, align="right", pad="0"),
        FieldConfigItem(name="decision_type", source="decision_type", position=9, length=12),
        FieldConfigItem(name="hold_amount", source="hold_amount", position=10, length=12, align="right", pad="0"),
        FieldConfigItem(name="hold_expiration_date", source="hold_expiration_date", position=11, length=8),
        FieldConfigItem(name="hold_reason_code", source="hold_reason_code", position=12, length=20),
        FieldConfigItem(name="decision_timestamp", source="decision_timestamp", position=13, length=20),
        FieldConfigItem(name="decision_hash", source="decision_hash", position=14, length=64),
    ]
)
