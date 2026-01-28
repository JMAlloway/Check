"""Image Connector (Connector A) - Bank-Side Image Connector Management.

This module implements the SaaS-side management of bank-side image connectors.
Connectors run inside the bank network and serve check images securely.

Each connector:
- Has a unique ID and base URL
- Uses RS256 JWT authentication
- Is tied to a specific tenant
- Can be enabled/disabled
- Supports public key rotation

The SaaS issues short-lived JWTs (60-120s) for image requests.
"""

from datetime import datetime
from enum import Enum
from typing import Any

from app.db.session import Base
from app.models.base import TimestampMixin, UUIDMixin
from sqlalchemy import (
    Boolean,
    DateTime,
)
from sqlalchemy import Enum as SQLEnum
from sqlalchemy import (
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship


class ConnectorStatus(str, Enum):
    """Connector operational status."""

    ACTIVE = "active"  # Connector is active and accepting requests
    INACTIVE = "inactive"  # Connector is disabled (manual)
    UNREACHABLE = "unreachable"  # Health check failed
    ROTATING = "rotating"  # Key rotation in progress


class ImageConnector(Base, UUIDMixin, TimestampMixin):
    """
    SaaS-side configuration for a bank-side image connector.

    Each tenant may have one or more connectors configured,
    though typically there's one per bank location/data center.
    """

    __tablename__ = "image_connectors"

    # Tenant isolation
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    # Connector identification
    connector_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Unique identifier matching the connector's CONNECTOR_ID",
    )
    name: Mapped[str] = mapped_column(
        String(255), nullable=False, comment="Human-friendly name (e.g., 'Primary DC Connector')"
    )
    description: Mapped[str | None] = mapped_column(Text)

    # Network configuration
    base_url: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        comment="Base URL for the connector (e.g., 'https://connector.bank.local:8443')",
    )

    # Status
    status: Mapped[ConnectorStatus] = mapped_column(
        SQLEnum(ConnectorStatus, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=ConnectorStatus.INACTIVE,
    )
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=False)

    # JWT Authentication Keys (RS256)
    # Primary key currently in use
    public_key_pem: Mapped[str] = mapped_column(
        Text, nullable=False, comment="RSA public key in PEM format for JWT signing"
    )
    public_key_id: Mapped[str] = mapped_column(
        String(100), nullable=False, comment="Key identifier (for key rotation)"
    )
    public_key_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), comment="When this key expires (null = never)"
    )

    # Secondary key for rotation (overlap period)
    secondary_public_key_pem: Mapped[str | None] = mapped_column(Text)
    secondary_public_key_id: Mapped[str | None] = mapped_column(String(100))
    secondary_public_key_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )

    # JWT token settings
    token_expiry_seconds: Mapped[int] = mapped_column(
        Integer, default=120, comment="JWT token expiry in seconds (60-300)"
    )
    jwt_issuer: Mapped[str] = mapped_column(
        String(100), default="check-review-saas", comment="Issuer claim for JWTs"
    )

    # Health check
    last_health_check_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_health_check_status: Mapped[str | None] = mapped_column(String(20))
    last_health_check_latency_ms: Mapped[int | None] = mapped_column(Integer)
    health_check_failure_count: Mapped[int] = mapped_column(Integer, default=0)
    last_successful_request_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Connector metadata (from health check)
    connector_version: Mapped[str | None] = mapped_column(String(50))
    connector_mode: Mapped[str | None] = mapped_column(String(20))
    allowed_roots: Mapped[list[str] | None] = mapped_column(JSONB)

    # Operational settings
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=30)
    max_retries: Mapped[int] = mapped_column(Integer, default=2)
    circuit_breaker_threshold: Mapped[int] = mapped_column(
        Integer, default=5, comment="Consecutive failures before circuit opens"
    )
    circuit_breaker_timeout_seconds: Mapped[int] = mapped_column(
        Integer, default=60, comment="Seconds before retrying after circuit opens"
    )

    # Priority for load balancing (lower = higher priority)
    priority: Mapped[int] = mapped_column(Integer, default=100)

    # Audit
    created_by_user_id: Mapped[str] = mapped_column(String(36), nullable=False)
    last_modified_by_user_id: Mapped[str | None] = mapped_column(String(36))

    # Connection test results
    last_connection_test_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_connection_test_result: Mapped[str | None] = mapped_column(Text)
    last_connection_test_success: Mapped[bool | None] = mapped_column(Boolean)

    __table_args__ = (
        UniqueConstraint("tenant_id", "connector_id", name="uq_image_connectors_tenant_connector"),
        Index("ix_image_connectors_tenant_enabled", "tenant_id", "is_enabled"),
        Index("ix_image_connectors_status", "status"),
    )


class ConnectorAuditLog(Base, UUIDMixin, TimestampMixin):
    """
    Audit log for connector configuration changes.

    Tracks all administrative actions on connectors.
    """

    __tablename__ = "connector_audit_logs"

    # Connector reference
    connector_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("image_connectors.id", ondelete="CASCADE"), nullable=False
    )

    # Action details
    action: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Action type: created, updated, enabled, disabled, key_rotated, deleted",
    )
    user_id: Mapped[str] = mapped_column(String(36), nullable=False)

    # Change details
    changes: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, comment="Before/after values for changed fields"
    )

    # Request context
    ip_address: Mapped[str | None] = mapped_column(String(45))
    user_agent: Mapped[str | None] = mapped_column(String(500))

    __table_args__ = (
        Index("ix_connector_audit_logs_connector", "connector_id"),
        Index("ix_connector_audit_logs_user", "user_id"),
        Index("ix_connector_audit_logs_created", "created_at"),
    )


class ConnectorRequestLog(Base, UUIDMixin):
    """
    Log of image requests made through connectors.

    Used for monitoring, debugging, and usage analytics.
    Note: Does NOT store image data or raw paths.
    """

    __tablename__ = "connector_request_logs"

    # Timing
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )

    # Connector reference
    connector_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("image_connectors.id", ondelete="SET NULL"), nullable=True
    )
    connector_name: Mapped[str] = mapped_column(String(255), nullable=False)

    # Request details
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(36), nullable=False)
    request_type: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="by-handle, by-item, lookup"
    )

    # Item identification (for tracking, not secrets)
    trace_number: Mapped[str | None] = mapped_column(String(50))
    check_date: Mapped[str | None] = mapped_column(String(10))
    path_hash: Mapped[str | None] = mapped_column(String(64))  # SHA256
    side: Mapped[str | None] = mapped_column(String(10))

    # Response details
    success: Mapped[bool] = mapped_column(Boolean, nullable=False)
    status_code: Mapped[int | None] = mapped_column(Integer)
    error_code: Mapped[str | None] = mapped_column(String(50))
    error_message: Mapped[str | None] = mapped_column(String(500))

    # Metrics
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    bytes_received: Mapped[int | None] = mapped_column(Integer)
    from_cache: Mapped[bool | None] = mapped_column(Boolean)

    # Correlation
    correlation_id: Mapped[str] = mapped_column(String(36), nullable=False)

    __table_args__ = (
        Index("ix_connector_request_logs_tenant_time", "tenant_id", "requested_at"),
        Index("ix_connector_request_logs_connector", "connector_id"),
        Index("ix_connector_request_logs_correlation", "correlation_id"),
    )
