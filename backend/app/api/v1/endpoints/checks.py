"""Check item endpoints."""

from datetime import datetime
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.api.deps import DBSession, RequireCheckView, require_permission
from app.audit.service import AuditService
from app.models.audit import AuditAction
from app.models.check import CheckStatus, RiskLevel
from app.schemas.check import (
    CheckHistoryResponse,
    CheckItemListResponse,
    CheckItemResponse,
    CheckSearchRequest,
)
from app.schemas.common import PaginatedResponse
from app.services.check import CheckService

router = APIRouter()


@router.get("", response_model=PaginatedResponse[CheckItemListResponse])
async def list_check_items(
    db: DBSession,
    current_user: Annotated[object, Depends(require_permission("check_item", "view"))],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: list[CheckStatus] | None = Query(None),
    risk_level: list[RiskLevel] | None = Query(None),
    amount_min: Decimal | None = None,
    amount_max: Decimal | None = None,
    queue_id: str | None = None,
    assigned_to: str | None = None,
    has_ai_flags: bool | None = None,
    sla_breached: bool | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
):
    """List check items with filtering and pagination."""
    check_service = CheckService(db)

    search = CheckSearchRequest(
        status=status,
        risk_level=risk_level,
        amount_min=amount_min,
        amount_max=amount_max,
        queue_id=queue_id,
        assigned_to=assigned_to,
        has_ai_flags=has_ai_flags,
        sla_breached=sla_breached,
        date_from=date_from,
        date_to=date_to,
    )

    items, total = await check_service.search_items(
        search, current_user.id, current_user.tenant_id, page, page_size
    )

    total_pages = (total + page_size - 1) // page_size

    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        has_next=page < total_pages,
        has_previous=page > 1,
    )


@router.get("/my-queue", response_model=PaginatedResponse[CheckItemListResponse])
async def get_my_queue(
    db: DBSession,
    current_user: RequireCheckView,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """Get check items assigned to current user."""
    check_service = CheckService(db)

    search = CheckSearchRequest(
        assigned_to=current_user.id,
        status=[CheckStatus.NEW, CheckStatus.IN_REVIEW, CheckStatus.PENDING_APPROVAL],
    )

    items, total = await check_service.search_items(
        search, current_user.id, current_user.tenant_id, page, page_size
    )
    total_pages = (total + page_size - 1) // page_size

    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        has_next=page < total_pages,
        has_previous=page > 1,
    )


@router.get("/{item_id}", response_model=CheckItemResponse)
async def get_check_item(
    request: Request,
    item_id: str,
    db: DBSession,
    current_user: Annotated[object, Depends(require_permission("check_item", "view"))],
):
    """Get a specific check item with full details."""
    check_service = CheckService(db)
    audit_service = AuditService(db)

    item = await check_service.get_check_item(item_id, current_user.id, current_user.tenant_id)

    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Check item not found",
        )

    # Log item view
    await audit_service.log_item_viewed(
        check_item_id=item_id,
        user_id=current_user.id,
        tenant_id=current_user.tenant_id,
        username=current_user.username,
        ip_address=request.client.host if request.client else None,
    )

    return item


@router.get("/{item_id}/history", response_model=list[CheckHistoryResponse])
async def get_check_history(
    item_id: str,
    db: DBSession,
    current_user: Annotated[object, Depends(require_permission("check_item", "view"))],
    limit: int = Query(10, ge=1, le=50),
):
    """Get check history for the account associated with a check item."""
    check_service = CheckService(db)

    item = await check_service.get_check_item(item_id, current_user.id, current_user.tenant_id)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Check item not found",
        )

    history = await check_service.get_check_history(item.account_id, current_user.id, limit=limit)
    return history


