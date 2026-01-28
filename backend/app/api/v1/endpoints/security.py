"""Security incident and breach notification endpoints.

Provides API for:
- Reporting security incidents
- Managing incident lifecycle (confirm, contain, resolve)
- Tracking breach notifications
- Viewing incident timelines
"""

from datetime import datetime, timezone
from typing import Annotated

from app.api.deps import get_current_active_superuser, get_db
from app.models.user import User
from app.security.breach import BreachNotificationService
from app.security.models import (
    IncidentSeverity,
    IncidentStatus,
    IncidentType,
)
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


# =============================================================================
# Request/Response Schemas
# =============================================================================


class CreateIncidentRequest(BaseModel):
    """Request to create a security incident."""

    incident_type: IncidentType
    severity: IncidentSeverity
    title: str = Field(..., min_length=5, max_length=255)
    description: str = Field(..., min_length=10)
    discovered_at: datetime
    occurred_at: datetime | None = None
    affected_users_count: int | None = None
    affected_records_count: int | None = None
    data_types_exposed: list[str] | None = None
    evidence: dict | None = None


class ConfirmIncidentRequest(BaseModel):
    """Request to confirm a security incident."""

    root_cause: str | None = None
    additional_data_types: list[str] | None = None


class ContainIncidentRequest(BaseModel):
    """Request to mark incident as contained."""

    containment_actions: str = Field(..., min_length=10)


class ResolveIncidentRequest(BaseModel):
    """Request to resolve a security incident."""

    remediation_steps: str = Field(..., min_length=10)
    lessons_learned: str | None = None


class SendNotificationRequest(BaseModel):
    """Request to mark notification as sent."""

    delivery_method: str = "email"
    delivery_reference: str | None = None


class IncidentResponse(BaseModel):
    """Security incident response."""

    id: str
    tenant_id: str
    incident_type: str
    severity: str
    status: str
    title: str
    description: str
    discovered_at: datetime
    occurred_at: datetime | None
    contained_at: datetime | None
    resolved_at: datetime | None
    affected_users_count: int | None
    affected_records_count: int | None
    data_types_exposed: list[str] | None
    pii_exposed: bool
    financial_data_exposed: bool
    requires_regulator_notification: bool
    requires_customer_notification: bool
    notification_deadline: datetime | None
    root_cause: str | None
    remediation_steps: str | None
    lessons_learned: str | None
    created_at: datetime
    updated_at: datetime | None


class NotificationResponse(BaseModel):
    """Breach notification response."""

    id: str
    incident_id: str
    notification_type: str
    recipient: str
    subject: str
    status: str
    sent_at: datetime | None
    delivery_method: str | None


class PendingNotificationResponse(BaseModel):
    """Pending notification summary."""

    notification_id: str
    incident_id: str
    incident_title: str
    severity: str
    notification_type: str
    recipient: str
    subject: str
    deadline: str | None
    is_overdue: bool


class TimelineEntryResponse(BaseModel):
    """Incident timeline entry."""

    id: str
    type: str
    content: str
    user_id: str
    previous_value: str | None
    new_value: str | None
    created_at: str


# =============================================================================
# Endpoints
# =============================================================================


@router.post("/incidents", response_model=IncidentResponse, status_code=status.HTTP_201_CREATED)
async def create_incident(
    request: Request,
    data: CreateIncidentRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_superuser),
) -> IncidentResponse:
    """Create a new security incident report.

    This initiates the breach notification workflow. Based on the
    severity and data types exposed, the system will determine
    required notifications.

    Requires superuser privileges.
    """
    service = BreachNotificationService(db)

    incident = await service.create_incident(
        tenant_id=current_user.tenant_id,
        incident_type=data.incident_type,
        severity=data.severity,
        title=data.title,
        description=data.description,
        discovered_at=data.discovered_at,
        reported_by_id=current_user.id,
        reported_by_username=current_user.username,
        occurred_at=data.occurred_at,
        affected_users_count=data.affected_users_count,
        affected_records_count=data.affected_records_count,
        data_types_exposed=data.data_types_exposed,
        evidence=data.evidence,
        ip_address=request.client.host if request.client else None,
    )

    await db.commit()

    return _incident_to_response(incident)


@router.post("/incidents/{incident_id}/confirm", response_model=IncidentResponse)
async def confirm_incident(
    incident_id: str,
    request: Request,
    data: ConfirmIncidentRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_superuser),
) -> IncidentResponse:
    """Confirm a security incident after investigation.

    This triggers the creation of required notifications based on
    incident severity and exposed data types.

    Requires superuser privileges.
    """
    service = BreachNotificationService(db)

    try:
        incident = await service.confirm_incident(
            incident_id=incident_id,
            user_id=current_user.id,
            username=current_user.username,
            root_cause=data.root_cause,
            additional_data_types=data.additional_data_types,
            ip_address=request.client.host if request.client else None,
        )
        await db.commit()
        return _incident_to_response(incident)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/incidents/{incident_id}/contain", response_model=IncidentResponse)
