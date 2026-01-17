"""Item Context Connector - SFTP Inbound Connector for Check Context Data.

This module implements an inbound connector that retrieves item context data
(account history, balances, check patterns) from bank SFTP sites via daily
flat file transfers.

The context data enriches CheckItems with account-level information needed
for risk assessment:
- Account tenure and balances
- Historical check patterns (averages, frequency)
- Exception history (returns, overdrafts)

File Flow:
1. Bank exports context data to SFTP site daily
2. Connector polls SFTP site on schedule
3. Files are downloaded, validated, and parsed
4. Context data is matched to CheckItems by account_id/external_item_id
5. CheckItems are enriched with context fields
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

class ContextConnectorStatus(str, Enum):
    """Connector operational status."""

    ACTIVE = "active"              # Connector is active and polling
    INACTIVE = "inactive"          # Manually disabled
    ERROR = "error"                # Last operation failed
    TESTING = "testing"            # In test mode (doesn't update items)


class FileFormat(str, Enum):
    """Supported input file formats."""

    CSV = "csv"
    TSV = "tsv"
    FIXED_WIDTH = "fixed_width"
    PIPE_DELIMITED = "pipe"


class ImportStatus(str, Enum):
    """Import job status."""

    PENDING = "pending"            # Queued for processing
    DOWNLOADING = "downloading"    # Downloading from SFTP
    VALIDATING = "validating"      # Validating file format/content
    PROCESSING = "processing"      # Processing records
    COMPLETED = "completed"        # Successfully completed
    PARTIAL = "partial"            # Completed with some errors
    FAILED = "failed"              # Failed
    CANCELLED = "cancelled"        # Manually cancelled


class RecordStatus(str, Enum):
    """Individual record import status."""

    PENDING = "pending"
    MATCHED = "matched"            # Matched to existing CheckItem
    APPLIED = "applied"            # Context applied to CheckItem
    NOT_FOUND = "not_found"        # No matching CheckItem found
    DUPLICATE = "duplicate"        # Duplicate record in file
    INVALID = "invalid"            # Failed validation
    ERROR = "error"                # Processing error


# =============================================================================
# CONNECTOR CONFIGURATION
# =============================================================================

class ItemContextConnector(Base, UUIDMixin, TimestampMixin):
    """
    SFTP connector configuration for inbound item context data.

    Each tenant can have multiple connectors for different source systems
    or file types.
    """

    __tablename__ = "item_context_connectors"

    # Tenant isolation
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    # Connector identification
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    source_system: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Source system identifier (e.g., 'fiserv', 'q2', 'jack_henry')"
    )

    # Status
    status: Mapped[ContextConnectorStatus] = mapped_column(
        SQLEnum(ContextConnectorStatus, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=ContextConnectorStatus.INACTIVE
    )
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=False)

    # SFTP Connection Settings
    sftp_host: Mapped[str] = mapped_column(String(255), nullable=False)
    sftp_port: Mapped[int] = mapped_column(Integer, default=22)
    sftp_username: Mapped[str] = mapped_column(String(100), nullable=False)
    # Password stored encrypted - see app/core/encryption.py
    sftp_password_encrypted: Mapped[str | None] = mapped_column(Text)
    # Alternative: SSH key authentication
    sftp_private_key_encrypted: Mapped[str | None] = mapped_column(Text)
    sftp_key_passphrase_encrypted: Mapped[str | None] = mapped_column(Text)

    # SFTP Paths
    sftp_remote_path: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        default="/outbound",
        comment="Remote directory to poll for files"
    )
    sftp_archive_path: Mapped[str | None] = mapped_column(
        String(500),
        comment="Remote path to move processed files (null = delete after processing)"
    )
    sftp_error_path: Mapped[str | None] = mapped_column(
        String(500),
        comment="Remote path for files that failed processing"
    )

    # File Pattern & Format
    file_pattern: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        default="*.csv",
        comment="Glob pattern for files to process (e.g., 'CONTEXT_*.csv')"
    )
    file_format: Mapped[FileFormat] = mapped_column(
        SQLEnum(FileFormat, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=FileFormat.CSV
    )
    file_encoding: Mapped[str] = mapped_column(String(20), default="UTF-8")
    file_delimiter: Mapped[str | None] = mapped_column(
        String(5),
        comment="Delimiter for CSV/delimited files (default: comma)"
    )
    has_header_row: Mapped[bool] = mapped_column(Boolean, default=True)
    skip_rows: Mapped[int] = mapped_column(
        Integer,
        default=0,
        comment="Number of rows to skip at start of file (after header)"
    )

    # Field Mapping Configuration
    # Maps file columns to CheckItem context fields
    # Structure: {"account_id": {"column": 0, "name": "ACCT_NUM"}, ...}
    field_mapping: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict
    )

    # Fixed-width field positions (for FIXED_WIDTH format)
    # Structure: {"account_id": {"start": 0, "end": 15}, ...}
    fixed_width_config: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    # Matching Configuration
    # How to match file records to CheckItems
    match_by_external_item_id: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        comment="Match by external_item_id (check-level) vs account_id (account-level)"
    )
    match_field: Mapped[str] = mapped_column(
        String(50),
        default="account_id",
        comment="CheckItem field to match against"
    )

    # Schedule Configuration
    schedule_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    schedule_cron: Mapped[str | None] = mapped_column(
        String(100),
        comment="Cron expression (e.g., '0 6 * * *' for 6 AM daily)"
    )
    schedule_timezone: Mapped[str] = mapped_column(String(50), default="America/New_York")

    # Processing Settings
    max_records_per_file: Mapped[int] = mapped_column(Integer, default=100000)
    batch_size: Mapped[int] = mapped_column(
        Integer,
        default=1000,
        comment="Records to process per database transaction"
    )
    fail_on_validation_error: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        comment="Fail entire import if any record fails validation"
    )
    update_existing: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        comment="Update context if CheckItem already has context data"
    )

    # Connection Health
    last_connection_test_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_connection_test_success: Mapped[bool | None] = mapped_column(Boolean)
    last_connection_test_error: Mapped[str | None] = mapped_column(Text)

    # Last Successful Import
    last_import_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_import_file: Mapped[str | None] = mapped_column(String(255))
    last_import_records: Mapped[int | None] = mapped_column(Integer)

    # Error Tracking
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0)
    last_error_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error_message: Mapped[str | None] = mapped_column(Text)

    # Audit
    created_by_user_id: Mapped[str] = mapped_column(String(36), nullable=False)
    last_modified_by_user_id: Mapped[str | None] = mapped_column(String(36))

    # Relationships
    imports: Mapped[list["ItemContextImport"]] = relationship(
        back_populates="connector",
        cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "name",
            name="uq_item_context_connectors_tenant_name"
        ),
        Index("ix_item_context_connectors_tenant_enabled", "tenant_id", "is_enabled"),
        Index("ix_item_context_connectors_status", "status"),
    )


# =============================================================================
# IMPORT TRACKING
# =============================================================================

class ItemContextImport(Base, UUIDMixin, TimestampMixin):
    """
    Tracks individual import jobs/files.

    Each file processed creates one import record for audit
    and troubleshooting.
    """

    __tablename__ = "item_context_imports"

    # Connector reference
    connector_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("item_context_connectors.id", ondelete="CASCADE"),
        nullable=False
    )
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    # File information
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_size_bytes: Mapped[int | None] = mapped_column(Integer)
    file_checksum: Mapped[str | None] = mapped_column(String(128))  # SHA-256
    file_modified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Status
    status: Mapped[ImportStatus] = mapped_column(
        SQLEnum(ImportStatus, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=ImportStatus.PENDING
    )

    # Timing
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_seconds: Mapped[int | None] = mapped_column(Integer)

    # Record counts
    total_records: Mapped[int] = mapped_column(Integer, default=0)
    matched_records: Mapped[int] = mapped_column(Integer, default=0)
    applied_records: Mapped[int] = mapped_column(Integer, default=0)
    not_found_records: Mapped[int] = mapped_column(Integer, default=0)
    duplicate_records: Mapped[int] = mapped_column(Integer, default=0)
    invalid_records: Mapped[int] = mapped_column(Integer, default=0)
    error_records: Mapped[int] = mapped_column(Integer, default=0)

    # Error handling
    error_message: Mapped[str | None] = mapped_column(Text)
    error_details: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    # Trigger type
    triggered_by: Mapped[str] = mapped_column(
        String(20),
        default="manual",
        comment="'manual', 'scheduled', or 'api'"
    )
    triggered_by_user_id: Mapped[str | None] = mapped_column(String(36))

    # Processing metadata
    processing_metadata: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        comment="Additional processing info (validation warnings, etc.)"
    )

    # Relationships
    connector: Mapped["ItemContextConnector"] = relationship(back_populates="imports")
    records: Mapped[list["ItemContextImportRecord"]] = relationship(
        back_populates="import_job",
        cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_item_context_imports_connector_status", "connector_id", "status"),
        Index("ix_item_context_imports_tenant_created", "tenant_id", "created_at"),
        Index("ix_item_context_imports_file", "file_name"),
    )


class ItemContextImportRecord(Base, UUIDMixin, TimestampMixin):
    """
    Individual record from an import file.

    Stores details for each row processed, enabling
    troubleshooting of matching/application issues.

    Note: Only stores error/not_found records by default to save space.
    Successful records are counted but not stored individually unless
    configured for full audit.
    """

    __tablename__ = "item_context_import_records"

    # Import reference
    import_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("item_context_imports.id", ondelete="CASCADE"),
        nullable=False
    )

    # Position in file
    row_number: Mapped[int] = mapped_column(Integer, nullable=False)

    # Status
    status: Mapped[RecordStatus] = mapped_column(
        SQLEnum(RecordStatus, values_callable=lambda x: [e.value for e in x]),
        nullable=False
    )

    # Matching identifiers from file
    account_id_from_file: Mapped[str | None] = mapped_column(String(50))
    external_item_id_from_file: Mapped[str | None] = mapped_column(String(100))

    # Matched CheckItem (if found)
    check_item_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("check_items.id", ondelete="SET NULL")
    )

    # Context data from file (stored for troubleshooting)
    context_data: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    # Error details
    error_code: Mapped[str | None] = mapped_column(String(50))
    error_message: Mapped[str | None] = mapped_column(Text)

    # Raw row data (for debugging, optional)
    raw_row_data: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        Index("ix_item_context_import_records_import_status", "import_id", "status"),
        Index("ix_item_context_import_records_check_item", "check_item_id"),
    )


# =============================================================================
# FIELD MAPPING TEMPLATES
# =============================================================================

# Standard field mapping templates for common core systems
FIELD_MAPPING_TEMPLATES = {
    "fiserv_premier": {
        "account_id": {"column": 0, "name": "ACCT_NBR"},
        "external_item_id": {"column": 1, "name": "ITEM_ID"},
        "account_tenure_days": {"column": 2, "name": "ACCT_AGE_DAYS", "type": "int"},
        "current_balance": {"column": 3, "name": "CURR_BAL", "type": "decimal"},
        "average_balance_30d": {"column": 4, "name": "AVG_BAL_30", "type": "decimal"},
        "avg_check_amount_30d": {"column": 5, "name": "AVG_CHK_30", "type": "decimal"},
        "avg_check_amount_90d": {"column": 6, "name": "AVG_CHK_90", "type": "decimal"},
        "avg_check_amount_365d": {"column": 7, "name": "AVG_CHK_365", "type": "decimal"},
        "check_std_dev_30d": {"column": 8, "name": "CHK_STDDEV_30", "type": "decimal"},
        "max_check_amount_90d": {"column": 9, "name": "MAX_CHK_90", "type": "decimal"},
        "check_frequency_30d": {"column": 10, "name": "CHK_CNT_30", "type": "int"},
        "returned_item_count_90d": {"column": 11, "name": "RTN_CNT_90", "type": "int"},
        "exception_count_90d": {"column": 12, "name": "EXC_CNT_90", "type": "int"},
        "relationship_id": {"column": 13, "name": "REL_ID"},
    },
    "jack_henry_silverlake": {
        "account_id": {"column": 0, "name": "AccountNumber"},
        "external_item_id": {"column": 1, "name": "ItemSeqNum"},
        "account_tenure_days": {"column": 2, "name": "DaysOpen", "type": "int"},
        "current_balance": {"column": 3, "name": "CurrentBalance", "type": "decimal"},
        "average_balance_30d": {"column": 4, "name": "AvgBal30Day", "type": "decimal"},
        "avg_check_amount_30d": {"column": 5, "name": "AvgCheckAmt30", "type": "decimal"},
        "avg_check_amount_90d": {"column": 6, "name": "AvgCheckAmt90", "type": "decimal"},
        "check_frequency_30d": {"column": 7, "name": "CheckCount30", "type": "int"},
        "returned_item_count_90d": {"column": 8, "name": "ReturnCount90", "type": "int"},
    },
    "q2_core": {
        "account_id": {"column": 0, "name": "acct_id"},
        "external_item_id": {"column": 1, "name": "tran_id"},
        "account_tenure_days": {"column": 2, "name": "acct_age", "type": "int"},
        "current_balance": {"column": 3, "name": "ledger_bal", "type": "decimal"},
        "average_balance_30d": {"column": 4, "name": "avg_bal_30d", "type": "decimal"},
        "avg_check_amount_30d": {"column": 5, "name": "avg_chk_30d", "type": "decimal"},
        "check_frequency_30d": {"column": 6, "name": "chk_freq_30d", "type": "int"},
        "returned_item_count_90d": {"column": 7, "name": "nsf_cnt_90d", "type": "int"},
    },
}
