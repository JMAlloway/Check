"""Reporting endpoints."""

from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy import and_, func, select

from app.api.deps import DBSession, require_permission
from app.audit.service import AuditService
from app.models.audit import AuditAction, AuditLog
from app.models.check import CheckItem, CheckStatus, RiskLevel
from app.models.decision import Decision, DecisionAction

router = APIRouter()


@router.get("/dashboard")
async def get_dashboard_stats(
    db: DBSession,
    current_user: Annotated[object, Depends(require_permission("report", "view"))],
):
    """Get dashboard statistics."""
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    # Total items in review
    pending_result = await db.execute(
        select(func.count(CheckItem.id)).where(
            CheckItem.status.in_([
                CheckStatus.NEW,
                CheckStatus.IN_REVIEW,
                CheckStatus.PENDING_APPROVAL,
                CheckStatus.ESCALATED,
            ])
        )
    )
    pending_count = pending_result.scalar() or 0

    # Items processed today
    processed_result = await db.execute(
        select(func.count(CheckItem.id)).where(
            CheckItem.status.in_([CheckStatus.APPROVED, CheckStatus.RETURNED, CheckStatus.REJECTED]),
            CheckItem.updated_at >= today_start,
        )
    )
    processed_today = processed_result.scalar() or 0

    # SLA breached items
    sla_result = await db.execute(
        select(func.count(CheckItem.id)).where(
            CheckItem.sla_breached == True,
            CheckItem.status.in_([CheckStatus.NEW, CheckStatus.IN_REVIEW, CheckStatus.PENDING_APPROVAL]),
        )
    )
    sla_breached = sla_result.scalar() or 0

    # Items by risk level
    risk_counts = {}
    for risk in RiskLevel:
        count_result = await db.execute(
            select(func.count(CheckItem.id)).where(
                CheckItem.risk_level == risk,
                CheckItem.status.in_([CheckStatus.NEW, CheckStatus.IN_REVIEW, CheckStatus.PENDING_APPROVAL]),
            )
        )
        risk_counts[risk.value] = count_result.scalar() or 0

    # Items by status
    status_counts = {}
    for status_val in CheckStatus:
        count_result = await db.execute(
            select(func.count(CheckItem.id)).where(CheckItem.status == status_val)
        )
        count = count_result.scalar() or 0
        if count > 0:
            status_counts[status_val.value] = count

    # Dual control pending
    dual_control_result = await db.execute(
        select(func.count(Decision.id)).where(
            Decision.is_dual_control_required == True,
            Decision.dual_control_approved_at.is_(None),
        )
    )
    dual_control_pending = dual_control_result.scalar() or 0

    return {
        "summary": {
            "pending_items": pending_count,
            "processed_today": processed_today,
            "sla_breached": sla_breached,
            "dual_control_pending": dual_control_pending,
        },
        "items_by_risk": risk_counts,
        "items_by_status": status_counts,
        "timestamp": now.isoformat(),
    }


@router.get("/throughput")
async def get_throughput_report(
    db: DBSession,
    current_user: Annotated[object, Depends(require_permission("report", "view"))],
    days: int = Query(7, ge=1, le=90),
):
    """Get throughput report for the last N days."""
    now = datetime.now(timezone.utc)
    start_date = now - timedelta(days=days)

    # Get daily processing counts
    daily_data = []
    for i in range(days):
        day_start = (start_date + timedelta(days=i)).replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)

        processed_result = await db.execute(
            select(func.count(CheckItem.id)).where(
                CheckItem.status.in_([CheckStatus.APPROVED, CheckStatus.RETURNED, CheckStatus.REJECTED]),
                CheckItem.updated_at >= day_start,
                CheckItem.updated_at < day_end,
            )
        )

        received_result = await db.execute(
            select(func.count(CheckItem.id)).where(
                CheckItem.presented_date >= day_start,
                CheckItem.presented_date < day_end,
            )
        )

        daily_data.append({
            "date": day_start.date().isoformat(),
            "processed": processed_result.scalar() or 0,
            "received": received_result.scalar() or 0,
        })

    return {
        "period": {"start": start_date.isoformat(), "end": now.isoformat()},
        "daily": daily_data,
    }


