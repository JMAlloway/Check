"""Reporting endpoints."""

from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy import and_, func, select

from app.api.deps import DBSession, require_permission
from app.audit.service import AuditService
from app.models.audit import AuditAction, AuditLog, ItemView
from app.models.check import CheckItem, CheckStatus, RiskLevel
from app.models.decision import Decision, DecisionAction
from app.models.user import User

router = APIRouter()


@router.get("/dashboard")
async def get_dashboard_stats(
    db: DBSession,
    current_user: Annotated[object, Depends(require_permission("report", "view"))],
):
    """Get dashboard statistics."""
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    # CRITICAL: All queries filter by tenant_id for multi-tenant security
    tenant_id = current_user.tenant_id

    # Total items in review
    pending_result = await db.execute(
        select(func.count(CheckItem.id)).where(
            CheckItem.tenant_id == tenant_id,
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
            CheckItem.tenant_id == tenant_id,
            CheckItem.status.in_([CheckStatus.APPROVED, CheckStatus.RETURNED, CheckStatus.REJECTED]),
            CheckItem.updated_at >= today_start,
        )
    )
    processed_today = processed_result.scalar() or 0

    # SLA breached items
    sla_result = await db.execute(
        select(func.count(CheckItem.id)).where(
            CheckItem.tenant_id == tenant_id,
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
                CheckItem.tenant_id == tenant_id,
                CheckItem.risk_level == risk,
                CheckItem.status.in_([CheckStatus.NEW, CheckStatus.IN_REVIEW, CheckStatus.PENDING_APPROVAL]),
            )
        )
        risk_counts[risk.value] = count_result.scalar() or 0

    # Items by status
    status_counts = {}
    for status_val in CheckStatus:
        count_result = await db.execute(
            select(func.count(CheckItem.id)).where(
                CheckItem.tenant_id == tenant_id,
                CheckItem.status == status_val,
            )
        )
        count = count_result.scalar() or 0
        if count > 0:
            status_counts[status_val.value] = count

    # Dual control pending
    dual_control_result = await db.execute(
        select(func.count(Decision.id)).where(
            Decision.tenant_id == tenant_id,
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

    # CRITICAL: Filter by tenant_id for multi-tenant security
    tenant_id = current_user.tenant_id

    # Get daily processing counts
    daily_data = []
    for i in range(days):
        day_start = (start_date + timedelta(days=i)).replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)

        processed_result = await db.execute(
            select(func.count(CheckItem.id)).where(
                CheckItem.tenant_id == tenant_id,
                CheckItem.status.in_([CheckStatus.APPROVED, CheckStatus.RETURNED, CheckStatus.REJECTED]),
                CheckItem.updated_at >= day_start,
                CheckItem.updated_at < day_end,
            )
        )

        received_result = await db.execute(
            select(func.count(CheckItem.id)).where(
                CheckItem.tenant_id == tenant_id,
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

    # CRITICAL: Filter by tenant_id for multi-tenant security
    tenant_id = current_user.tenant_id

    # Decision action breakdown
    action_counts = {}
    for action in DecisionAction:
        count_result = await db.execute(
            select(func.count(Decision.id)).where(
                Decision.tenant_id == tenant_id,
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
            Decision.tenant_id == tenant_id,
            Decision.action.in_([DecisionAction.APPROVE, DecisionAction.RETURN, DecisionAction.REJECT]),
            Decision.created_at >= start_date,
        )
    )
    total_final_count = total_final.scalar() or 0

    approved = await db.execute(
        select(func.count(Decision.id)).where(
            Decision.tenant_id == tenant_id,
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

    # CRITICAL: Filter by tenant_id for multi-tenant security
    tenant_id = current_user.tenant_id

    # Get all users who made decisions in the period (within this tenant)
    users_result = await db.execute(
        select(Decision.user_id, func.count(Decision.id).label("count"))
        .where(
            Decision.tenant_id == tenant_id,
            Decision.created_at >= start_date,
        )
        .group_by(Decision.user_id)
        .order_by(func.count(Decision.id).desc())
    )
    user_stats = users_result.all()

    performance = []
    for user_id, count in user_stats:
        # Get user info (users are also tenant-scoped)
        user_result = await db.execute(
            select(User.username, User.full_name).where(
                User.id == user_id,
                User.tenant_id == tenant_id,
            )
        )
        user_info = user_result.one_or_none()

        if user_info:
            username, full_name = user_info

            # Get breakdown by action
            actions_result = await db.execute(
                select(Decision.action, func.count(Decision.id))
                .where(
                    Decision.tenant_id == tenant_id,
                    Decision.user_id == user_id,
                    Decision.created_at >= start_date,
                )
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

    # CRITICAL: Filter by tenant_id for multi-tenant security
    tenant_id = current_user.tenant_id

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

    # CRITICAL: Filter by tenant_id for multi-tenant security
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
        .where(Decision.tenant_id == tenant_id)
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


@router.get("/export/item-views")
async def export_item_views_csv(
    request: Request,
    db: DBSession,
    current_user: Annotated[object, Depends(require_permission("report", "export"))],
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    include_interactions: bool = True,
):
    """Export item view interactions to CSV.

    Provides detailed reviewer interaction data including:
    - View duration
    - Image viewing behavior (front/back)
    - Tool usage (zoom, magnifier)
    - AI assist engagement
    - Context panel usage

    This data is critical for:
    - Reviewer performance analysis
    - Training effectiveness measurement
    - Workflow optimization
    - Compliance auditing (due diligence verification)
    """
    # CRITICAL: Filter by tenant_id for multi-tenant security
    tenant_id = current_user.tenant_id

    # Audit log the export - critical for data governance
    audit_service = AuditService(db)
    await audit_service.log_report_access(
        report_type="item_views_csv",
        user_id=current_user.id,
        username=current_user.username,
        parameters={
            "date_from": date_from.isoformat() if date_from else None,
            "date_to": date_to.isoformat() if date_to else None,
            "include_interactions": include_interactions,
        },
        exported=True,
        ip_address=request.client.host if request.client else None,
    )

    # Build query with tenant filtering
    query = (
        select(
            ItemView.id,
            ItemView.check_item_id,
            ItemView.user_id,
            ItemView.view_started_at,
            ItemView.view_ended_at,
            ItemView.duration_seconds,
            ItemView.front_image_viewed,
            ItemView.back_image_viewed,
            ItemView.zoom_used,
            ItemView.magnifier_used,
            ItemView.history_compared,
            ItemView.ai_assists_viewed,
            ItemView.context_panel_viewed,
            User.username,
        )
        .join(User, ItemView.user_id == User.id)
        .where(ItemView.tenant_id == tenant_id)
    )

    if date_from:
        query = query.where(ItemView.view_started_at >= date_from)
    if date_to:
        query = query.where(ItemView.view_started_at <= date_to)

    query = query.order_by(ItemView.view_started_at.desc())

    result = await db.execute(query)
    rows = result.all()

    # Build CSV
    import csv
    import io

    output = io.StringIO()
    writer = csv.writer(output)

    if include_interactions:
        writer.writerow([
            "View ID",
            "Check Item ID",
            "User ID",
            "Username",
            "View Started",
            "View Ended",
            "Duration (seconds)",
            "Front Image Viewed",
            "Back Image Viewed",
            "Zoom Used",
            "Magnifier Used",
            "History Compared",
            "AI Assists Viewed",
            "Context Panel Viewed",
        ])

        for row in rows:
            writer.writerow([
                row.id,
                row.check_item_id,
                row.user_id,
                row.username,
                row.view_started_at.isoformat() if row.view_started_at else "",
                row.view_ended_at.isoformat() if row.view_ended_at else "",
                row.duration_seconds or "",
                "Yes" if row.front_image_viewed else "No",
                "Yes" if row.back_image_viewed else "No",
                "Yes" if row.zoom_used else "No",
                "Yes" if row.magnifier_used else "No",
                "Yes" if row.history_compared else "No",
                "Yes" if row.ai_assists_viewed else "No",
                "Yes" if row.context_panel_viewed else "No",
            ])
    else:
        # Simplified export without interaction details
        writer.writerow([
            "View ID",
            "Check Item ID",
            "Username",
            "View Started",
            "Duration (seconds)",
        ])

        for row in rows:
            writer.writerow([
                row.id,
                row.check_item_id,
                row.username,
                row.view_started_at.isoformat() if row.view_started_at else "",
                row.duration_seconds or "",
            ])

    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=item_views_{datetime.now().strftime('%Y%m%d')}.csv"
        },
    )


@router.get("/item-views/summary")
async def get_item_view_summary(
    db: DBSession,
    current_user: Annotated[object, Depends(require_permission("report", "view"))],
    days: int = Query(30, ge=1, le=365),
):
    """Get summary of item view interactions.

    Provides aggregate statistics on reviewer behavior:
    - Average view duration
    - Image viewing patterns
    - Tool usage rates
    - AI assist engagement rates
    """
    now = datetime.now(timezone.utc)
    start_date = now - timedelta(days=days)

    # CRITICAL: Filter by tenant_id for multi-tenant security
    tenant_id = current_user.tenant_id

    # Total views in period
    total_views = await db.execute(
        select(func.count(ItemView.id)).where(
            ItemView.tenant_id == tenant_id,
            ItemView.view_started_at >= start_date,
        )
    )
    total_count = total_views.scalar() or 0

    # Average duration
    avg_duration = await db.execute(
        select(func.avg(ItemView.duration_seconds)).where(
            ItemView.tenant_id == tenant_id,
            ItemView.view_started_at >= start_date,
            ItemView.duration_seconds.isnot(None),
        )
    )
    avg_duration_secs = avg_duration.scalar() or 0

    # Interaction rates
    async def get_rate(field):
        result = await db.execute(
            select(func.count(ItemView.id)).where(
                ItemView.tenant_id == tenant_id,
                ItemView.view_started_at >= start_date,
                field == True,
            )
        )
        count = result.scalar() or 0
        return round((count / total_count * 100), 1) if total_count > 0 else 0

    front_image_rate = await get_rate(ItemView.front_image_viewed)
    back_image_rate = await get_rate(ItemView.back_image_viewed)
    zoom_rate = await get_rate(ItemView.zoom_used)
    magnifier_rate = await get_rate(ItemView.magnifier_used)
    history_rate = await get_rate(ItemView.history_compared)
    ai_assist_rate = await get_rate(ItemView.ai_assists_viewed)
    context_panel_rate = await get_rate(ItemView.context_panel_viewed)

    # Views by user (top 10)
    user_views = await db.execute(
        select(ItemView.user_id, User.username, func.count(ItemView.id).label("count"))
        .join(User, ItemView.user_id == User.id)
        .where(
            ItemView.tenant_id == tenant_id,
            ItemView.view_started_at >= start_date,
        )
        .group_by(ItemView.user_id, User.username)
        .order_by(func.count(ItemView.id).desc())
        .limit(10)
    )
    top_reviewers = [
        {"user_id": uid, "username": uname, "view_count": cnt}
        for uid, uname, cnt in user_views.all()
    ]

    return {
        "period": {"start": start_date.isoformat(), "end": now.isoformat()},
        "total_views": total_count,
        "average_duration_seconds": round(avg_duration_secs, 1),
        "interaction_rates": {
            "front_image_viewed": front_image_rate,
            "back_image_viewed": back_image_rate,
            "zoom_used": zoom_rate,
            "magnifier_used": magnifier_rate,
            "history_compared": history_rate,
            "ai_assists_viewed": ai_assist_rate,
            "context_panel_viewed": context_panel_rate,
        },
        "top_reviewers": top_reviewers,
    }