async def contain_incident(
    incident_id: str,
    request: Request,
    data: ContainIncidentRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_superuser),
) -> IncidentResponse:
    """Mark a security incident as contained.

    Document the containment actions taken to stop the breach.

    Requires superuser privileges.
    """
    service = BreachNotificationService(db)

    try:
        incident = await service.contain_incident(
            incident_id=incident_id,
            user_id=current_user.id,
            username=current_user.username,
            containment_actions=data.containment_actions,
            ip_address=request.client.host if request.client else None,
        )
        await db.commit()
        return _incident_to_response(incident)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/incidents/{incident_id}/resolve", response_model=IncidentResponse)
async def resolve_incident(
    incident_id: str,
    request: Request,
    data: ResolveIncidentRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_superuser),
) -> IncidentResponse:
    """Resolve a security incident.

    Document remediation steps and lessons learned.

    Requires superuser privileges.
    """
    service = BreachNotificationService(db)

    try:
        incident = await service.resolve_incident(
            incident_id=incident_id,
            user_id=current_user.id,
            username=current_user.username,
            remediation_steps=data.remediation_steps,
            lessons_learned=data.lessons_learned,
            ip_address=request.client.host if request.client else None,
        )
        await db.commit()
        return _incident_to_response(incident)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/incidents", response_model=list[IncidentResponse])
async def list_active_incidents(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_superuser),
) -> list[IncidentResponse]:
    """List all active (non-closed) security incidents.

    Requires superuser privileges.
    """
    service = BreachNotificationService(db)
    incidents = await service.get_active_incidents(current_user.tenant_id)
    return [_incident_to_response(i) for i in incidents]


@router.get("/incidents/{incident_id}/timeline", response_model=list[TimelineEntryResponse])
async def get_incident_timeline(
    incident_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_superuser),
) -> list[TimelineEntryResponse]:
    """Get the full timeline of a security incident.

    Requires superuser privileges.
    """
    service = BreachNotificationService(db)
    timeline = await service.get_incident_timeline(incident_id)
    return [TimelineEntryResponse(**entry) for entry in timeline]


@router.get("/notifications/pending", response_model=list[PendingNotificationResponse])
async def list_pending_notifications(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_superuser),
) -> list[PendingNotificationResponse]:
    """List all pending breach notifications.

    Shows notifications that need to be sent, ordered by deadline.

    Requires superuser privileges.
    """
    service = BreachNotificationService(db)
    notifications = await service.get_pending_notifications(current_user.tenant_id)
    return [PendingNotificationResponse(**n) for n in notifications]


@router.post("/notifications/{notification_id}/send", response_model=NotificationResponse)
async def send_notification(
    notification_id: str,
    request: Request,
    data: SendNotificationRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_superuser),
) -> NotificationResponse:
    """Mark a breach notification as sent.

    Record delivery method and reference for audit purposes.

    Requires superuser privileges.
    """
    service = BreachNotificationService(db)

    try:
        notification = await service.send_notification(
            notification_id=notification_id,
            user_id=current_user.id,
            username=current_user.username,
            delivery_method=data.delivery_method,
            delivery_reference=data.delivery_reference,
            ip_address=request.client.host if request.client else None,
        )
        await db.commit()

        return NotificationResponse(
            id=str(notification.id),
            incident_id=notification.incident_id,
            notification_type=notification.notification_type,
            recipient=notification.recipient,
            subject=notification.subject,
            status=notification.status.value,
            sent_at=notification.sent_at,
            delivery_method=notification.delivery_method,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# =============================================================================
# Helper Functions
# =============================================================================


def _incident_to_response(incident) -> IncidentResponse:
    """Convert incident model to response."""
    return IncidentResponse(
        id=str(incident.id),
        tenant_id=incident.tenant_id,
        incident_type=incident.incident_type.value,
        severity=incident.severity.value,
        status=incident.status.value,
        title=incident.title,
        description=incident.description,
        discovered_at=incident.discovered_at,
        occurred_at=incident.occurred_at,
        contained_at=incident.contained_at,
        resolved_at=incident.resolved_at,
        affected_users_count=incident.affected_users_count,
        affected_records_count=incident.affected_records_count,
        data_types_exposed=incident.data_types_exposed,
        pii_exposed=incident.pii_exposed,
        financial_data_exposed=incident.financial_data_exposed,
        requires_regulator_notification=incident.requires_regulator_notification,
        requires_customer_notification=incident.requires_customer_notification,
        notification_deadline=incident.notification_deadline,
        root_cause=incident.root_cause,
        remediation_steps=incident.remediation_steps,
        lessons_learned=incident.lessons_learned,
        created_at=incident.created_at,
        updated_at=incident.updated_at,
    )
