"""Audit log endpoints."""

from datetime import datetime, timedelta, timezone
from typing import Annotated
from uuid import uuid4
import json

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
import io

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
from app.services.pdf_generator import AuditPacketGenerator

router = APIRouter()

# In-memory cache for generated packets (in production, use Redis or S3)
_packet_cache: dict[str, tuple[bytes, datetime]] = {}


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

    # CRITICAL: Filter by tenant_id for multi-tenant security
    logs, total = await audit_service.search_audit_logs(
        tenant_id=current_user.tenant_id,
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
                metadata=json.loads(log.extra_data) if log.extra_data else None,
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
    # CRITICAL: Filter by tenant_id for multi-tenant security
    logs = await audit_service.get_item_audit_trail(
        item_id=item_id,
        tenant_id=current_user.tenant_id,
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


@router.get("/items/{item_id}/views", response_model=list[ItemViewResponse])
async def get_item_views(
    item_id: str,
    db: DBSession,
    current_user: Annotated[object, Depends(require_permission("audit", "view"))],
):
    """Get all view records for a check item."""
    from app.models.user import User

    # CRITICAL: Filter by tenant_id for multi-tenant security
    result = await db.execute(
        select(ItemView).where(
            ItemView.check_item_id == item_id,
            ItemView.tenant_id == current_user.tenant_id,
        ).order_by(ItemView.view_started_at.desc())
    )
    views = result.scalars().all()

    responses = []
    for v in views:
        # Get username (users are tenant-scoped)
        user_result = await db.execute(
            select(User.username).where(
                User.id == v.user_id,
                User.tenant_id == current_user.tenant_id,
            )
        )
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
    global _packet_cache

    # Clean up expired packets
    now = datetime.now(timezone.utc)
    expired_keys = [k for k, (_, exp) in _packet_cache.items() if exp < now]
    for k in expired_keys:
        del _packet_cache[k]

    # Verify item exists and belongs to this tenant
    # CRITICAL: Filter by tenant_id for multi-tenant security
    result = await db.execute(
        select(CheckItem).where(
            CheckItem.id == packet_request.check_item_id,
            CheckItem.tenant_id == current_user.tenant_id,
        )
    )
    item = result.scalar_one_or_none()

    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Check item not found",
        )

    # Generate packet ID
    packet_id = str(uuid4())

    # Generate PDF
    pdf_generator = AuditPacketGenerator(db)
    try:
        pdf_bytes = await pdf_generator.generate(
            check_item_id=packet_request.check_item_id,
            include_images=packet_request.include_images,
            include_history=packet_request.include_history,
            generated_by=current_user.username,
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate PDF: {str(e)}",
        )

    # Store in cache (expires in 1 hour)
    expires_at = now + timedelta(hours=1)
    _packet_cache[packet_id] = (pdf_bytes, expires_at)

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

    # Generate download URL (relative to API base, frontend adds /api/v1 prefix)
    download_url = f"/audit/packet/{packet_id}/download"

    return AuditPacketResponse(
        packet_id=packet_id,
        check_item_id=packet_request.check_item_id,
        generated_at=now,
        generated_by=current_user.username,
        format=packet_request.format,
        download_url=download_url,
        expires_at=expires_at,
    )


@router.get("/packet/{packet_id}/download")
async def download_audit_packet(
    packet_id: str,
    current_user: Annotated[object, Depends(require_permission("audit", "export"))],
):
    """Download a generated audit packet."""
    global _packet_cache

    # Check if packet exists and is not expired
    if packet_id not in _packet_cache:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Packet not found or expired",
        )

    pdf_bytes, expires_at = _packet_cache[packet_id]

    if datetime.now(timezone.utc) > expires_at:
        del _packet_cache[packet_id]
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Packet has expired",
        )

    # Return PDF as streaming response
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=audit_packet_{packet_id}.pdf",
            "Content-Length": str(len(pdf_bytes)),
        },
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
    # CRITICAL: Filter by tenant_id for multi-tenant security
    logs = await audit_service.get_user_activity(
        user_id=user_id,
        tenant_id=current_user.tenant_id,
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
