"""Archive endpoints for historical items and decisions."""

import csv
import io
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import joinedload

from app.api.deps import DBSession, require_permission
from app.audit.service import AuditService
from app.models.audit import AuditAction, AuditLog
from app.models.check import CheckItem, CheckStatus, RiskLevel
from app.models.decision import Decision, DecisionAction
from app.schemas.common import PaginatedResponse

router = APIRouter()

# Statuses considered "archived" (completed/final)
ARCHIVED_STATUSES = [
    CheckStatus.APPROVED,
    CheckStatus.RETURNED,
    CheckStatus.REJECTED,
    CheckStatus.CLOSED,
]


@router.get("/items")
async def search_archived_items(
    db: DBSession,
    current_user: Annotated[object, Depends(require_permission("archive", "view"))],
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    status: list[CheckStatus] | None = Query(None),
    risk_level: list[RiskLevel] | None = Query(None),
    decision_action: list[DecisionAction] | None = Query(None),
    amount_min: Decimal | None = None,
    amount_max: Decimal | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    account_number: str | None = None,
    reviewer_id: str | None = None,
    search_query: str | None = None,
):
    """
    Search archived (completed) items.

    Returns items with final statuses: APPROVED, RETURNED, REJECTED, EXCEPTION.
    Supports filtering by date range, amount, risk level, reviewer, etc.
    """
    tenant_id = current_user.tenant_id

    # Base query - only archived statuses
    query = select(CheckItem).where(
        CheckItem.tenant_id == tenant_id,
        CheckItem.status.in_(status if status else ARCHIVED_STATUSES),
    )

    # Apply filters
    if risk_level:
        query = query.where(CheckItem.risk_level.in_(risk_level))

    if amount_min is not None:
        query = query.where(CheckItem.amount >= amount_min)

    if amount_max is not None:
        query = query.where(CheckItem.amount <= amount_max)

    if date_from:
        query = query.where(CheckItem.updated_at >= date_from)

    if date_to:
        query = query.where(CheckItem.updated_at <= date_to)

    if account_number:
        query = query.where(CheckItem.account_number.ilike(f"%{account_number}%"))

    if search_query:
        # Search in payee name, memo, check number
        query = query.where(
            or_(
                CheckItem.payee_name.ilike(f"%{search_query}%"),
                CheckItem.memo.ilike(f"%{search_query}%"),
                CheckItem.check_number.ilike(f"%{search_query}%"),
                CheckItem.external_item_id.ilike(f"%{search_query}%"),
            )
        )

    # If filtering by reviewer or decision action, we need to join with decisions
    if reviewer_id or decision_action:
        query = query.join(Decision, Decision.check_item_id == CheckItem.id)
        if reviewer_id:
            query = query.where(Decision.user_id == reviewer_id)
        if decision_action:
            query = query.where(Decision.action.in_(decision_action))

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Apply pagination and ordering
    query = query.order_by(CheckItem.updated_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    items = result.scalars().all()

    total_pages = (total + page_size - 1) // page_size

    # Format response
    items_response = []
    for item in items:
        # Get the final decision for this item
        decision_result = await db.execute(
            select(Decision)
            .where(
                Decision.check_item_id == item.id,
                Decision.tenant_id == tenant_id,
            )
            .order_by(Decision.created_at.desc())
            .limit(1)
        )
        decision = decision_result.scalar_one_or_none()

        items_response.append({
            "id": item.id,
            "external_item_id": item.external_item_id,
            "account_number": item.account_number,
            "amount": float(item.amount) if item.amount else None,
            "payee_name": item.payee_name,
            "check_number": item.check_number,
            "status": item.status.value,
            "risk_level": item.risk_level.value if item.risk_level else None,
            "created_at": item.created_at.isoformat() if item.created_at else None,
            "updated_at": item.updated_at.isoformat() if item.updated_at else None,
            "decision": {
                "id": decision.id,
                "action": decision.action.value,
                "user_id": decision.user_id,
                "created_at": decision.created_at.isoformat() if decision.created_at else None,
                "notes": decision.notes,
            } if decision else None,
        })

    return {
        "items": items_response,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
        "has_next": page < total_pages,
        "has_previous": page > 1,
    }


@router.get("/items/{item_id}")
async def get_archived_item_detail(
    item_id: str,
    db: DBSession,
    current_user: Annotated[object, Depends(require_permission("archive", "view"))],
):
    """
    Get detailed view of an archived item including full audit trail.
    """
    tenant_id = current_user.tenant_id

    # Get the item
    result = await db.execute(
        select(CheckItem).where(
            CheckItem.id == item_id,
            CheckItem.tenant_id == tenant_id,
        )
    )
    item = result.scalar_one_or_none()

    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Archived item not found",
        )

    # Get all decisions for this item
    decisions_result = await db.execute(
        select(Decision)
        .where(
            Decision.check_item_id == item_id,
            Decision.tenant_id == tenant_id,
        )
        .order_by(Decision.created_at.asc())
    )
    decisions = decisions_result.scalars().all()

    # Get audit trail
    audit_service = AuditService(db)
    audit_trail = await audit_service.get_item_audit_trail(item_id, tenant_id, limit=200)

    return {
        "item": {
            "id": item.id,
            "external_item_id": item.external_item_id,
            "account_number": item.account_number,
            "routing_number": item.routing_number,
            "amount": float(item.amount) if item.amount else None,
            "payee_name": item.payee_name,
            "check_number": item.check_number,
            "check_date": item.check_date.isoformat() if item.check_date else None,
            "memo": item.memo,
            "status": item.status.value,
            "risk_level": item.risk_level.value if item.risk_level else None,
            "risk_score": item.risk_score,
            "ai_recommendation": item.ai_recommendation,
            "ai_confidence": item.ai_confidence,
            "account_type": item.account_type.value if item.account_type else None,
            "account_tenure_days": item.account_tenure_days,
            "created_at": item.created_at.isoformat() if item.created_at else None,
            "updated_at": item.updated_at.isoformat() if item.updated_at else None,
        },
        "decisions": [
            {
                "id": d.id,
                "decision_type": d.decision_type.value if d.decision_type else None,
                "action": d.action.value,
                "user_id": d.user_id,
                "notes": d.notes,
                "ai_assisted": d.ai_assisted,
                "is_dual_control_required": d.is_dual_control_required,
                "dual_control_approver_id": d.dual_control_approver_id,
                "dual_control_approved_at": d.dual_control_approved_at.isoformat() if d.dual_control_approved_at else None,
                "created_at": d.created_at.isoformat() if d.created_at else None,
            }
            for d in decisions
        ],
        "audit_trail": [
            {
                "id": log.id,
                "action": log.action.value,
                "user_id": log.user_id,
                "username": log.username,
                "description": log.description,
                "timestamp": log.timestamp.isoformat() if log.timestamp else None,
            }
            for log in audit_trail
        ],
    }


