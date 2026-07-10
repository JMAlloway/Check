"""Reporting endpoints."""

from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy import and_, func, select

from app.api.deps import DBSession, require_permission
from app.audit.service import AuditService
from app.core.client_ip import get_client_ip
from app.core.config import settings
from app.core.rate_limit import RateLimits, user_limiter
from app.demo.scenarios import get_daily_volume_context, get_daily_volume_series
from app.models.audit import AuditAction, AuditLog
from app.models.check import CheckItem, CheckStatus, RiskLevel
from app.models.decision import Decision, DecisionAction, DecisionType

router = APIRouter()


@router.get("/dashboard")
@user_limiter.limit(RateLimits.SEARCH)  # User-based: 60/min, 500/hour
async def get_dashboard_stats(
    request: Request,
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
            CheckItem.status.in_(
                [
                    CheckStatus.NEW,
                    CheckStatus.IN_REVIEW,
                    CheckStatus.PENDING_DUAL_CONTROL,
                    CheckStatus.ESCALATED,
                ]
            ),
        )
    )
    pending_count = pending_result.scalar() or 0

    # Items processed today
    processed_result = await db.execute(
        select(func.count(CheckItem.id)).where(
            CheckItem.tenant_id == tenant_id,
            CheckItem.status.in_(
                [CheckStatus.APPROVED, CheckStatus.RETURNED, CheckStatus.REJECTED]
            ),
            CheckItem.updated_at >= today_start,
        )
    )
    processed_today = processed_result.scalar() or 0

    # SLA breached items
    sla_result = await db.execute(
        select(func.count(CheckItem.id)).where(
            CheckItem.tenant_id == tenant_id,
            CheckItem.sla_breached == True,
            CheckItem.status.in_(
                [CheckStatus.NEW, CheckStatus.IN_REVIEW, CheckStatus.PENDING_DUAL_CONTROL]
            ),
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
                CheckItem.status.in_(
                    [CheckStatus.NEW, CheckStatus.IN_REVIEW, CheckStatus.PENDING_DUAL_CONTROL]
                ),
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

    # Dual control pending - count check items awaiting a second-level approval
    # (PENDING_DUAL_CONTROL status). This must match what the Approvals queue
    # shows; counting Decision rows double-counts items with multiple recorded
    # recommendations and contradicts the Approvals list.
    dual_control_result = await db.execute(
        select(func.count(CheckItem.id)).where(
            CheckItem.tenant_id == tenant_id,
            CheckItem.status == CheckStatus.PENDING_DUAL_CONTROL,
        )
    )
    dual_control_pending = dual_control_result.scalar() or 0

    result = {
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

    # In demo mode, frame the review queue against whole-bank daily volume. This
    # is illustrative context (not per-item rows) showing that the queue is the
    # small exception slice of a much larger straight-through-cleared volume.
    # Anchor "routed to review" to the live OPEN queue (the exception slice) so
    # the headline volume matches the queue the user is looking at: ~267 routed
    # to review out of ~10k presented (~97.3% straight-through).
    if settings.DEMO_MODE:
        result["daily_volume"] = get_daily_volume_context(
            now.date(), routed_to_review=pending_count
        )

    return result


@router.get("/throughput")
async def get_throughput_report(
    db: DBSession,
    current_user: Annotated[object, Depends(require_permission("report", "view"))],
    days: int = Query(7, ge=1, le=90),
):
    """Get throughput report for the last N days (inclusive of today)."""
    now = datetime.now(timezone.utc)
    # Include today: a "last N days" window ends on the current day.
    start_date = now - timedelta(days=days - 1)

    # CRITICAL: Filter by tenant_id for multi-tenant security
    tenant_id = current_user.tenant_id

    # Get daily processing counts
    daily_data = []
    for i in range(days):
        day_start = (start_date + timedelta(days=i)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        day_end = day_start + timedelta(days=1)

        processed_result = await db.execute(
            select(func.count(CheckItem.id)).where(
                CheckItem.tenant_id == tenant_id,
                CheckItem.status.in_(
                    [CheckStatus.APPROVED, CheckStatus.RETURNED, CheckStatus.REJECTED]
                ),
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

        daily_data.append(
            {
                "date": day_start.date().isoformat(),
                "processed": processed_result.scalar() or 0,
                "received": received_result.scalar() or 0,
            }
        )

    # In demo mode, overlay the whole-bank presented / straight-through volume
    # so the throughput chart conveys real bank scale rather than just the
    # exception queue's row counts.
    if settings.DEMO_MODE:
        backdrop = {v["date"]: v for v in get_daily_volume_series(days, now.date())}
        # Anchor TODAY's bar to the live open-review queue (the same count the
        # dashboard uses) so the throughput "today" entry matches the dashboard
        # "presented today" regardless of weekday. Historical days keep their
        # deterministic, date-seeded baseline.
        today_iso = now.date().isoformat()
        pending_result = await db.execute(
            select(func.count(CheckItem.id)).where(
                CheckItem.tenant_id == tenant_id,
                CheckItem.status.in_(
                    [
                        CheckStatus.NEW,
                        CheckStatus.IN_REVIEW,
                        CheckStatus.PENDING_DUAL_CONTROL,
                        CheckStatus.ESCALATED,
                    ]
                ),
            )
        )
        pending_count = pending_result.scalar() or 0
        backdrop[today_iso] = get_daily_volume_context(now.date(), routed_to_review=pending_count)
        for day in daily_data:
            ctx = backdrop.get(day["date"])
            if ctx:
                day["presented"] = ctx["presented"]
                day["straight_through_cleared"] = ctx["straight_through_cleared"]

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

    # Count ONE decision per item: the terminal/approver decision. Dual-control
    # items record two decisions (a review recommendation + an approval), so
    # counting every Decision row double-counts them and inflates totals beyond
    # the number of items actually decided. Filtering to the APPROVAL_DECISION
    # yields exactly one final decision per decided item and reconciles the
    # totals & approval_rate with the dashboard's processed counts.
    final_decision = Decision.decision_type == DecisionType.APPROVAL_DECISION

    # Decision action breakdown
    action_counts = {}
    for action in DecisionAction:
        count_result = await db.execute(
            select(func.count(Decision.id)).where(
                Decision.tenant_id == tenant_id,
                final_decision,
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
            final_decision,
            Decision.action.in_(
                [DecisionAction.APPROVE, DecisionAction.RETURN, DecisionAction.REJECT]
            ),
            Decision.created_at >= start_date,
        )
    )
    total_final_count = total_final.scalar() or 0

    approved = await db.execute(
        select(func.count(Decision.id)).where(
            Decision.tenant_id == tenant_id,
            final_decision,
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

    # Count one terminal decision per item (see get_decision_report) so a single
    # dual-control item isn't credited to two reviewers and the totals reconcile
    # with the dashboard.
    final_decision = Decision.decision_type == DecisionType.APPROVAL_DECISION

    # Get all users who made decisions in the period (within this tenant)
    users_result = await db.execute(
        select(Decision.user_id, func.count(Decision.id).label("count"))
        .where(
            Decision.tenant_id == tenant_id,
            final_decision,
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
                    final_decision,
                    Decision.user_id == user_id,
                    Decision.created_at >= start_date,
                )
                .group_by(Decision.action)
            )
            actions = {a.value: c for a, c in actions_result.all()}

            performance.append(
                {
                    "user_id": user_id,
                    "username": username,
                    "full_name": full_name,
                    "total_decisions": count,
                    "by_action": actions,
                }
            )

    return {
        "period": {"start": start_date.isoformat(), "end": now.isoformat()},
        "reviewers": performance,
    }


@router.get("/export/decisions")
@user_limiter.limit(RateLimits.EXPORT_CSV)  # User-based: 5/min, 20/hour (expensive)
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
        tenant_id=tenant_id,
        parameters={
            "date_from": date_from.isoformat() if date_from else None,
            "date_to": date_to.isoformat() if date_to else None,
        },
        exported=True,
        ip_address=get_client_ip(request),
    )
    # Persist the export audit row (get_db does not auto-commit); an
    # uncommitted data-export record is a data-governance gap.
    await db.commit()

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

    def _csv_safe(value: object) -> str:
        # Neutralize spreadsheet formula injection: a cell starting with
        # = + - @ (or tab/CR) is executed as a formula in Excel/Sheets. Prefix
        # a single quote so it is rendered as literal text.
        text_value = "" if value is None else str(value)
        if text_value and text_value[0] in ("=", "+", "-", "@", "\t", "\r"):
            return "'" + text_value
        return text_value

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "Decision ID",
            "Check Item ID",
            "Account",
            "Amount",
            "Action",
            "Reviewer",
            "Decision Date",
            "Notes",
        ]
    )

    for row in rows:
        writer.writerow(
            [
                row.id,
                row.check_item_id,
                row.account_number_masked,
                str(row.amount),
                row.action.value,
                _csv_safe(row.username),
                row.created_at.isoformat(),
                _csv_safe(row.notes),
            ]
        )

    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=decisions_{datetime.now().strftime('%Y%m%d')}.csv"
        },
    )


# ============================================================================
# PDF Report Endpoints
# ============================================================================


@router.get("/export/pdf/daily-activity")
@user_limiter.limit(RateLimits.REPORT_PDF)  # User-based: 5/min, 30/hour (very expensive)
async def export_daily_activity_pdf(
    request: Request,
    db: DBSession,
    current_user: Annotated[object, Depends(require_permission("report", "export"))],
    date_from: datetime | None = None,
    date_to: datetime | None = None,
):
    """Export Daily Activity Log as PDF."""
    from app.services.pdf_reports import PDFReportService

    tenant_id = current_user.tenant_id

    # Default to today if no dates provided
    if date_from is None:
        date_from = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    if date_to is None:
        date_to = datetime.now(timezone.utc)

    # Audit log the export
    audit_service = AuditService(db)
    await audit_service.log_report_access(
        report_type="daily_activity_pdf",
        user_id=current_user.id,
        username=current_user.username,
        tenant_id=tenant_id,
        parameters={
            "date_from": date_from.isoformat(),
            "date_to": date_to.isoformat(),
        },
        exported=True,
        ip_address=get_client_ip(request),
    )
    await db.commit()

    # Generate PDF
    pdf_service = PDFReportService(db)
    tenant_name = getattr(current_user, "tenant_name", None) or "Financial Institution"
    pdf_content = await pdf_service.generate_daily_activity_log(
        tenant_id=tenant_id,
        date_from=date_from,
        date_to=date_to,
        tenant_name=tenant_name,
    )

    filename = f"daily_activity_{date_from.strftime('%Y%m%d')}.pdf"
    return Response(
        content=pdf_content,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/export/pdf/daily-summary")
@user_limiter.limit(RateLimits.REPORT_PDF)  # User-based: 5/min, 30/hour (very expensive)
async def export_daily_summary_pdf(
    request: Request,
    db: DBSession,
    current_user: Annotated[object, Depends(require_permission("report", "export"))],
    date_from: datetime | None = None,
    date_to: datetime | None = None,
):
    """Export Daily Summary Report as PDF."""
    from app.services.pdf_reports import PDFReportService

    tenant_id = current_user.tenant_id

    # Default to today if no dates provided
    if date_from is None:
        date_from = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    if date_to is None:
        date_to = datetime.now(timezone.utc)

    # Audit log the export
    audit_service = AuditService(db)
    await audit_service.log_report_access(
        report_type="daily_summary_pdf",
        user_id=current_user.id,
        username=current_user.username,
        tenant_id=tenant_id,
        parameters={
            "date_from": date_from.isoformat(),
            "date_to": date_to.isoformat(),
        },
        exported=True,
        ip_address=get_client_ip(request),
    )
    await db.commit()

    # Generate PDF
    pdf_service = PDFReportService(db)
    tenant_name = getattr(current_user, "tenant_name", None) or "Financial Institution"
    pdf_content = await pdf_service.generate_daily_summary(
        tenant_id=tenant_id,
        date_from=date_from,
        date_to=date_to,
        tenant_name=tenant_name,
    )

    filename = f"daily_summary_{date_from.strftime('%Y%m%d')}.pdf"
    return Response(
        content=pdf_content,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/export/pdf/executive-overview")
@user_limiter.limit(RateLimits.REPORT_PDF)  # User-based: 5/min, 30/hour (very expensive)
async def export_executive_overview_pdf(
    request: Request,
    db: DBSession,
    current_user: Annotated[object, Depends(require_permission("report", "export"))],
):
    """Export Executive Overview Report with QoQ/MoM/YoY KPIs as PDF."""
    from app.services.pdf_reports import PDFReportService

    tenant_id = current_user.tenant_id

    # Audit log the export
    audit_service = AuditService(db)
    await audit_service.log_report_access(
        report_type="executive_overview_pdf",
        user_id=current_user.id,
        username=current_user.username,
        tenant_id=tenant_id,
        parameters={},
        exported=True,
        ip_address=get_client_ip(request),
    )
    await db.commit()

    # Generate PDF
    pdf_service = PDFReportService(db)
    tenant_name = getattr(current_user, "tenant_name", None) or "Financial Institution"
    pdf_content = await pdf_service.generate_executive_overview(
        tenant_id=tenant_id,
        tenant_name=tenant_name,
    )

    filename = f"executive_overview_{datetime.now().strftime('%Y%m%d')}.pdf"
    return Response(
        content=pdf_content,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
