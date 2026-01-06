"""Audit log endpoints."""

from datetime import datetime
from typing import Annotated
import json

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select

from app.api.deps import DBSession, CurrentUser, require_permission
from app.models.audit import AuditAction, AuditLog, ItemView
from app.models.check import CheckItem
from app.schemas.audit import (
    AuditLogResponse,
    AuditLogSearchRequest,
    AuditPacketRequest,
    AuditPacketResponse,
    ItemViewResponse,
)
from app.schemas.common import PaginatedResponse
from app.audit.service import AuditService

router = APIRouter()


@router.get("/logs", response_model=PaginatedResponse[AuditLogResponse])
async def search_audit_logs(
    db: DBSession,
    current_user: Annotated[object, Depends(require_permission("audit", "view"))],
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    action: AuditAction | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    user_id: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
):
    """Search audit logs with filtering."""
    audit_service = AuditService(db)

    logs, total = await audit_service.search_audit_logs(
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        user_id=user_id,
        date_from=date_from,
        date_to=date_to,
        page=page,
        page_size=page_size,
    )

    total_pages = (total + page_size - 1) // page_size

    return PaginatedResponse(
        items=[
            AuditLogResponse(
                id=log.id,
                timestamp=log.timestamp,
                user_id=log.user_id,
                username=log.username,
                ip_address=log.ip_address,
                action=log.action,
                resource_type=log.resource_type,
                resource_id=log.resource_id,
                description=log.description,
                before_value=json.loads(log.before_value) if log.before_value else None,
                after_value=json.loads(log.after_value) if log.after_value else None,
                metadata=json.loads(log.metadata) if log.metadata else None,
            )
            for log in logs
        ],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        has_next=page < total_pages,
        has_previous=page > 1,
    )


@router.get("/items/{item_id}", response_model=list[AuditLogResponse])
async def get_item_audit_trail(
    item_id: str,
    db: DBSession,
    current_user: Annotated[object, Depends(require_permission("audit", "view"))],
    limit: int = Query(100, ge=1, le=500),
):
    """Get complete audit trail for a check item."""
    audit_service = AuditService(db)
    logs = await audit_service.get_item_audit_trail(item_id, limit=limit)

    return [
        AuditLogResponse(
            id=log.id,
            timestamp=log.timestamp,
            user_id=log.user_id,
            username=log.username,
            ip_address=log.ip_address,
            action=log.action,
            resource_type=log.resource_type,
            resource_id=log.resource_id,
            description=log.description,
            before_value=json.loads(log.before_value) if log.before_value else None,
            after_value=json.loads(log.after_value) if log.after_value else None,
            metadata=json.loads(log.metadata) if log.metadata else None,
        )
        for log in logs
    ]


@router.get("/items/{item_id}/views", response_model=list[ItemViewResponse])
async def get_item_views(
    item_id: str,
    db: DBSession,
    current_user: Annotated[object, Depends(require_permission("audit", "view"))],
):
    """Get all view records for a check item."""
    from app.models.user import User

    result = await db.execute(
        select(ItemView).where(ItemView.check_item_id == item_id).order_by(ItemView.view_started_at.desc())
    )
    views = result.scalars().all()

    responses = []
    for v in views:
        # Get username
        user_result = await db.execute(select(User.username).where(User.id == v.user_id))
        username = user_result.scalar_one_or_none()

        responses.append(
            ItemViewResponse(
                id=v.id,
                check_item_id=v.check_item_id,
                user_id=v.user_id,
                username=username,
                view_started_at=v.view_started_at,
                view_ended_at=v.view_ended_at,
                duration_seconds=v.duration_seconds,
                front_image_viewed=v.front_image_viewed,
                back_image_viewed=v.back_image_viewed,
                zoom_used=v.zoom_used,
                magnifier_used=v.magnifier_used,
                history_compared=v.history_compared,
                ai_assists_viewed=v.ai_assists_viewed,
            )
        )

    return responses


@router.post("/packet", response_model=AuditPacketResponse)
async def generate_audit_packet(
    packet_request: AuditPacketRequest,
    db: DBSession,
    current_user: Annotated[object, Depends(require_permission("audit", "export"))],
):
    """Generate an audit packet for a check item."""
    from datetime import timedelta, timezone
    from uuid import uuid4

    from app.core.security import generate_signed_url

    # Verify item exists
    result = await db.execute(
        select(CheckItem).where(CheckItem.id == packet_request.check_item_id)
    )
    item = result.scalar_one_or_none()

    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Check item not found",
        )

    # Generate packet ID
    packet_id = str(uuid4())

    # Log packet generation
    audit_service = AuditService(db)
    await audit_service.log(
        action=AuditAction.AUDIT_PACKET_GENERATED,
        resource_type="check_item",
        resource_id=packet_request.check_item_id,
        user_id=current_user.id,
        username=current_user.username,
        description=f"Generated audit packet {packet_id}",
        metadata={
            "packet_id": packet_id,
            "format": packet_request.format,
            "include_images": packet_request.include_images,
        },
    )

    # Generate download URL (valid for 1 hour)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
    download_url = generate_signed_url(f"packet_{packet_id}", expires_in=3600)

    return AuditPacketResponse(
        packet_id=packet_id,
        check_item_id=packet_request.check_item_id,
        generated_at=datetime.now(timezone.utc),
        generated_by=current_user.username,
        format=packet_request.format,
        download_url=download_url,
        expires_at=expires_at,
    )


@router.get("/users/{user_id}", response_model=list[AuditLogResponse])
async def get_user_activity(
    user_id: str,
    db: DBSession,
    current_user: Annotated[object, Depends(require_permission("audit", "view"))],
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    limit: int = Query(100, ge=1, le=500),
):
    """Get audit log entries for a specific user."""
    audit_service = AuditService(db)
    logs = await audit_service.get_user_activity(
        user_id=user_id,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
    )

    return [
        AuditLogResponse(
            id=log.id,
            timestamp=log.timestamp,
            user_id=log.user_id,
            username=log.username,
            ip_address=log.ip_address,
            action=log.action,
            resource_type=log.resource_type,
            resource_id=log.resource_id,
            description=log.description,
            before_value=json.loads(log.before_value) if log.before_value else None,
            after_value=json.loads(log.after_value) if log.after_value else None,
            metadata=json.loads(log.metadata) if log.metadata else None,
        )
        for log in logs
    ]
