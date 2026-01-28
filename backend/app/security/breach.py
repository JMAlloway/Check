"""Breach notification service.

Implements a comprehensive breach notification workflow for:
- State breach notification law compliance (varies by state)
- Banking regulator notification (OCC, FDIC, state regulators)
- Customer notification
- Internal escalation
- Evidence preservation

Key regulatory timelines:
- State laws: Typically 30-90 days for customer notification
- Banking regulators: 36 hours for significant incidents (OCC guidelines)
- GDPR (if applicable): 72 hours for supervisory authority
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from app.audit.service import AuditService
from app.models.audit import AuditAction
from app.security.models import (
    BreachNotification,
    IncidentSeverity,
    IncidentStatus,
    IncidentType,
    IncidentUpdate,
    NotificationStatus,
    SecurityIncident,
)
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("security.breach")


class BreachNotificationService:
    """Service for managing security incidents and breach notifications.

    Provides a complete workflow for:
    1. Incident reporting and classification
    2. Impact assessment
    3. Notification requirements determination
    4. Stakeholder notification tracking
    5. Incident resolution and documentation
    """

    # Notification deadlines by type (in hours)
    NOTIFICATION_DEADLINES = {
        "regulator_occ": 36,  # OCC cyber incident notification
        "regulator_fdic": 36,  # FDIC notification
        "regulator_state": 72,  # State banking regulator
        "customer": 720,  # 30 days (varies by state)
        "law_enforcement": 72,  # When required
        "credit_bureau": 720,  # When SSN/credit data exposed
    }

    # Data types that trigger specific notification requirements
    NOTIFICATION_TRIGGERS = {
        "ssn": ["customer", "credit_bureau"],
        "account_number": ["customer", "regulator_occ"],
        "routing_number": ["regulator_occ"],
        "credit_card": ["customer", "credit_bureau"],
        "password": ["customer"],
        "mfa_secret": ["customer"],
    }

    def __init__(self, db: AsyncSession):
        self.db = db
        self.audit_service = AuditService(db)

    async def create_incident(
        self,
        tenant_id: str,
        incident_type: IncidentType,
        severity: IncidentSeverity,
        title: str,
        description: str,
        discovered_at: datetime,
        reported_by_id: str,
        reported_by_username: str,
        occurred_at: datetime | None = None,
        affected_users_count: int | None = None,
        affected_records_count: int | None = None,
        data_types_exposed: list[str] | None = None,
        evidence: dict | None = None,
        ip_address: str | None = None,
    ) -> SecurityIncident:
        """Create a new security incident report.

        This is the entry point for the breach notification workflow.
        """
        # Determine if PII or financial data is exposed
        pii_exposed = False
        financial_data_exposed = False

        if data_types_exposed:
            pii_types = {"ssn", "name", "address", "phone", "email", "dob"}
            financial_types = {"account_number", "routing_number", "credit_card", "balance"}

            pii_exposed = bool(set(data_types_exposed) & pii_types)
            financial_data_exposed = bool(set(data_types_exposed) & financial_types)

        # Determine notification requirements based on severity and data exposed
        requires_regulator = severity in (IncidentSeverity.HIGH, IncidentSeverity.CRITICAL)
        requires_customer = pii_exposed or financial_data_exposed

        # Calculate notification deadline (most urgent)
        notification_deadline = None
        if requires_regulator:
            notification_deadline = discovered_at + timedelta(hours=36)
        elif requires_customer:
            notification_deadline = discovered_at + timedelta(hours=720)  # 30 days

        incident = SecurityIncident(
            tenant_id=tenant_id,
            incident_type=incident_type,
            severity=severity,
            status=IncidentStatus.DRAFT,
            title=title,
            description=description,
            discovered_at=discovered_at,
            occurred_at=occurred_at,
            affected_users_count=affected_users_count,
            affected_records_count=affected_records_count,
            data_types_exposed=data_types_exposed,
            pii_exposed=pii_exposed,
            financial_data_exposed=financial_data_exposed,
            requires_regulator_notification=requires_regulator,
            requires_customer_notification=requires_customer,
            notification_deadline=notification_deadline,
            reported_by_id=reported_by_id,
            evidence=evidence,
        )

        self.db.add(incident)
        await self.db.flush()

        # Create initial update
        await self._add_update(
            incident.id,
            reported_by_id,
            "note",
            f"Incident reported: {title}",
        )

        # Audit log
        await self.audit_service.log(
            action=AuditAction.SUSPICIOUS_ACTIVITY,
            resource_type="security_incident",
            resource_id=str(incident.id),
            user_id=reported_by_id,
            username=reported_by_username,
            ip_address=ip_address,
            description=f"Security incident reported: {title}",
            metadata={
                "incident_type": incident_type.value,
                "severity": severity.value,
                "pii_exposed": pii_exposed,
                "financial_data_exposed": financial_data_exposed,
            },
            tenant_id=tenant_id,
        )

        # Log to security event stream
        logger.critical(
            f"SECURITY INCIDENT: {title}",
            extra={
                "event_type": "security.incident.created",
                "incident_id": str(incident.id),
                "incident_type": incident_type.value,
                "severity": severity.value,
                "pii_exposed": pii_exposed,
                "financial_data_exposed": financial_data_exposed,
                "requires_regulator_notification": requires_regulator,
                "notification_deadline": (
                    notification_deadline.isoformat() if notification_deadline else None
                ),
                "is_security_event": True,
                "soc2_control": "CC7.2",
            },
        )

        return incident

    async def confirm_incident(
        self,
        incident_id: str,
        user_id: str,
        username: str,
        root_cause: str | None = None,
        additional_data_types: list[str] | None = None,
        ip_address: str | None = None,
    ) -> SecurityIncident:
        """Confirm a security incident after investigation.

        This transitions the incident from DRAFT to CONFIRMED status
        and triggers notification workflow.
        """
        incident = await self._get_incident(incident_id)
        if not incident:
            raise ValueError(f"Incident not found: {incident_id}")

        if incident.status != IncidentStatus.DRAFT:
            raise ValueError(f"Incident is not in DRAFT status: {incident.status}")

        # Update status
        old_status = incident.status
        incident.status = IncidentStatus.CONFIRMED
        if root_cause:
            incident.root_cause = root_cause

        # Update data types if new ones discovered
        if additional_data_types:
            current_types = incident.data_types_exposed or []
            incident.data_types_exposed = list(set(current_types + additional_data_types))

            # Recalculate notification requirements
            self._recalculate_notification_requirements(incident)

        # Add update
        await self._add_update(
            incident_id,
            user_id,
            "status_change",
            f"Incident confirmed. Root cause: {root_cause or 'Under investigation'}",
            previous_value=old_status.value,
            new_value=IncidentStatus.CONFIRMED.value,
        )

        # Create required notifications
        await self._create_required_notifications(incident, user_id)

        # Audit log
        await self.audit_service.log(
            action=AuditAction.SUSPICIOUS_ACTIVITY,
            resource_type="security_incident",
            resource_id=str(incident.id),
            user_id=user_id,
            username=username,
            ip_address=ip_address,
            description=f"Security incident confirmed: {incident.title}",
            metadata={
                "previous_status": old_status.value,
                "new_status": IncidentStatus.CONFIRMED.value,
                "root_cause": root_cause,
            },
            tenant_id=incident.tenant_id,
        )

        logger.critical(
            f"SECURITY INCIDENT CONFIRMED: {incident.title}",
            extra={
                "event_type": "security.incident.confirmed",
                "incident_id": str(incident.id),
                "severity": incident.severity.value,
                "requires_regulator_notification": incident.requires_regulator_notification,
                "requires_customer_notification": incident.requires_customer_notification,
                "is_security_event": True,
                "soc2_control": "CC7.2",
            },
        )

        return incident

    async def contain_incident(
        self,
        incident_id: str,
        user_id: str,
        username: str,
        containment_actions: str,
        ip_address: str | None = None,
    ) -> SecurityIncident:
        """Mark incident as contained."""
        incident = await self._get_incident(incident_id)
        if not incident:
            raise ValueError(f"Incident not found: {incident_id}")

        old_status = incident.status
        incident.status = IncidentStatus.CONTAINED
        incident.contained_at = datetime.now(timezone.utc)

        await self._add_update(
            incident_id,
            user_id,
            "status_change",
            f"Incident contained. Actions taken: {containment_actions}",
            previous_value=old_status.value,
            new_value=IncidentStatus.CONTAINED.value,
        )

        # Audit log
        await self.audit_service.log(
            action=AuditAction.SUSPICIOUS_ACTIVITY,
            resource_type="security_incident",
            resource_id=str(incident.id),
            user_id=user_id,
            username=username,
            ip_address=ip_address,
            description=f"Security incident contained: {incident.title}",
            metadata={
                "containment_actions": containment_actions,
            },
            tenant_id=incident.tenant_id,
        )

        logger.warning(
            f"SECURITY INCIDENT CONTAINED: {incident.title}",
            extra={
                "event_type": "security.incident.contained",
                "incident_id": str(incident.id),
                "is_security_event": True,
            },
        )

        return incident

    async def resolve_incident(
        self,
        incident_id: str,
        user_id: str,
        username: str,
        remediation_steps: str,
        lessons_learned: str | None = None,
        ip_address: str | None = None,
    ) -> SecurityIncident:
        """Resolve a security incident."""
        incident = await self._get_incident(incident_id)
        if not incident:
            raise ValueError(f"Incident not found: {incident_id}")

        old_status = incident.status
        incident.status = IncidentStatus.RESOLVED
        incident.resolved_at = datetime.now(timezone.utc)
        incident.remediation_steps = remediation_steps
        if lessons_learned:
            incident.lessons_learned = lessons_learned

        await self._add_update(
            incident_id,
            user_id,
            "resolution",
            f"Incident resolved. Remediation: {remediation_steps}",
            previous_value=old_status.value,
            new_value=IncidentStatus.RESOLVED.value,
        )

        # Audit log
        await self.audit_service.log(
            action=AuditAction.SUSPICIOUS_ACTIVITY,
            resource_type="security_incident",
            resource_id=str(incident.id),
            user_id=user_id,
            username=username,
            ip_address=ip_address,
            description=f"Security incident resolved: {incident.title}",
            metadata={
                "remediation_steps": remediation_steps,
                "lessons_learned": lessons_learned,
            },
            tenant_id=incident.tenant_id,
        )

        logger.info(
            f"SECURITY INCIDENT RESOLVED: {incident.title}",
            extra={
                "event_type": "security.incident.resolved",
                "incident_id": str(incident.id),
                "is_security_event": True,
            },
        )

        return incident

    async def send_notification(
        self,
        notification_id: str,
        user_id: str,
        username: str,
        delivery_method: str = "email",
        delivery_reference: str | None = None,
        ip_address: str | None = None,
    ) -> BreachNotification:
        """Mark a notification as sent."""
        result = await self.db.execute(
            select(BreachNotification).where(BreachNotification.id == notification_id)
        )
        notification = result.scalar_one_or_none()

        if not notification:
            raise ValueError(f"Notification not found: {notification_id}")

        notification.status = NotificationStatus.SENT
        notification.sent_at = datetime.now(timezone.utc)
        notification.sent_by_id = user_id
        notification.delivery_method = delivery_method
        notification.delivery_reference = delivery_reference

        # Get incident for audit
        incident = await self._get_incident(notification.incident_id)

        # Add incident update
        await self._add_update(
            notification.incident_id,
            user_id,
            "notification_sent",
            f"Notification sent to {notification.recipient} via {delivery_method}",
        )

        # Audit log
        if incident:
            await self.audit_service.log(
                action=AuditAction.SUSPICIOUS_ACTIVITY,
                resource_type="breach_notification",
                resource_id=str(notification.id),
                user_id=user_id,
                username=username,
                ip_address=ip_address,
                description=f"Breach notification sent: {notification.notification_type}",
                metadata={
                    "incident_id": notification.incident_id,
                    "notification_type": notification.notification_type,
                    "recipient": notification.recipient,
                    "delivery_method": delivery_method,
                },
                tenant_id=incident.tenant_id,
            )

        logger.info(
            f"BREACH NOTIFICATION SENT: {notification.notification_type}",
            extra={
                "event_type": "security.notification.sent",
                "notification_id": str(notification.id),
                "incident_id": notification.incident_id,
                "notification_type": notification.notification_type,
                "is_security_event": True,
                "soc2_control": "CC7.2",
            },
        )

        return notification

    async def get_pending_notifications(self, tenant_id: str) -> list[dict]:
        """Get all pending notifications that need to be sent."""
        result = await self.db.execute(
            select(BreachNotification, SecurityIncident)
            .join(SecurityIncident, BreachNotification.incident_id == SecurityIncident.id)
            .where(
                SecurityIncident.tenant_id == tenant_id,
                BreachNotification.status == NotificationStatus.PENDING,
            )
            .order_by(SecurityIncident.notification_deadline.asc())
        )

        notifications = []
        for notification, incident in result.all():
            notifications.append(
                {
                    "notification_id": str(notification.id),
                    "incident_id": str(incident.id),
                    "incident_title": incident.title,
                    "severity": incident.severity.value,
                    "notification_type": notification.notification_type,
                    "recipient": notification.recipient,
                    "subject": notification.subject,
                    "deadline": (
                        incident.notification_deadline.isoformat()
                        if incident.notification_deadline
                        else None
                    ),
                    "is_overdue": (
                        incident.notification_deadline
                        and incident.notification_deadline < datetime.now(timezone.utc)
                    ),
                }
            )

        return notifications

    async def get_incident_timeline(self, incident_id: str) -> list[dict]:
        """Get the full timeline of an incident."""
        result = await self.db.execute(
            select(IncidentUpdate)
            .where(IncidentUpdate.incident_id == incident_id)
            .order_by(IncidentUpdate.created_at.asc())
        )

        updates = []
        for update in result.scalars().all():
            updates.append(
                {
                    "id": str(update.id),
                    "type": update.update_type,
                    "content": update.content,
                    "user_id": update.user_id,
                    "previous_value": update.previous_value,
                    "new_value": update.new_value,
                    "created_at": update.created_at.isoformat(),
                }
            )

        return updates

    async def get_active_incidents(self, tenant_id: str) -> list[SecurityIncident]:
        """Get all active (non-closed) incidents for a tenant."""
        result = await self.db.execute(
            select(SecurityIncident)
            .where(
                SecurityIncident.tenant_id == tenant_id,
                SecurityIncident.status != IncidentStatus.CLOSED,
            )
            .order_by(SecurityIncident.severity.desc(), SecurityIncident.discovered_at.desc())
        )
        return list(result.scalars().all())

    async def _get_incident(self, incident_id: str) -> SecurityIncident | None:
        """Get incident by ID."""
        result = await self.db.execute(
            select(SecurityIncident).where(SecurityIncident.id == incident_id)
        )
        return result.scalar_one_or_none()

    async def _add_update(
        self,
        incident_id: str,
        user_id: str,
        update_type: str,
        content: str,
        previous_value: str | None = None,
        new_value: str | None = None,
    ) -> IncidentUpdate:
        """Add an update to the incident timeline."""
        update = IncidentUpdate(
            incident_id=incident_id,
            user_id=user_id,
            update_type=update_type,
            content=content,
            previous_value=previous_value,
            new_value=new_value,
        )
        self.db.add(update)
        await self.db.flush()
        return update

    def _recalculate_notification_requirements(self, incident: SecurityIncident) -> None:
        """Recalculate notification requirements based on exposed data types."""
        if not incident.data_types_exposed:
            return

        required_notifications = set()
        for data_type in incident.data_types_exposed:
            if data_type in self.NOTIFICATION_TRIGGERS:
                required_notifications.update(self.NOTIFICATION_TRIGGERS[data_type])

        # Update flags
        incident.requires_regulator_notification = bool(
            {"regulator_occ", "regulator_fdic"} & required_notifications
        ) or incident.severity in (IncidentSeverity.HIGH, IncidentSeverity.CRITICAL)

        incident.requires_customer_notification = "customer" in required_notifications

    async def _create_required_notifications(
        self,
        incident: SecurityIncident,
        user_id: str,
    ) -> list[BreachNotification]:
        """Create pending notifications based on incident requirements."""
        notifications = []

        if incident.requires_regulator_notification:
            # OCC notification
            notifications.append(
                await self._create_notification(
                    incident,
                    "regulator_occ",
                    "Office of the Comptroller of the Currency",
                    f"Cyber Security Incident Report: {incident.title}",
                    self._generate_regulator_notification_content(incident),
                )
            )

            # State regulator
            notifications.append(
                await self._create_notification(
                    incident,
                    "regulator_state",
                    "State Banking Regulator",
                    f"Security Incident Notification: {incident.title}",
                    self._generate_regulator_notification_content(incident),
                )
            )

        if incident.requires_customer_notification:
            notifications.append(
                await self._create_notification(
                    incident,
                    "customer",
                    "Affected Customers",
                    f"Important Security Notice from Your Bank",
                    self._generate_customer_notification_content(incident),
                )
            )

        # Internal notification always required
        notifications.append(
            await self._create_notification(
                incident,
                "internal",
                "Security Team",
                f"[{incident.severity.value.upper()}] Security Incident: {incident.title}",
                self._generate_internal_notification_content(incident),
            )
        )

        return notifications

    async def _create_notification(
        self,
        incident: SecurityIncident,
        notification_type: str,
        recipient: str,
        subject: str,
        content: str,
    ) -> BreachNotification:
        """Create a pending notification."""
        notification = BreachNotification(
            incident_id=str(incident.id),
            notification_type=notification_type,
            recipient=recipient,
            subject=subject,
            content=content,
            status=NotificationStatus.PENDING,
        )
        self.db.add(notification)
        await self.db.flush()
        return notification

    def _generate_regulator_notification_content(self, incident: SecurityIncident) -> str:
        """Generate content for regulatory notification."""
        return f"""
