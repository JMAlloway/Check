"""Security incident and breach notification models."""

from datetime import datetime
from enum import Enum
from typing import Any

from sqlalchemy import Boolean, DateTime, Enum as SQLEnum, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.base import TimestampMixin, UUIDMixin


class IncidentSeverity(str, Enum):
    """Severity levels for security incidents."""

    LOW = "low"           # Minor policy violation, no data exposure
    MEDIUM = "medium"     # Potential data exposure, limited scope
    HIGH = "high"         # Confirmed data exposure, significant scope
    CRITICAL = "critical" # Major breach, regulatory notification required


class IncidentStatus(str, Enum):
    """Status of a security incident."""

    DRAFT = "draft"           # Initial report, under investigation
    CONFIRMED = "confirmed"   # Breach confirmed
    CONTAINED = "contained"   # Breach contained, remediation in progress
    RESOLVED = "resolved"     # Incident resolved
    CLOSED = "closed"         # Post-incident review complete


class IncidentType(str, Enum):
    """Types of security incidents."""

    UNAUTHORIZED_ACCESS = "unauthorized_access"
    DATA_BREACH = "data_breach"
    ACCOUNT_COMPROMISE = "account_compromise"
    INSIDER_THREAT = "insider_threat"
    MALWARE = "malware"
    PHISHING = "phishing"
    DENIAL_OF_SERVICE = "denial_of_service"
    DATA_LOSS = "data_loss"
    POLICY_VIOLATION = "policy_violation"
    SUSPICIOUS_ACTIVITY = "suspicious_activity"
    AUDIT_FAILURE = "audit_failure"
    OTHER = "other"


class NotificationStatus(str, Enum):
    """Status of breach notification."""

    PENDING = "pending"
    SENT = "sent"
    ACKNOWLEDGED = "acknowledged"
    FAILED = "failed"


class SecurityIncident(Base, UUIDMixin, TimestampMixin):
    """Security incident record for breach tracking and notification.

    Supports the breach notification workflow required for:
    - State breach notification laws (varies by state)
    - Banking regulator notifications (OCC, FDIC, etc.)
    - Internal incident response procedures
    - SOC 2 incident management controls
    """

    __tablename__ = "security_incidents"

    # Tenant isolation
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    # Incident classification
    incident_type: Mapped[IncidentType] = mapped_column(
        SQLEnum(IncidentType, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    severity: Mapped[IncidentSeverity] = mapped_column(
        SQLEnum(IncidentSeverity, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    status: Mapped[IncidentStatus] = mapped_column(
        SQLEnum(IncidentStatus, values_callable=lambda x: [e.value for e in x]),
        default=IncidentStatus.DRAFT,
        nullable=False,
    )

    # Incident details
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    # Discovery and timeline
    discovered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    occurred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    contained_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Impact assessment
    affected_users_count: Mapped[int | None] = mapped_column()
    affected_records_count: Mapped[int | None] = mapped_column()
    data_types_exposed: Mapped[list[str] | None] = mapped_column(JSONB)  # e.g., ["ssn", "account_number"]
    pii_exposed: Mapped[bool] = mapped_column(Boolean, default=False)
    financial_data_exposed: Mapped[bool] = mapped_column(Boolean, default=False)

    # Regulatory notification requirements
    requires_regulator_notification: Mapped[bool] = mapped_column(Boolean, default=False)
    requires_customer_notification: Mapped[bool] = mapped_column(Boolean, default=False)
    notification_deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Reporter and assignee
    reported_by_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"))
    assigned_to_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"))

    # Investigation details
    root_cause: Mapped[str | None] = mapped_column(Text)
    remediation_steps: Mapped[str | None] = mapped_column(Text)
    lessons_learned: Mapped[str | None] = mapped_column(Text)

    # Evidence and documentation
    evidence: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    related_audit_log_ids: Mapped[list[str] | None] = mapped_column(JSONB)

    # External references
    external_ticket_id: Mapped[str | None] = mapped_column(String(100))
    regulator_case_number: Mapped[str | None] = mapped_column(String(100))

    __table_args__ = (
        Index("ix_security_incidents_tenant_status", "tenant_id", "status"),
        Index("ix_security_incidents_severity", "severity"),
        Index("ix_security_incidents_discovered", "discovered_at"),
    )


class BreachNotification(Base, UUIDMixin, TimestampMixin):
    """Record of breach notifications sent to various parties.

    Tracks notifications to:
    - Affected customers
    - Regulatory bodies
    - Law enforcement
    - Internal stakeholders
    - Credit bureaus (if required)
    """

    __tablename__ = "breach_notifications"

    # Link to incident
    incident_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("security_incidents.id"),
        nullable=False,
    )

    # Notification target
    notification_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # Types: "customer", "regulator_occ", "regulator_fdic", "regulator_state",
    #        "law_enforcement", "credit_bureau", "internal"
    recipient: Mapped[str] = mapped_column(String(255), nullable=False)

    # Notification content
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # Status tracking
    status: Mapped[NotificationStatus] = mapped_column(
        SQLEnum(NotificationStatus, values_callable=lambda x: [e.value for e in x]),
        default=NotificationStatus.PENDING,
        nullable=False,
    )
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failure_reason: Mapped[str | None] = mapped_column(Text)

    # Sent by
    sent_by_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"))

    # Delivery details
    delivery_method: Mapped[str | None] = mapped_column(String(50))  # email, mail, portal
    delivery_reference: Mapped[str | None] = mapped_column(String(255))  # tracking number, etc.

    __table_args__ = (
        Index("ix_breach_notifications_incident", "incident_id"),
        Index("ix_breach_notifications_status", "status"),
    )


class IncidentUpdate(Base, UUIDMixin, TimestampMixin):
    """Timeline entry for incident updates and communications."""

    __tablename__ = "incident_updates"

    # Link to incident
    incident_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("security_incidents.id"),
        nullable=False,
    )

    # Update details
    update_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # Types: "status_change", "assignment", "note", "evidence_added",
    #        "notification_sent", "escalation", "resolution"
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # Who made the update
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)

    # Previous/new values for status changes
    previous_value: Mapped[str | None] = mapped_column(String(255))
    new_value: Mapped[str | None] = mapped_column(String(255))

    __table_args__ = (Index("ix_incident_updates_incident", "incident_id"),)
