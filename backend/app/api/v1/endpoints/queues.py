"""Queue management endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.api.deps import DBSession, require_permission
from app.audit.service import AuditService
from app.core.rate_limit import user_limiter, RateLimits
from app.models.audit import AuditAction
from app.models.check import CheckItem, CheckStatus
from app.models.queue import Queue, QueueAssignment
from app.schemas.common import MessageResponse, PaginatedResponse
from app.schemas.queue import (
    QueueAssignmentCreate,
    QueueAssignmentResponse,
    QueueCreate,
    QueueResponse,
    QueueStatsResponse,
    QueueUpdate,
)

router = APIRouter()


@router.get("", response_model=list[QueueResponse])
@user_limiter.limit(RateLimits.SEARCH)  # User-based: 60/min, 500/hour
async def list_queues(
    request: Request,
    db: DBSession,
    current_user: Annotated[object, Depends(require_permission("queue", "view"))],
    include_inactive: bool = Query(False),
):
    """List all queues."""
    # CRITICAL: Filter by tenant_id for multi-tenant security
    query = (
        select(Queue)
        .where(Queue.tenant_id == current_user.tenant_id)
        .order_by(Queue.display_order, Queue.name)
    )

    if not include_inactive:
        query = query.where(Queue.is_active == True)

    result = await db.execute(query)
    queues = result.scalars().all()

    return [
        QueueResponse(
            id=q.id,
            name=q.name,
            description=q.description,
            queue_type=q.queue_type,
            sla_hours=q.sla_hours,
            warning_threshold_minutes=q.warning_threshold_minutes,
            is_active=q.is_active,
            display_order=q.display_order,
            current_item_count=q.current_item_count,
            items_processed_today=q.items_processed_today,
            created_at=q.created_at,
            updated_at=q.updated_at,
        )
        for q in queues
    ]


@router.post("", response_model=QueueResponse)
async def create_queue(
    request: Request,
    queue_data: QueueCreate,
    db: DBSession,
    current_user: Annotated[object, Depends(require_permission("queue", "create"))],
):
    """Create a new queue."""
    import json

    queue = Queue(
        tenant_id=current_user.tenant_id,  # CRITICAL: Multi-tenant isolation
        name=queue_data.name,
        description=queue_data.description,
        queue_type=queue_data.queue_type,
        sla_hours=queue_data.sla_hours,
        warning_threshold_minutes=queue_data.warning_threshold_minutes,
        routing_criteria=(
            json.dumps(queue_data.routing_criteria) if queue_data.routing_criteria else None
        ),
        allowed_roles=(
            json.dumps(queue_data.allowed_role_ids) if queue_data.allowed_role_ids else None
        ),
        allowed_users=(
            json.dumps(queue_data.allowed_user_ids) if queue_data.allowed_user_ids else None
        ),
    )

    db.add(queue)
    await db.flush()

    audit_service = AuditService(db)
    await audit_service.log(
        action=AuditAction.QUEUE_CREATED,
        resource_type="queue",
        resource_id=queue.id,
        user_id=current_user.id,
        username=current_user.username,
        ip_address=request.client.host if request.client else None,
        description=f"Created queue {queue.name}",
    )

    # Explicit commit for write operation
    await db.commit()

    return QueueResponse(
        id=queue.id,
        name=queue.name,
        description=queue.description,
        queue_type=queue.queue_type,
        sla_hours=queue.sla_hours,
        warning_threshold_minutes=queue.warning_threshold_minutes,
        is_active=queue.is_active,
        display_order=queue.display_order,
        current_item_count=queue.current_item_count,
        items_processed_today=queue.items_processed_today,
        created_at=queue.created_at,
        updated_at=queue.updated_at,
    )


@router.get("/{queue_id}", response_model=QueueResponse)
async def get_queue(
    queue_id: str,
    db: DBSession,
    current_user: Annotated[object, Depends(require_permission("queue", "view"))],
):
    """Get a specific queue."""
    # CRITICAL: Filter by tenant_id for multi-tenant security
    result = await db.execute(
        select(Queue).where(
            Queue.id == queue_id,
            Queue.tenant_id == current_user.tenant_id,
        )
    )
    queue = result.scalar_one_or_none()

    if not queue:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Queue not found",
        )

    return QueueResponse(
        id=queue.id,
        name=queue.name,
        description=queue.description,
        queue_type=queue.queue_type,
        sla_hours=queue.sla_hours,
        warning_threshold_minutes=queue.warning_threshold_minutes,
        is_active=queue.is_active,
        display_order=queue.display_order,
        current_item_count=queue.current_item_count,
        items_processed_today=queue.items_processed_today,
        created_at=queue.created_at,
        updated_at=queue.updated_at,
    )


@router.patch("/{queue_id}", response_model=QueueResponse)
async def update_queue(
    request: Request,
    queue_id: str,
    queue_data: QueueUpdate,
    db: DBSession,
    current_user: Annotated[object, Depends(require_permission("queue", "update"))],
):
    """Update a queue."""
    # CRITICAL: Filter by tenant_id for multi-tenant security
    result = await db.execute(
        select(Queue).where(
            Queue.id == queue_id,
            Queue.tenant_id == current_user.tenant_id,
        )
    )
    queue = result.scalar_one_or_none()

    if not queue:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Queue not found",
        )

    if queue_data.name is not None:
        queue.name = queue_data.name
    if queue_data.description is not None:
        queue.description = queue_data.description
    if queue_data.queue_type is not None:
        queue.queue_type = queue_data.queue_type
    if queue_data.is_active is not None:
        queue.is_active = queue_data.is_active
    if queue_data.sla_hours is not None:
        queue.sla_hours = queue_data.sla_hours
    if queue_data.display_order is not None:
        queue.display_order = queue_data.display_order

    audit_service = AuditService(db)
    await audit_service.log(
        action=AuditAction.QUEUE_UPDATED,
        resource_type="queue",
        resource_id=queue_id,
        user_id=current_user.id,
        username=current_user.username,
        ip_address=request.client.host if request.client else None,
        description=f"Updated queue {queue.name}",
    )

    return QueueResponse(
        id=queue.id,
        name=queue.name,
        description=queue.description,
        queue_type=queue.queue_type,
        sla_hours=queue.sla_hours,
        warning_threshold_minutes=queue.warning_threshold_minutes,
        is_active=queue.is_active,
        display_order=queue.display_order,
        current_item_count=queue.current_item_count,
        items_processed_today=queue.items_processed_today,
        created_at=queue.created_at,
        updated_at=queue.updated_at,
    )


@router.get("/{queue_id}/stats", response_model=QueueStatsResponse)
@user_limiter.limit(RateLimits.SEARCH)  # User-based: 60/min, 500/hour (aggregation query)
async def get_queue_stats(
    request: Request,
    queue_id: str,
    db: DBSession,
    current_user: Annotated[object, Depends(require_permission("queue", "view"))],
):
    """Get statistics for a queue."""
    # CRITICAL: Filter by tenant_id for multi-tenant security
    result = await db.execute(
        select(Queue).where(
            Queue.id == queue_id,
            Queue.tenant_id == current_user.tenant_id,
        )
    )
    queue = result.scalar_one_or_none()

    if not queue:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Queue not found",
        )

    # Get item counts by status
    # CRITICAL: Filter by tenant_id for multi-tenant security
    status_counts = {}
    for status_val in CheckStatus:
        count_result = await db.execute(
            select(func.count(CheckItem.id)).where(
                CheckItem.queue_id == queue_id,
                CheckItem.tenant_id == current_user.tenant_id,
                CheckItem.status == status_val,
            )
        )
        count = count_result.scalar() or 0
        if count > 0:
            status_counts[status_val.value] = count

    # Get item counts by risk level
    # CRITICAL: Filter by tenant_id for multi-tenant security
    from app.models.check import RiskLevel

    risk_counts = {}
    for risk_val in RiskLevel:
        count_result = await db.execute(
            select(func.count(CheckItem.id)).where(
                CheckItem.queue_id == queue_id,
                CheckItem.tenant_id == current_user.tenant_id,
                CheckItem.risk_level == risk_val,
                CheckItem.status.in_(
                    [CheckStatus.NEW, CheckStatus.IN_REVIEW, CheckStatus.PENDING_APPROVAL]
                ),
            )
        )
        count = count_result.scalar() or 0
        if count > 0:
            risk_counts[risk_val.value] = count

    # Get SLA breached count
    # CRITICAL: Filter by tenant_id for multi-tenant security
    sla_result = await db.execute(
        select(func.count(CheckItem.id)).where(
            CheckItem.queue_id == queue_id,
            CheckItem.tenant_id == current_user.tenant_id,
            CheckItem.sla_breached == True,
            CheckItem.status.in_(
                [CheckStatus.NEW, CheckStatus.IN_REVIEW, CheckStatus.PENDING_APPROVAL]
            ),
        )
    )
    sla_breached = sla_result.scalar() or 0

    # Get total active items
    # CRITICAL: Filter by tenant_id for multi-tenant security
    total_result = await db.execute(
        select(func.count(CheckItem.id)).where(
            CheckItem.queue_id == queue_id,
            CheckItem.tenant_id == current_user.tenant_id,
            CheckItem.status.in_(
                [CheckStatus.NEW, CheckStatus.IN_REVIEW, CheckStatus.PENDING_APPROVAL]
            ),
        )
    )
    total = total_result.scalar() or 0

    return QueueStatsResponse(
        queue_id=queue_id,
        queue_name=queue.name,
        total_items=total,
        items_by_status=status_counts,
        items_by_risk_level=risk_counts,
        sla_breached_count=sla_breached,
        avg_processing_time_minutes=None,  # Would calculate from audit logs
        items_processed_today=queue.items_processed_today,
        items_processed_this_hour=0,  # Would calculate from audit logs
        oldest_item_age_minutes=None,  # Would calculate from presented_date
    )


@router.get("/{queue_id}/assignments", response_model=list[QueueAssignmentResponse])
async def get_queue_assignments(
    queue_id: str,
    db: DBSession,
    current_user: Annotated[object, Depends(require_permission("queue", "view"))],
):
    """Get user assignments for a queue."""
    # First verify the queue belongs to this tenant
    queue_result = await db.execute(
        select(Queue).where(
            Queue.id == queue_id,
            Queue.tenant_id == current_user.tenant_id,
        )
    )
    if not queue_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Queue not found",
        )

    result = await db.execute(
        select(QueueAssignment)
        .options(selectinload(QueueAssignment.user))
        .where(QueueAssignment.queue_id == queue_id)
    )
    assignments = result.scalars().all()

    return [
        QueueAssignmentResponse(
            id=a.id,
            queue_id=a.queue_id,
            user_id=a.user_id,
            can_review=a.can_review,
            can_approve=a.can_approve,
            max_concurrent_items=a.max_concurrent_items,
            is_active=a.is_active,
            assigned_at=a.assigned_at,
            assigned_by_id=a.assigned_by_id,
            user_name=a.user.full_name if a.user else None,
            queue_name=None,
            created_at=a.created_at,
            updated_at=a.updated_at,
        )
        for a in assignments
    ]


@router.post("/{queue_id}/assignments", response_model=QueueAssignmentResponse)
async def create_queue_assignment(
    request: Request,
    queue_id: str,
    assignment_data: QueueAssignmentCreate,
    db: DBSession,
    current_user: Annotated[object, Depends(require_permission("queue", "assign"))],
):
    """Assign a user to a queue."""
    from datetime import datetime, timezone

    # Verify queue exists and belongs to this tenant
    # CRITICAL: Filter by tenant_id for multi-tenant security
    result = await db.execute(
        select(Queue).where(
            Queue.id == queue_id,
            Queue.tenant_id == current_user.tenant_id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Queue not found",
        )

    # Check for existing assignment
    result = await db.execute(
        select(QueueAssignment).where(
            QueueAssignment.queue_id == queue_id,
            QueueAssignment.user_id == assignment_data.user_id,
        )
    )
    existing = result.scalar_one_or_none()

    if existing:
        # Update existing
        existing.can_review = assignment_data.can_review
        existing.can_approve = assignment_data.can_approve
        existing.max_concurrent_items = assignment_data.max_concurrent_items
        existing.is_active = True
        assignment = existing
    else:
        # Create new
        assignment = QueueAssignment(
            queue_id=queue_id,
            user_id=assignment_data.user_id,
            can_review=assignment_data.can_review,
            can_approve=assignment_data.can_approve,
            max_concurrent_items=assignment_data.max_concurrent_items,
            assigned_at=datetime.now(timezone.utc),
            assigned_by_id=current_user.id,
        )
        db.add(assignment)

    await db.flush()

    # Explicit commit for write operation
    await db.commit()

    return QueueAssignmentResponse(
        id=assignment.id,
        queue_id=assignment.queue_id,
        user_id=assignment.user_id,
        can_review=assignment.can_review,
        can_approve=assignment.can_approve,
        max_concurrent_items=assignment.max_concurrent_items,
        is_active=assignment.is_active,
        assigned_at=assignment.assigned_at,
        assigned_by_id=assignment.assigned_by_id,
        user_name=None,
        queue_name=None,
        created_at=assignment.created_at,
        updated_at=assignment.updated_at,
    )