@router.get("/export/csv")
async def export_archived_items_csv(
    db: DBSession,
    current_user: Annotated[object, Depends(require_permission("archive", "export"))],
    status: list[CheckStatus] | None = Query(None),
    risk_level: list[RiskLevel] | None = Query(None),
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    max_records: int = Query(10000, ge=1, le=50000),
):
    """
    Export archived items to CSV.

    Maximum 50,000 records per export. Use date filters for larger datasets.
    """
    tenant_id = current_user.tenant_id

    # Audit log the export
    audit_service = AuditService(db)
    await audit_service.log_report_access(
        report_type="archive_export_csv",
        user_id=current_user.id,
        username=current_user.username,
        tenant_id=tenant_id,
        parameters={
            "status": [s.value for s in status] if status else None,
            "risk_level": [r.value for r in risk_level] if risk_level else None,
            "date_from": date_from.isoformat() if date_from else None,
            "date_to": date_to.isoformat() if date_to else None,
            "max_records": max_records,
        },
        exported=True,
    )
    await db.commit()

    # Build query
    query = select(CheckItem).where(
        CheckItem.tenant_id == tenant_id,
        CheckItem.status.in_(status if status else ARCHIVED_STATUSES),
    )

    if risk_level:
        query = query.where(CheckItem.risk_level.in_(risk_level))

    if date_from:
        query = query.where(CheckItem.updated_at >= date_from)

    if date_to:
        query = query.where(CheckItem.updated_at <= date_to)

    query = query.order_by(CheckItem.updated_at.desc()).limit(max_records)

    result = await db.execute(query)
    items = result.scalars().all()

    # Get decisions for all items
    item_ids = [item.id for item in items]
    decisions_result = await db.execute(
        select(Decision)
        .where(
            Decision.check_item_id.in_(item_ids),
            Decision.tenant_id == tenant_id,
        )
    )
    decisions_by_item = {}
    for decision in decisions_result.scalars().all():
        if decision.check_item_id not in decisions_by_item:
            decisions_by_item[decision.check_item_id] = decision

    # Generate CSV
    output = io.StringIO()
    writer = csv.writer(output)

    # Header
    writer.writerow([
        "Item ID",
        "External ID",
        "Account Number",
        "Amount",
        "Payee Name",
        "Check Number",
        "Check Date",
        "Status",
        "Risk Level",
        "Risk Score",
        "Decision Action",
        "Decision Date",
        "Reviewer ID",
        "Decision Notes",
        "AI Assisted",
        "Dual Control Required",
        "Created At",
        "Updated At",
    ])

    # Data rows
    for item in items:
        decision = decisions_by_item.get(item.id)
        writer.writerow([
            item.id,
            item.external_item_id,
            item.account_number,
            float(item.amount) if item.amount else "",
            item.payee_name or "",
            item.check_number or "",
            item.check_date.isoformat() if item.check_date else "",
            item.status.value,
            item.risk_level.value if item.risk_level else "",
            item.risk_score or "",
            decision.action.value if decision else "",
            decision.created_at.isoformat() if decision and decision.created_at else "",
            decision.user_id if decision else "",
            decision.notes or "" if decision else "",
            decision.ai_assisted if decision else "",
            decision.is_dual_control_required if decision else "",
            item.created_at.isoformat() if item.created_at else "",
            item.updated_at.isoformat() if item.updated_at else "",
        ])

    csv_content = output.getvalue()
    output.close()

    # Generate filename with date range
    if date_from and date_to:
        filename = f"archive_export_{date_from.strftime('%Y%m%d')}_to_{date_to.strftime('%Y%m%d')}.csv"
    else:
        filename = f"archive_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/stats")
