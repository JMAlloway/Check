"""Check item endpoints."""

import asyncio
import time
from datetime import datetime
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.api.deps import DBSession, RequireCheckView, require_permission
from app.audit.service import AuditService
from app.core.client_ip import get_client_ip
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
    page_size: int = Query(20, ge=1, le=500),
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
    sort_by: str | None = Query(None),
    sort_order: str = Query("desc"),
):
    """List check items with filtering, sorting and pagination."""
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
        sort_by=sort_by,
        sort_order=sort_order,
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
    page_size: int = Query(20, ge=1, le=500),
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


# ---------------------------------------------------------------------------
# Claim-based worklist + soft locks
#
# Lets a team of reviewers "pull" the next item rather than browse-and-pick,
# and prevents two reviewers from working the same item at once. Locks are
# advisory (soft) and kept in memory with a TTL - appropriate for the demo's
# single worker; a clustered deployment would back this with Redis.
# ---------------------------------------------------------------------------

_worklist_lock = asyncio.Lock()
# item_id -> {"user_id", "username", "tenant_id", "expires_at"}
_soft_locks: dict[str, dict] = {}
LOCK_TTL_SECONDS = 300


def _active_locks() -> dict[str, dict]:
    """Return the live (non-expired) locks, pruning any that have lapsed."""
    now = time.time()
    for item_id in [k for k, v in _soft_locks.items() if v["expires_at"] <= now]:
        _soft_locks.pop(item_id, None)
    return _soft_locks


@router.get("/worklist/locks")
async def get_worklist_locks(
    current_user: Annotated[object, Depends(require_permission("check_item", "view"))],
):
    """List items currently locked by a reviewer (for queue badges)."""
    locks = _active_locks()
    return {
        "locks": [
            {"item_id": item_id, "username": lk["username"], "user_id": lk["user_id"]}
            for item_id, lk in locks.items()
            if lk.get("tenant_id") == current_user.tenant_id
        ]
    }


@router.post("/worklist/pull-next", response_model=CheckItemResponse)
async def pull_next_item(
    request: Request,
    db: DBSession,
    current_user: Annotated[object, Depends(require_permission("check_item", "review"))],
):
    """Claim the highest-priority unclaimed pending item for the current user."""
    from sqlalchemy import or_, select

    from app.models.check import CheckItem

    async with _worklist_lock:
        locks = _active_locks()
        result = await db.execute(
            select(CheckItem)
            .where(
                CheckItem.tenant_id == current_user.tenant_id,
                CheckItem.status.in_([CheckStatus.NEW, CheckStatus.IN_REVIEW]),
                or_(
                    CheckItem.assigned_reviewer_id.is_(None),
                    CheckItem.assigned_reviewer_id == current_user.id,
                ),
            )
            .order_by(CheckItem.priority.desc(), CheckItem.created_at.asc())
        )

        candidate = None
        for item in result.scalars().all():
            lock = locks.get(item.id)
            if lock and lock["user_id"] != current_user.id:
                continue  # actively held by someone else
            candidate = item
            break

        if candidate is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No items are available to pull right now.",
            )

        candidate.assigned_reviewer_id = current_user.id
        if candidate.status == CheckStatus.NEW:
            candidate.status = CheckStatus.IN_REVIEW
        _soft_locks[candidate.id] = {
            "user_id": current_user.id,
            "username": current_user.username,
            "tenant_id": current_user.tenant_id,
            "expires_at": time.time() + LOCK_TTL_SECONDS,
        }
        item_id = candidate.id

        audit_service = AuditService(db)
        await audit_service.log(
            action=AuditAction.ITEM_ASSIGNED,
            resource_type="check_item",
            resource_id=item_id,
            user_id=current_user.id,
            username=current_user.username,
            ip_address=get_client_ip(request),
            description="Pulled next item from the worklist",
        )
        await db.commit()

    check_service = CheckService(db)
    return await check_service.get_check_item(item_id, current_user.id, current_user.tenant_id)


@router.post("/{item_id}/release")
async def release_worklist_item(
    item_id: str,
    current_user: Annotated[object, Depends(require_permission("check_item", "view"))],
):
    """Release a soft lock the current user holds on an item."""
    lock = _soft_locks.get(item_id)
    if lock and lock["user_id"] == current_user.id:
        _soft_locks.pop(item_id, None)
        return {"released": True}
    return {"released": False}


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
        ip_address=get_client_ip(request),
    )

    await db.commit()  # Commit the audit log

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
        ip_address=get_client_ip(request),
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
        ip_address=get_client_ip(request),
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
        status = [
            CheckStatus.NEW,
            CheckStatus.IN_REVIEW,
            CheckStatus.PENDING_APPROVAL,
            CheckStatus.ESCALATED,
        ]

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