CYBER SECURITY INCIDENT REPORT

Incident ID: {incident.id}
Date Discovered: {incident.discovered_at.isoformat()}
Severity: {incident.severity.value.upper()}

INCIDENT SUMMARY:
{incident.description}

IMPACT ASSESSMENT:
- Affected Users: {incident.affected_users_count or 'Under investigation'}
- Affected Records: {incident.affected_records_count or 'Under investigation'}
- PII Exposed: {'Yes' if incident.pii_exposed else 'No'}
- Financial Data Exposed: {'Yes' if incident.financial_data_exposed else 'No'}
- Data Types: {', '.join(incident.data_types_exposed or ['None identified'])}

ROOT CAUSE:
{incident.root_cause or 'Under investigation'}

CONTAINMENT STATUS:
{incident.status.value.upper()}

REMEDIATION STEPS:
{incident.remediation_steps or 'In progress'}

This notification is being provided in accordance with regulatory requirements.
Additional information will be provided as the investigation continues.
"""

    def _generate_customer_notification_content(self, incident: SecurityIncident) -> str:
        """Generate content for customer notification."""
        return f"""
IMPORTANT SECURITY NOTICE

We are writing to inform you about a security incident that may affect your account.

WHAT HAPPENED:
{incident.description}

WHAT INFORMATION WAS INVOLVED:
{', '.join(incident.data_types_exposed or ['Account information'])}