@router.get("/decisions")
async def get_decision_report(
    db: DBSession,
    current_user: Annotated[object, Depends(require_permission("report", "view"))],
    days: int = Query(30, ge=1, le=365),
):
    """Get decision breakdown report."""
    now = datetime.now(timezone.utc)
    start_date = now - timedelta(days=days)

    # Decision action breakdown
    action_counts = {}
    for action in DecisionAction:
        count_result = await db.execute(
            select(func.count(Decision.id)).where(
                Decision.action == action,
                Decision.created_at >= start_date,
            )
        )
        count = count_result.scalar() or 0
        if count > 0:
            action_counts[action.value] = count

    # Approval rate
    total_final = await db.execute(
        select(func.count(Decision.id)).where(
            Decision.action.in_([DecisionAction.APPROVE, DecisionAction.RETURN, DecisionAction.REJECT]),
            Decision.created_at >= start_date,
        )
    )
    total_final_count = total_final.scalar() or 0

    approved = await db.execute(
        select(func.count(Decision.id)).where(
            Decision.action == DecisionAction.APPROVE,
            Decision.created_at >= start_date,
        )
    )
    approved_count = approved.scalar() or 0

    approval_rate = (approved_count / total_final_count * 100) if total_final_count > 0 else 0

    return {
        "period": {"start": start_date.isoformat(), "end": now.isoformat()},
        "by_action": action_counts,
        "approval_rate": round(approval_rate, 2),
        "total_decisions": total_final_count,
    }


@router.get("/reviewer-performance")
async def get_reviewer_performance(
    db: DBSession,
    current_user: Annotated[object, Depends(require_permission("report", "view"))],
    days: int = Query(30, ge=1, le=365),
):
    """Get reviewer performance metrics."""
    from app.models.user import User

    now = datetime.now(timezone.utc)
    start_date = now - timedelta(days=days)

    # Get all users who made decisions in the period
    users_result = await db.execute(
        select(Decision.user_id, func.count(Decision.id).label("count"))
        .where(Decision.created_at >= start_date)
        .group_by(Decision.user_id)
        .order_by(func.count(Decision.id).desc())
    )
    user_stats = users_result.all()

    performance = []
    for user_id, count in user_stats:
        # Get user info
        user_result = await db.execute(
            select(User.username, User.full_name).where(User.id == user_id)
        )
        user_info = user_result.one_or_none()

        if user_info:
            username, full_name = user_info

            # Get breakdown by action
            actions_result = await db.execute(
                select(Decision.action, func.count(Decision.id))
                .where(Decision.user_id == user_id, Decision.created_at >= start_date)
                .group_by(Decision.action)
            )
            actions = {a.value: c for a, c in actions_result.all()}

            performance.append({
                "user_id": user_id,
                "username": username,
                "full_name": full_name,
                "total_decisions": count,
                "by_action": actions,
            })

    return {
        "period": {"start": start_date.isoformat(), "end": now.isoformat()},
        "reviewers": performance,
    }


@router.get("/export/decisions")
async def export_decisions_csv(
    request: Request,
    db: DBSession,
    current_user: Annotated[object, Depends(require_permission("report", "export"))],
    date_from: datetime | None = None,
    date_to: datetime | None = None,
):
    """Export decisions to CSV."""
    from app.models.user import User

    # Audit log the export - critical for data governance
    audit_service = AuditService(db)
    await audit_service.log_report_access(
        report_type="decisions_csv",
        user_id=current_user.id,
        username=current_user.username,
        parameters={
            "date_from": date_from.isoformat() if date_from else None,
            "date_to": date_to.isoformat() if date_to else None,
        },
        exported=True,
        ip_address=request.client.host if request.client else None,
    )

    query = (
        select(
            Decision.id,
            Decision.check_item_id,
            Decision.action,
            Decision.created_at,
            Decision.notes,
            User.username,
            CheckItem.account_number_masked,
            CheckItem.amount,
        )
        .join(User, Decision.user_id == User.id)
        .join(CheckItem, Decision.check_item_id == CheckItem.id)
    )

    if date_from:
        query = query.where(Decision.created_at >= date_from)
    if date_to:
        query = query.where(Decision.created_at <= date_to)

    query = query.order_by(Decision.created_at.desc())

    result = await db.execute(query)
    rows = result.all()

    # Build CSV
    import csv
    import io

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Decision ID",
        "Check Item ID",
        "Account",
        "Amount",
        "Action",
        "Reviewer",
        "Decision Date",
        "Notes",
    ])

    for row in rows:
        writer.writerow([
            row.id,
            row.check_item_id,
            row.account_number_masked,
            str(row.amount),
            row.action.value,
            row.username,
            row.created_at.isoformat(),
            row.notes or "",
        ])

    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=decisions_{datetime.now().strftime('%Y%m%d')}.csv"
        },
    )