@router.post("/{item_id}/assign", response_model=CheckItemResponse)
async def assign_check_item(
    request: Request,
    item_id: str,
    db: DBSession,
    current_user: Annotated[object, Depends(require_permission("check_item", "assign"))],
    reviewer_id: str | None = None,
    approver_id: str | None = None,
    queue_id: str | None = None,
):
    """Assign a check item to a reviewer/approver or queue."""
    from sqlalchemy import select

    from app.models.check import CheckItem

    # CRITICAL: Always filter by tenant_id for multi-tenant security
    result = await db.execute(
        select(CheckItem).where(
            CheckItem.id == item_id,
            CheckItem.tenant_id == current_user.tenant_id,
        )
    )
    item = result.scalar_one_or_none()

    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Check item not found",
        )

    audit_service = AuditService(db)

    before_state = {
        "reviewer_id": item.assigned_reviewer_id,
        "approver_id": item.assigned_approver_id,
        "queue_id": item.queue_id,
    }

    if reviewer_id:
        item.assigned_reviewer_id = reviewer_id
    if approver_id:
        item.assigned_approver_id = approver_id
    if queue_id:
        item.queue_id = queue_id

    await audit_service.log(
        action=AuditAction.ITEM_ASSIGNED,
        resource_type="check_item",
        resource_id=item_id,
        user_id=current_user.id,
        username=current_user.username,
        ip_address=request.client.host if request.client else None,
        description="Check item assignment updated",
        before_value=before_state,
        after_value={
            "reviewer_id": item.assigned_reviewer_id,
            "approver_id": item.assigned_approver_id,
            "queue_id": item.queue_id,
        },
    )

    check_service = CheckService(db)
    return await check_service.get_check_item(item_id, current_user.id, current_user.tenant_id)


@router.post("/{item_id}/status", response_model=CheckItemResponse)
async def update_check_status(
    request: Request,
    item_id: str,
    db: DBSession,
    current_user: Annotated[object, Depends(require_permission("check_item", "update"))],
    status: CheckStatus = Query(...),
):
    """Update check item status."""
    from sqlalchemy import select

    from app.models.check import CheckItem

    # CRITICAL: Always filter by tenant_id for multi-tenant security
    result = await db.execute(
        select(CheckItem).where(
            CheckItem.id == item_id,
            CheckItem.tenant_id == current_user.tenant_id,
        )
    )
    item = result.scalar_one_or_none()

    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Check item not found",
        )

    audit_service = AuditService(db)
    old_status = item.status

    item.status = status

    await audit_service.log(
        action=AuditAction.ITEM_STATUS_CHANGED,
        resource_type="check_item",
        resource_id=item_id,
        user_id=current_user.id,
        username=current_user.username,
        ip_address=request.client.host if request.client else None,
        description=f"Status changed from {old_status.value} to {status.value}",
        before_value={"status": old_status.value},
        after_value={"status": status.value},
    )

    check_service = CheckService(db)
    return await check_service.get_check_item(item_id, current_user.id, current_user.tenant_id)


@router.get("/{item_id}/adjacent")
async def get_adjacent_items(
    item_id: str,
    db: DBSession,
    current_user: Annotated[object, Depends(require_permission("check_item", "view"))],
    status: list[CheckStatus] | None = Query(None),
    risk_level: list[RiskLevel] | None = Query(None),
):
    """Get IDs of previous and next items in queue for navigation.

    Returns the adjacent item IDs based on the same filters as the queue view,
    allowing reviewers to navigate directly between items without returning to queue.
    """
    check_service = CheckService(db)

    # Default to reviewable statuses if not specified
    if status is None:
        status = [CheckStatus.NEW, CheckStatus.IN_REVIEW, CheckStatus.PENDING_APPROVAL, CheckStatus.ESCALATED]

    adjacent = await check_service.get_adjacent_items(
        item_id=item_id,
        user_id=current_user.id,
        tenant_id=current_user.tenant_id,
        status=status,
        risk_level=risk_level,
    )

    return adjacent


@router.post("/sync")
async def sync_presented_items(
    db: DBSession,
    current_user: Annotated[object, Depends(require_permission("check_item", "sync"))],
    amount_min: Decimal = Query(Decimal("5000")),
):
    """Sync new presented items from external system."""
    check_service = CheckService(db)
    count = await check_service.sync_presented_items(
        tenant_id=current_user.tenant_id,
        amount_min=amount_min,
    )
    return {"message": f"Synced {count} new items", "count": count}