WHAT WE ARE DOING:
We have taken immediate steps to secure our systems and are working with
cybersecurity experts to investigate this incident thoroughly.

WHAT YOU CAN DO:
- Monitor your account statements for any unauthorized activity
- Consider placing a fraud alert on your credit file
- Be cautious of unsolicited communications asking for personal information

FOR MORE INFORMATION:
Please contact our customer service team if you have any questions or concerns.

We sincerely apologize for any inconvenience this may cause and are committed
to protecting your information.
"""

    def _generate_internal_notification_content(self, incident: SecurityIncident) -> str:
        """Generate content for internal notification."""
        return f"""
SECURITY INCIDENT ALERT

Incident ID: {incident.id}
Severity: {incident.severity.value.upper()}
Status: {incident.status.value.upper()}

SUMMARY:
{incident.title}

DETAILS:
{incident.description}

IMPACT:
- Affected Users: {incident.affected_users_count or 'TBD'}
- Affected Records: {incident.affected_records_count or 'TBD'}
- PII Exposed: {'Yes' if incident.pii_exposed else 'No'}
- Financial Data: {'Yes' if incident.financial_data_exposed else 'No'}

NOTIFICATION REQUIREMENTS:
- Regulator: {'Required' if incident.requires_regulator_notification else 'Not required'}
- Customer: {'Required' if incident.requires_customer_notification else 'Not required'}
- Deadline: {incident.notification_deadline.isoformat() if incident.notification_deadline else 'N/A'}

Please coordinate with the incident response team immediately.
"""
