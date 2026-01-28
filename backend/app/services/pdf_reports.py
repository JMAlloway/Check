"""PDF Report Generation Service using ReportLab."""

import io
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from app.models.audit import AuditAction, AuditLog
from app.models.check import CheckItem, CheckStatus, RiskLevel
from app.models.decision import Decision, DecisionAction
from app.models.user import User
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession


class PDFReportService:
    """Service for generating PDF reports."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()

    def _setup_custom_styles(self):
        """Set up custom paragraph styles."""
        self.styles.add(
            ParagraphStyle(
                name="ReportTitle",
                parent=self.styles["Heading1"],
                fontSize=18,
                spaceAfter=20,
                alignment=TA_CENTER,
            )
        )
        self.styles.add(
            ParagraphStyle(
                name="SectionHeader",
                parent=self.styles["Heading2"],
                fontSize=14,
                spaceBefore=15,
                spaceAfter=10,
                textColor=colors.HexColor("#1e3a5f"),
            )
        )
        self.styles.add(
            ParagraphStyle(
                name="SubHeader",
                parent=self.styles["Heading3"],
                fontSize=11,
                spaceBefore=10,
                spaceAfter=5,
            )
        )
        self.styles.add(
            ParagraphStyle(
                name="KPIValue",
                parent=self.styles["Normal"],
                fontSize=24,
                alignment=TA_CENTER,
                textColor=colors.HexColor("#1e40af"),
            )
        )
        self.styles.add(
            ParagraphStyle(
                name="KPILabel",
                parent=self.styles["Normal"],
                fontSize=10,
                alignment=TA_CENTER,
                textColor=colors.gray,
            )
        )
        self.styles.add(
            ParagraphStyle(
                name="Footer",
                parent=self.styles["Normal"],
                fontSize=8,
                alignment=TA_CENTER,
                textColor=colors.gray,
            )
        )

    def _create_header(
        self, title: str, date_range: str, tenant_name: str = "Financial Institution"
    ):
        """Create report header elements."""
        elements = []
        elements.append(Paragraph(tenant_name, self.styles["Normal"]))
        elements.append(Paragraph(title, self.styles["ReportTitle"]))
        elements.append(Paragraph(f"Report Period: {date_range}", self.styles["Normal"]))
        elements.append(
            Paragraph(
                f"Generated: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}",
                self.styles["Normal"],
            )
        )
        elements.append(Spacer(1, 20))
        return elements

    def _create_table(self, data: list[list], col_widths: list[float] | None = None) -> Table:
        """Create a styled table."""
        table = Table(data, colWidths=col_widths)
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e3a5f")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, 0), 10),
                    ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
                    ("TOPPADDING", (0, 0), (-1, 0), 12),
                    ("BACKGROUND", (0, 1), (-1, -1), colors.white),
                    ("TEXTCOLOR", (0, 1), (-1, -1), colors.black),
                    ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                    ("FONTSIZE", (0, 1), (-1, -1), 9),
                    ("BOTTOMPADDING", (0, 1), (-1, -1), 8),
                    ("TOPPADDING", (0, 1), (-1, -1), 8),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.gray),
                    (
                        "ROWBACKGROUNDS",
                        (0, 1),
                        (-1, -1),
                        [colors.white, colors.HexColor("#f8fafc")],
                    ),
                ]
            )
        )
        return table

    def _create_kpi_table(self, kpis: list[dict]) -> Table:
        """Create a KPI display table."""
        data = []
        row_values = []
        row_labels = []

        for kpi in kpis:
            row_values.append(Paragraph(str(kpi["value"]), self.styles["KPIValue"]))
            row_labels.append(Paragraph(kpi["label"], self.styles["KPILabel"]))

        data.append(row_values)
        data.append(row_labels)

        table = Table(data, colWidths=[1.5 * inch] * len(kpis))
        table.setStyle(
            TableStyle(
                [
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                    ("TOPPADDING", (0, 0), (-1, -1), 10),
                ]
            )
        )
        return table

    async def generate_daily_activity_log(
        self,
        tenant_id: str,
        date_from: datetime,
        date_to: datetime,
        tenant_name: str = "Financial Institution",
    ) -> bytes:
        """Generate Daily Activity Log PDF report."""
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=0.5 * inch,
            leftMargin=0.5 * inch,
            topMargin=0.5 * inch,
            bottomMargin=0.5 * inch,
        )
        elements = []

        # Header
        date_range = f"{date_from.strftime('%B %d, %Y')} - {date_to.strftime('%B %d, %Y')}"
        elements.extend(self._create_header("Daily Activity Log", date_range, tenant_name))

        # Get all decisions in date range
        decisions_query = (
            select(
                Decision.id,
                Decision.action,
                Decision.created_at,
                Decision.notes,
                Decision.is_dual_control_required,
                Decision.dual_control_approved_at,
                User.username,
                User.full_name,
                CheckItem.external_item_id,
                CheckItem.account_number_masked,
                CheckItem.amount,
                CheckItem.risk_level,
            )
            .join(User, Decision.user_id == User.id)
            .join(CheckItem, Decision.check_item_id == CheckItem.id)
            .where(
                Decision.tenant_id == tenant_id,
                Decision.created_at >= date_from,
                Decision.created_at <= date_to,
            )
            .order_by(Decision.created_at.desc())
        )

        result = await self.db.execute(decisions_query)
        decisions = result.all()

        # Summary section
        elements.append(Paragraph("Summary", self.styles["SectionHeader"]))

        total_decisions = len(decisions)
        action_counts = {}
        for d in decisions:
            action = d.action.value if hasattr(d.action, "value") else str(d.action)
            action_counts[action] = action_counts.get(action, 0) + 1

        summary_data = [
            ["Total Actions", "Approved", "Returned", "Rejected", "Escalated"],
            [
                str(total_decisions),
                str(action_counts.get("approve", 0)),
                str(action_counts.get("return", 0)),
                str(action_counts.get("reject", 0)),
                str(action_counts.get("escalate", 0)),
            ],
        ]
        elements.append(self._create_table(summary_data, [1.3 * inch] * 5))
        elements.append(Spacer(1, 20))

        # Activity detail table
        elements.append(Paragraph("Activity Detail", self.styles["SectionHeader"]))

        if decisions:
            detail_data = [
                ["Time", "User", "Action", "Item ID", "Account", "Amount", "Risk", "Notes"]
            ]
            for d in decisions:
                action = d.action.value if hasattr(d.action, "value") else str(d.action)
                risk = d.risk_level.value if hasattr(d.risk_level, "value") else str(d.risk_level)
                detail_data.append(
                    [
                        d.created_at.strftime("%H:%M:%S"),
                        d.username[:12],
                        action.title(),
                        (d.external_item_id or "")[:10],
                        d.account_number_masked or "",
                        f"${d.amount:,.2f}" if d.amount else "",
                        risk.title(),
                        (d.notes or "")[:20] + ("..." if d.notes and len(d.notes) > 20 else ""),
                    ]
                )

            col_widths = [
                0.7 * inch,
                0.9 * inch,
                0.7 * inch,
                0.8 * inch,
                0.9 * inch,
                0.8 * inch,
                0.6 * inch,
                1.1 * inch,
            ]
            elements.append(self._create_table(detail_data, col_widths))
        else:
            elements.append(
                Paragraph("No activity recorded for this period.", self.styles["Normal"])
            )

        # Footer
        elements.append(Spacer(1, 30))
        elements.append(
            Paragraph(
                "This report is confidential and intended for authorized personnel only.",
                self.styles["Footer"],
            )
        )

        doc.build(elements)
        buffer.seek(0)
        return buffer.getvalue()

    async def generate_daily_summary(
        self,
        tenant_id: str,
        date_from: datetime,
        date_to: datetime,
        tenant_name: str = "Financial Institution",
    ) -> bytes:
        """Generate Daily Summary PDF report."""
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=0.75 * inch,
            leftMargin=0.75 * inch,
            topMargin=0.75 * inch,
            bottomMargin=0.75 * inch,
        )
        elements = []

        # Header
        date_range = f"{date_from.strftime('%B %d, %Y')} - {date_to.strftime('%B %d, %Y')}"
        elements.extend(self._create_header("Daily Summary Report", date_range, tenant_name))

        # Get summary statistics
        # Total items received
        received_result = await self.db.execute(
            select(func.count(CheckItem.id)).where(
                CheckItem.tenant_id == tenant_id,
                CheckItem.presented_date >= date_from,
                CheckItem.presented_date <= date_to,
            )
        )
        total_received = received_result.scalar() or 0

        # Total items processed
        processed_result = await self.db.execute(
            select(func.count(CheckItem.id)).where(
                CheckItem.tenant_id == tenant_id,
                CheckItem.status.in_(
                    [CheckStatus.APPROVED, CheckStatus.RETURNED, CheckStatus.REJECTED]
                ),
                CheckItem.updated_at >= date_from,
                CheckItem.updated_at <= date_to,
            )
        )
        total_processed = processed_result.scalar() or 0

        # Total amount processed
        amount_result = await self.db.execute(
            select(func.sum(CheckItem.amount)).where(
                CheckItem.tenant_id == tenant_id,
                CheckItem.status == CheckStatus.APPROVED,
                CheckItem.updated_at >= date_from,
                CheckItem.updated_at <= date_to,
            )
        )
        total_amount = amount_result.scalar() or Decimal(0)

        # SLA breaches
        sla_result = await self.db.execute(
            select(func.count(CheckItem.id)).where(
                CheckItem.tenant_id == tenant_id,
                CheckItem.sla_breached == True,
                CheckItem.updated_at >= date_from,
                CheckItem.updated_at <= date_to,
            )
        )
        sla_breaches = sla_result.scalar() or 0

        # Key Metrics section
        elements.append(Paragraph("Key Metrics", self.styles["SectionHeader"]))
        kpis = [
            {"value": str(total_received), "label": "Items Received"},
            {"value": str(total_processed), "label": "Items Processed"},
            {"value": f"${total_amount:,.0f}", "label": "Amount Approved"},
            {"value": str(sla_breaches), "label": "SLA Breaches"},
        ]
        elements.append(self._create_kpi_table(kpis))
        elements.append(Spacer(1, 20))

        # Decision breakdown
        elements.append(Paragraph("Decision Breakdown", self.styles["SectionHeader"]))

        decision_result = await self.db.execute(
            select(Decision.action, func.count(Decision.id))
            .where(
                Decision.tenant_id == tenant_id,
                Decision.created_at >= date_from,
                Decision.created_at <= date_to,
            )
            .group_by(Decision.action)
        )
        decision_counts = {
            (a.value if hasattr(a, "value") else str(a)): c for a, c in decision_result.all()
        }

        decision_data = [
            ["Action", "Count", "Percentage"],
        ]
        total_decisions = sum(decision_counts.values())
        for action in ["approve", "return", "reject", "escalate"]:
            count = decision_counts.get(action, 0)
            pct = (count / total_decisions * 100) if total_decisions > 0 else 0
            decision_data.append([action.title(), str(count), f"{pct:.1f}%"])

        elements.append(self._create_table(decision_data, [2 * inch, 1.5 * inch, 1.5 * inch]))
        elements.append(Spacer(1, 20))

        # Risk distribution
        elements.append(Paragraph("Items by Risk Level", self.styles["SectionHeader"]))

        risk_data = [["Risk Level", "Count", "Percentage"]]
        for risk in RiskLevel:
            risk_result = await self.db.execute(
                select(func.count(CheckItem.id)).where(
                    CheckItem.tenant_id == tenant_id,
                    CheckItem.risk_level == risk,
                    CheckItem.presented_date >= date_from,
                    CheckItem.presented_date <= date_to,
                )
            )
            count = risk_result.scalar() or 0
            pct = (count / total_received * 100) if total_received > 0 else 0
            risk_data.append([risk.value.title(), str(count), f"{pct:.1f}%"])

        elements.append(self._create_table(risk_data, [2 * inch, 1.5 * inch, 1.5 * inch]))
        elements.append(Spacer(1, 20))

        # Top reviewers
        elements.append(Paragraph("Reviewer Activity", self.styles["SectionHeader"]))

        reviewer_result = await self.db.execute(
            select(User.username, User.full_name, func.count(Decision.id).label("count"))
            .join(Decision, User.id == Decision.user_id)
            .where(
                Decision.tenant_id == tenant_id,
                Decision.created_at >= date_from,
                Decision.created_at <= date_to,
            )
            .group_by(User.id, User.username, User.full_name)
            .order_by(func.count(Decision.id).desc())
            .limit(10)
        )
        reviewers = reviewer_result.all()

        if reviewers:
            reviewer_data = [["Reviewer", "Decisions"]]
            for r in reviewers:
                name = r.full_name or r.username
                reviewer_data.append([name, str(r.count)])
            elements.append(self._create_table(reviewer_data, [3 * inch, 2 * inch]))
        else:
            elements.append(Paragraph("No reviewer activity recorded.", self.styles["Normal"]))

        # Footer
        elements.append(Spacer(1, 30))
        elements.append(
            Paragraph(
                "This report is confidential and intended for authorized personnel only.",
                self.styles["Footer"],
            )
        )

        doc.build(elements)
        buffer.seek(0)
        return buffer.getvalue()

    async def generate_executive_overview(
        self,
        tenant_id: str,
        tenant_name: str = "Financial Institution",
    ) -> bytes:
        """Generate Executive Overview PDF with QoQ/MoM/YoY KPIs."""
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=0.75 * inch,
            leftMargin=0.75 * inch,
            topMargin=0.75 * inch,
            bottomMargin=0.75 * inch,
        )
        elements = []

        now = datetime.now(timezone.utc)

        # Define periods
        periods = {
            "current_month": {
                "start": now.replace(day=1, hour=0, minute=0, second=0, microsecond=0),
                "end": now,
                "label": now.strftime("%B %Y"),
            },
            "previous_month": {
                "start": (now.replace(day=1) - timedelta(days=1)).replace(
                    day=1, hour=0, minute=0, second=0, microsecond=0
                ),
                "end": now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                - timedelta(seconds=1),
                "label": (now.replace(day=1) - timedelta(days=1)).strftime("%B %Y"),
            },
            "current_quarter": self._get_quarter_dates(now),
            "previous_quarter": self._get_quarter_dates(now - timedelta(days=90)),
            "current_year": {
                "start": now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0),
                "end": now,
                "label": str(now.year),
            },
            "previous_year": {
                "start": now.replace(
                    year=now.year - 1, month=1, day=1, hour=0, minute=0, second=0, microsecond=0
                ),
                "end": now.replace(
                    year=now.year - 1, month=12, day=31, hour=23, minute=59, second=59
                ),
                "label": str(now.year - 1),
            },
        }

        # Header
        elements.extend(
            self._create_header(
                "Executive Overview",
                f"As of {now.strftime('%B %d, %Y')}",
                tenant_name,
            )
        )

        # Get metrics for each period
        async def get_period_metrics(start: datetime, end: datetime) -> dict:
            """Get key metrics for a period."""
            # Items processed
            processed = await self.db.execute(
                select(func.count(CheckItem.id)).where(
                    CheckItem.tenant_id == tenant_id,
                    CheckItem.status.in_(
                        [CheckStatus.APPROVED, CheckStatus.RETURNED, CheckStatus.REJECTED]
                    ),
                    CheckItem.updated_at >= start,
                    CheckItem.updated_at <= end,
                )
            )
            items_processed = processed.scalar() or 0

            # Amount approved
            amount = await self.db.execute(
                select(func.sum(CheckItem.amount)).where(
                    CheckItem.tenant_id == tenant_id,
                    CheckItem.status == CheckStatus.APPROVED,
                    CheckItem.updated_at >= start,
                    CheckItem.updated_at <= end,
                )
            )
            amount_approved = amount.scalar() or Decimal(0)

            # Approval rate
            total_decisions = await self.db.execute(
                select(func.count(Decision.id)).where(
                    Decision.tenant_id == tenant_id,
                    Decision.action.in_(
                        [DecisionAction.APPROVE, DecisionAction.RETURN, DecisionAction.REJECT]
                    ),
                    Decision.created_at >= start,
                    Decision.created_at <= end,
                )
            )
            total = total_decisions.scalar() or 0

            approved = await self.db.execute(
                select(func.count(Decision.id)).where(
                    Decision.tenant_id == tenant_id,
                    Decision.action == DecisionAction.APPROVE,
                    Decision.created_at >= start,
                    Decision.created_at <= end,
                )
            )
            approved_count = approved.scalar() or 0

            approval_rate = (approved_count / total * 100) if total > 0 else 0

            # SLA compliance
            sla_total = await self.db.execute(
                select(func.count(CheckItem.id)).where(
                    CheckItem.tenant_id == tenant_id,
                    CheckItem.updated_at >= start,
                    CheckItem.updated_at <= end,
                )
            )
            sla_total_count = sla_total.scalar() or 0

            sla_breached = await self.db.execute(
                select(func.count(CheckItem.id)).where(
                    CheckItem.tenant_id == tenant_id,
                    CheckItem.sla_breached == True,
                    CheckItem.updated_at >= start,
                    CheckItem.updated_at <= end,
                )
            )
            sla_breach_count = sla_breached.scalar() or 0

            sla_compliance = (
                ((sla_total_count - sla_breach_count) / sla_total_count * 100)
                if sla_total_count > 0
                else 100
            )

            return {
                "items_processed": items_processed,
                "amount_approved": amount_approved,
                "approval_rate": approval_rate,
                "sla_compliance": sla_compliance,
            }

        # Calculate all metrics
        metrics = {}
        for period_name, period_dates in periods.items():
            metrics[period_name] = await get_period_metrics(
                period_dates["start"], period_dates["end"]
            )

        # Month-over-Month section
        elements.append(
            Paragraph("Month-over-Month (MoM) Performance", self.styles["SectionHeader"])
        )

        mom_data = [
            [
                "Metric",
                periods["previous_month"]["label"],
                periods["current_month"]["label"],
                "Change",
            ],
        ]

        # Items processed MoM
        prev_items = metrics["previous_month"]["items_processed"]
        curr_items = metrics["current_month"]["items_processed"]
        change_items = self._calculate_change(prev_items, curr_items)
        mom_data.append(["Items Processed", str(prev_items), str(curr_items), change_items])

        # Amount approved MoM
        prev_amt = metrics["previous_month"]["amount_approved"]
        curr_amt = metrics["current_month"]["amount_approved"]
        change_amt = self._calculate_change(float(prev_amt), float(curr_amt))
        mom_data.append(["Amount Approved", f"${prev_amt:,.0f}", f"${curr_amt:,.0f}", change_amt])

        # Approval rate MoM
        prev_rate = metrics["previous_month"]["approval_rate"]
        curr_rate = metrics["current_month"]["approval_rate"]
        change_rate = f"{curr_rate - prev_rate:+.1f}pp"
        mom_data.append(["Approval Rate", f"{prev_rate:.1f}%", f"{curr_rate:.1f}%", change_rate])

        # SLA compliance MoM
        prev_sla = metrics["previous_month"]["sla_compliance"]
        curr_sla = metrics["current_month"]["sla_compliance"]
        change_sla = f"{curr_sla - prev_sla:+.1f}pp"
        mom_data.append(["SLA Compliance", f"{prev_sla:.1f}%", f"{curr_sla:.1f}%", change_sla])

        elements.append(
            self._create_table(mom_data, [2 * inch, 1.5 * inch, 1.5 * inch, 1.2 * inch])
        )
        elements.append(Spacer(1, 25))

        # Quarter-over-Quarter section
        elements.append(
            Paragraph("Quarter-over-Quarter (QoQ) Performance", self.styles["SectionHeader"])
        )

        qoq_data = [
            [
                "Metric",
                periods["previous_quarter"]["label"],
                periods["current_quarter"]["label"],
                "Change",
            ],
        ]

        prev_items = metrics["previous_quarter"]["items_processed"]
        curr_items = metrics["current_quarter"]["items_processed"]
        change_items = self._calculate_change(prev_items, curr_items)
        qoq_data.append(["Items Processed", str(prev_items), str(curr_items), change_items])

        prev_amt = metrics["previous_quarter"]["amount_approved"]
        curr_amt = metrics["current_quarter"]["amount_approved"]
        change_amt = self._calculate_change(float(prev_amt), float(curr_amt))
        qoq_data.append(["Amount Approved", f"${prev_amt:,.0f}", f"${curr_amt:,.0f}", change_amt])

        prev_rate = metrics["previous_quarter"]["approval_rate"]
        curr_rate = metrics["current_quarter"]["approval_rate"]
        change_rate = f"{curr_rate - prev_rate:+.1f}pp"
        qoq_data.append(["Approval Rate", f"{prev_rate:.1f}%", f"{curr_rate:.1f}%", change_rate])

        prev_sla = metrics["previous_quarter"]["sla_compliance"]
        curr_sla = metrics["current_quarter"]["sla_compliance"]
        change_sla = f"{curr_sla - prev_sla:+.1f}pp"
        qoq_data.append(["SLA Compliance", f"{prev_sla:.1f}%", f"{curr_sla:.1f}%", change_sla])

        elements.append(
            self._create_table(qoq_data, [2 * inch, 1.5 * inch, 1.5 * inch, 1.2 * inch])
        )
        elements.append(Spacer(1, 25))

        # Year-over-Year section
        elements.append(Paragraph("Year-over-Year (YoY) Performance", self.styles["SectionHeader"]))

        yoy_data = [
            [
                "Metric",
                periods["previous_year"]["label"],
                periods["current_year"]["label"],
                "Change",
            ],
        ]

        prev_items = metrics["previous_year"]["items_processed"]
        curr_items = metrics["current_year"]["items_processed"]
        change_items = self._calculate_change(prev_items, curr_items)
        yoy_data.append(["Items Processed", str(prev_items), str(curr_items), change_items])

        prev_amt = metrics["previous_year"]["amount_approved"]
        curr_amt = metrics["current_year"]["amount_approved"]
        change_amt = self._calculate_change(float(prev_amt), float(curr_amt))
        yoy_data.append(["Amount Approved", f"${prev_amt:,.0f}", f"${curr_amt:,.0f}", change_amt])

        prev_rate = metrics["previous_year"]["approval_rate"]
        curr_rate = metrics["current_year"]["approval_rate"]
        change_rate = f"{curr_rate - prev_rate:+.1f}pp"
        yoy_data.append(["Approval Rate", f"{prev_rate:.1f}%", f"{curr_rate:.1f}%", change_rate])

        prev_sla = metrics["previous_year"]["sla_compliance"]
        curr_sla = metrics["current_year"]["sla_compliance"]
        change_sla = f"{curr_sla - prev_sla:+.1f}pp"
        yoy_data.append(["SLA Compliance", f"{prev_sla:.1f}%", f"{curr_sla:.1f}%", change_sla])

        elements.append(
            self._create_table(yoy_data, [2 * inch, 1.5 * inch, 1.5 * inch, 1.2 * inch])
        )
        elements.append(Spacer(1, 25))

        # Current period highlights
        elements.append(Paragraph("Current Period Highlights", self.styles["SectionHeader"]))

        curr = metrics["current_month"]
        kpis = [
            {"value": str(curr["items_processed"]), "label": "Items This Month"},
            {"value": f"${curr['amount_approved']:,.0f}", "label": "Amount Approved"},
            {"value": f"{curr['approval_rate']:.1f}%", "label": "Approval Rate"},
            {"value": f"{curr['sla_compliance']:.1f}%", "label": "SLA Compliance"},
        ]
        elements.append(self._create_kpi_table(kpis))

        # Footer
        elements.append(Spacer(1, 30))
        elements.append(
            Paragraph(
                "This report is confidential and intended for executive management only.",
                self.styles["Footer"],
            )
        )

        doc.build(elements)
        buffer.seek(0)
        return buffer.getvalue()

    def _get_quarter_dates(self, date: datetime) -> dict:
        """Get start and end dates for the quarter containing the given date."""
        quarter = (date.month - 1) // 3 + 1
        year = date.year

        quarter_start_month = (quarter - 1) * 3 + 1
        start = datetime(year, quarter_start_month, 1, tzinfo=timezone.utc)

        if quarter == 4:
            end = datetime(year, 12, 31, 23, 59, 59, tzinfo=timezone.utc)
        else:
            end = datetime(year, quarter_start_month + 3, 1, tzinfo=timezone.utc) - timedelta(
                seconds=1
            )

        return {
            "start": start,
            "end": end,
            "label": f"Q{quarter} {year}",
        }

    def _calculate_change(self, previous: float, current: float) -> str:
        """Calculate percentage change between two values."""
        if previous == 0:
            if current == 0:
                return "0%"
            return "+100%"

        change = ((current - previous) / previous) * 100
        return f"{change:+.1f}%"