async def get_archive_statistics(
    db: DBSession,
    current_user: Annotated[object, Depends(require_permission("archive", "view"))],
):
    """
    Get statistics about archived items.
    """
    tenant_id = current_user.tenant_id
    now = datetime.now(timezone.utc)

    # Total archived items
    total_result = await db.execute(
        select(func.count(CheckItem.id)).where(
            CheckItem.tenant_id == tenant_id,
            CheckItem.status.in_(ARCHIVED_STATUSES),
        )
    )
    total_archived = total_result.scalar() or 0

    # By status
    status_counts = {}
    for archive_status in ARCHIVED_STATUSES:
        count_result = await db.execute(
            select(func.count(CheckItem.id)).where(
                CheckItem.tenant_id == tenant_id,
                CheckItem.status == archive_status,
            )
        )
        status_counts[archive_status.value] = count_result.scalar() or 0

    # By time period
    periods = {
        "last_7_days": now - timedelta(days=7),
        "last_30_days": now - timedelta(days=30),
        "last_90_days": now - timedelta(days=90),
        "last_year": now - timedelta(days=365),
    }

    period_counts = {}
    for period_name, start_date in periods.items():
        count_result = await db.execute(
            select(func.count(CheckItem.id)).where(
                CheckItem.tenant_id == tenant_id,
                CheckItem.status.in_(ARCHIVED_STATUSES),
                CheckItem.updated_at >= start_date,
            )
        )
        period_counts[period_name] = count_result.scalar() or 0

    # Oldest and newest archived items
    oldest_result = await db.execute(
        select(CheckItem.updated_at)
        .where(
            CheckItem.tenant_id == tenant_id,
            CheckItem.status.in_(ARCHIVED_STATUSES),
        )
        .order_by(CheckItem.updated_at.asc())
        .limit(1)
    )
    oldest = oldest_result.scalar_one_or_none()

    newest_result = await db.execute(
        select(CheckItem.updated_at)
        .where(
            CheckItem.tenant_id == tenant_id,
            CheckItem.status.in_(ARCHIVED_STATUSES),
        )
        .order_by(CheckItem.updated_at.desc())
        .limit(1)
    )
    newest = newest_result.scalar_one_or_none()

    # Total amount processed
    total_amount_result = await db.execute(
        select(func.sum(CheckItem.amount)).where(
            CheckItem.tenant_id == tenant_id,
            CheckItem.status.in_(ARCHIVED_STATUSES),
        )
    )
    total_amount = total_amount_result.scalar() or 0

    return {
        "total_archived": total_archived,
        "by_status": status_counts,
        "by_period": period_counts,
        "date_range": {
            "oldest": oldest.isoformat() if oldest else None,
            "newest": newest.isoformat() if newest else None,
        },
        "total_amount_processed": float(total_amount),
    }
