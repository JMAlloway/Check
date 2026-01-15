"""PDF Audit Packet Generator Service."""

import io
from datetime import datetime, timezone
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    Image,
    PageBreak,
    HRFlowable,
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from PIL import Image as PILImage

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.check import CheckItem
from app.models.decision import Decision
from app.models.audit import AuditLog, ItemView


class AuditPacketGenerator:
    """Generates PDF audit packets for check items."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()

    def _setup_custom_styles(self):
        """Setup custom paragraph styles."""
        self.styles.add(ParagraphStyle(
            name='AuditTitle',
            parent=self.styles['Heading1'],
            fontSize=18,
            alignment=TA_CENTER,
            spaceAfter=20,
        ))
        self.styles.add(ParagraphStyle(
            name='SectionHeader',
            parent=self.styles['Heading2'],
            fontSize=14,
            textColor=colors.HexColor('#1e3a5f'),
            spaceBefore=15,
            spaceAfter=10,
        ))
        self.styles.add(ParagraphStyle(
            name='SubHeader',
            parent=self.styles['Heading3'],
            fontSize=11,
            textColor=colors.HexColor('#374151'),
            spaceBefore=10,
            spaceAfter=5,
        ))
        self.styles.add(ParagraphStyle(
            name='FieldLabel',
            parent=self.styles['Normal'],
            fontSize=9,
            textColor=colors.HexColor('#6b7280'),
        ))
        self.styles.add(ParagraphStyle(
            name='FieldValue',
            parent=self.styles['Normal'],
            fontSize=10,
            textColor=colors.HexColor('#111827'),
        ))
        self.styles.add(ParagraphStyle(
            name='Footer',
            parent=self.styles['Normal'],
            fontSize=8,
            textColor=colors.HexColor('#9ca3af'),
            alignment=TA_CENTER,
        ))

    async def generate(
        self,
        check_item_id: str,
        include_images: bool = True,
        include_history: bool = True,
        generated_by: str = "System",
    ) -> bytes:
        """Generate a PDF audit packet for a check item."""
        # Fetch check item with related data
        item = await self._get_check_item(check_item_id)
        if not item:
            raise ValueError(f"Check item {check_item_id} not found")

        # Fetch decisions
        decisions = await self._get_decisions(check_item_id)

        # Fetch audit logs
        audit_logs = await self._get_audit_logs(check_item_id)

        # Fetch view records
        view_records = await self._get_view_records(check_item_id)

        # Create PDF
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=0.75 * inch,
            leftMargin=0.75 * inch,
            topMargin=0.75 * inch,
            bottomMargin=0.75 * inch,
        )

        # Build content
        story = []

        # Header
        story.extend(self._build_header(item, generated_by))

        # Check Details Section
        story.extend(self._build_check_details(item))

        # Account Context Section
        story.extend(self._build_account_context(item))

        # Check Images Section
        if include_images:
            story.extend(self._build_images_section(item))

        # Decision History Section
        story.extend(self._build_decision_history(decisions))

        # Audit Trail Section
        story.extend(self._build_audit_trail(audit_logs))

        # View Records Section
        story.extend(self._build_view_records(view_records))

        # Footer
        story.extend(self._build_footer(item))

        # Generate PDF
        doc.build(story)
        buffer.seek(0)
        return buffer.getvalue()

    async def _get_check_item(self, item_id: str) -> CheckItem | None:
        """Fetch check item with all related data."""
        from app.models.check import CheckImage
        result = await self.db.execute(
            select(CheckItem)
            .options(
                selectinload(CheckItem.queue),
                selectinload(CheckItem.images),
            )
            .where(CheckItem.id == item_id)
        )
        return result.scalar_one_or_none()

    async def _get_decisions(self, item_id: str) -> list[Decision]:
        """Fetch all decisions for a check item."""
        result = await self.db.execute(
            select(Decision)
            .where(Decision.check_item_id == item_id)
            .order_by(Decision.created_at.desc())
        )
        return list(result.scalars().all())

    async def _get_audit_logs(self, item_id: str) -> list[AuditLog]:
        """Fetch audit logs for a check item."""
        result = await self.db.execute(
            select(AuditLog)
            .where(AuditLog.resource_id == item_id)
            .order_by(AuditLog.timestamp.desc())
            .limit(100)
        )
        return list(result.scalars().all())

    async def _get_view_records(self, item_id: str) -> list[ItemView]:
        """Fetch view records for a check item."""
        result = await self.db.execute(
            select(ItemView)
            .where(ItemView.check_item_id == item_id)
            .order_by(ItemView.view_started_at.desc())
        )
        return list(result.scalars().all())

    def _build_header(self, item: CheckItem, generated_by: str) -> list:
        """Build the document header."""
        elements = []

        # Title
        elements.append(Paragraph("AUDIT PACKET", self.styles['AuditTitle']))
        elements.append(Paragraph("Check Review Console", self.styles['Normal']))
        elements.append(Spacer(1, 10))

        # Generation info
        now = datetime.now(timezone.utc)
        info_data = [
            ["Generated:", now.strftime("%Y-%m-%d %H:%M:%S UTC")],
            ["Generated By:", generated_by],
            ["Check Item ID:", str(item.id)],
            ["External ID:", item.external_item_id or "N/A"],
        ]

        info_table = Table(info_data, colWidths=[1.5 * inch, 4 * inch])
        info_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#6b7280')),
            ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
            ('ALIGN', (1, 0), (1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ]))
        elements.append(info_table)

        elements.append(Spacer(1, 15))
        elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#e5e7eb')))
        elements.append(Spacer(1, 15))

        return elements

    def _build_check_details(self, item: CheckItem) -> list:
        """Build check details section."""
        elements = []

        elements.append(Paragraph("Check Details", self.styles['SectionHeader']))

        # Main details table
        data = [
            ["Amount:", f"${item.amount:,.2f}", "Check Number:", item.check_number or "N/A"],
            ["Payee:", item.payee_name or "N/A", "Check Date:", item.check_date.strftime("%Y-%m-%d") if item.check_date else "N/A"],
            ["Memo:", item.memo or "N/A", "Presented:", item.presented_date.strftime("%Y-%m-%d %H:%M") if item.presented_date else "N/A"],
            ["Status:", item.status.value.upper(), "Risk Level:", item.risk_level.value.upper()],
            ["Account ID:", item.account_id or "N/A", "Source:", item.source_system or "N/A"],
        ]

        table = Table(data, colWidths=[1.2 * inch, 2.3 * inch, 1.2 * inch, 2.3 * inch])
        table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#6b7280')),
            ('TEXTCOLOR', (2, 0), (2, -1), colors.HexColor('#6b7280')),
            ('FONTNAME', (1, 0), (1, -1), 'Helvetica-Bold'),
            ('FONTNAME', (3, 0), (3, -1), 'Helvetica-Bold'),
            ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
            ('ALIGN', (2, 0), (2, -1), 'RIGHT'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
        ]))
        elements.append(table)

        # MICR line
        if item.micr_line:
            elements.append(Spacer(1, 10))
            elements.append(Paragraph("MICR Line", self.styles['SubHeader']))
            elements.append(Paragraph(f"<font face='Courier'>{item.micr_line}</font>", self.styles['FieldValue']))

        elements.append(Spacer(1, 15))
        return elements

    def _build_account_context(self, item: CheckItem) -> list:
        """Build account context section."""
        elements = []

        elements.append(Paragraph("Account Context", self.styles['SectionHeader']))

        # Account info
        account_type_str = item.account_type.value if item.account_type else "N/A"
        account_data = [
            ["Account Type:", account_type_str, "Tenure (Days):", str(item.account_tenure_days) if item.account_tenure_days else "N/A"],
            ["Current Balance:", f"${item.current_balance:,.2f}" if item.current_balance else "N/A", "Avg Balance (30d):", f"${item.average_balance_30d:,.2f}" if item.average_balance_30d else "N/A"],
        ]

        table = Table(account_data, colWidths=[1.3 * inch, 2.2 * inch, 1.3 * inch, 2.2 * inch])
        table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#6b7280')),
            ('TEXTCOLOR', (2, 0), (2, -1), colors.HexColor('#6b7280')),
            ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
            ('ALIGN', (2, 0), (2, -1), 'RIGHT'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        elements.append(table)

        # Check behavior stats
        elements.append(Paragraph("Check Behavior", self.styles['SubHeader']))

        behavior_data = [
            ["Avg Check (30d):", f"${item.avg_check_amount_30d:,.2f}" if item.avg_check_amount_30d else "N/A",
             "Avg Check (90d):", f"${item.avg_check_amount_90d:,.2f}" if item.avg_check_amount_90d else "N/A"],
            ["Max Check (90d):", f"${item.max_check_amount_90d:,.2f}" if item.max_check_amount_90d else "N/A",
             "Std Dev (30d):", f"${item.check_std_dev_30d:,.2f}" if item.check_std_dev_30d else "N/A"],
            ["Returned (90d):", str(item.returned_item_count_90d) if item.returned_item_count_90d is not None else "N/A",
             "Exceptions (90d):", str(item.exception_count_90d) if item.exception_count_90d is not None else "N/A"],
        ]

        behavior_table = Table(behavior_data, colWidths=[1.3 * inch, 2.2 * inch, 1.3 * inch, 2.2 * inch])
        behavior_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#6b7280')),
            ('TEXTCOLOR', (2, 0), (2, -1), colors.HexColor('#6b7280')),
            ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
            ('ALIGN', (2, 0), (2, -1), 'RIGHT'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        elements.append(behavior_table)

        elements.append(Spacer(1, 15))
        return elements

    def _build_images_section(self, item: CheckItem) -> list:
        """Build check images section."""
        elements = []

        elements.append(Paragraph("Check Images", self.styles['SectionHeader']))

        # Find front and back images from the related images
        front_image = next((img for img in (item.images or []) if img.image_type == "front"), None)
        back_image = next((img for img in (item.images or []) if img.image_type == "back"), None)

        # Front image
        if front_image:
            elements.append(Paragraph("Front Image", self.styles['SubHeader']))
            try:
                # For now, just indicate image location since we don't have actual files
                image_ref = front_image.external_image_id or front_image.storage_path or front_image.id
                elements.append(Paragraph(
                    f"<i>Image Reference: {image_ref}</i>",
                    self.styles['FieldValue']
                ))
            except Exception:
                elements.append(Paragraph("<i>Front image not available</i>", self.styles['FieldValue']))
        else:
            elements.append(Paragraph("<i>No front image available</i>", self.styles['FieldValue']))

        elements.append(Spacer(1, 10))

        # Back image
        if back_image:
            elements.append(Paragraph("Back Image", self.styles['SubHeader']))
            try:
                image_ref = back_image.external_image_id or back_image.storage_path or back_image.id
                elements.append(Paragraph(
                    f"<i>Image Reference: {image_ref}</i>",
                    self.styles['FieldValue']
                ))
            except Exception:
                elements.append(Paragraph("<i>Back image not available</i>", self.styles['FieldValue']))
        else:
            elements.append(Paragraph("<i>No back image available</i>", self.styles['FieldValue']))

        elements.append(Spacer(1, 15))
        return elements

    def _build_decision_history(self, decisions: list[Decision]) -> list:
        """Build decision history section."""
        elements = []

        elements.append(Paragraph("Decision History", self.styles['SectionHeader']))

        if not decisions:
            elements.append(Paragraph("<i>No decisions recorded</i>", self.styles['FieldValue']))
            elements.append(Spacer(1, 15))
            return elements

        # Table header
        headers = ["Date/Time", "Action", "User", "Reason Codes", "Notes"]
        data = [headers]

        for decision in decisions:
            # Parse reason codes from JSON string
            reason_codes_str = "-"
            if decision.reason_codes:
                try:
                    import json
                    codes = json.loads(decision.reason_codes)
                    if codes:
                        reason_codes_str = ", ".join(str(c)[:8] + "..." if len(str(c)) > 8 else str(c) for c in codes[:3])
                        if len(codes) > 3:
                            reason_codes_str += f" (+{len(codes)-3})"
                except (json.JSONDecodeError, TypeError):
                    reason_codes_str = "-"

            data.append([
                decision.created_at.strftime("%Y-%m-%d %H:%M") if decision.created_at else "N/A",
                decision.action.value.upper() if decision.action else "N/A",
                str(decision.user_id)[:8] + "..." if decision.user_id else "N/A",
                reason_codes_str,
                (decision.notes[:50] + "...") if decision.notes and len(decision.notes) > 50 else (decision.notes or "-"),
            ])

        table = Table(data, colWidths=[1.3 * inch, 1 * inch, 1 * inch, 1.7 * inch, 2 * inch])
        table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f3f4f6')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#374151')),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e5e7eb')),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
        ]))
        elements.append(table)

        elements.append(Spacer(1, 15))
        return elements

    def _build_audit_trail(self, logs: list[AuditLog]) -> list:
        """Build audit trail section."""
        elements = []

        elements.append(Paragraph("Audit Trail", self.styles['SectionHeader']))

        if not logs:
            elements.append(Paragraph("<i>No audit events recorded</i>", self.styles['FieldValue']))
            elements.append(Spacer(1, 15))
            return elements

        # Table header
        headers = ["Timestamp", "Action", "User", "Description"]
        data = [headers]

        for log in logs[:50]:  # Limit to 50 entries
            data.append([
                log.timestamp.strftime("%Y-%m-%d %H:%M:%S") if log.timestamp else "N/A",
                log.action.value if log.action else "N/A",
                log.username or "System",
                (log.description[:60] + "...") if log.description and len(log.description) > 60 else (log.description or "-"),
            ])

        table = Table(data, colWidths=[1.5 * inch, 1.5 * inch, 1.2 * inch, 2.8 * inch])
        table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f3f4f6')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#374151')),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e5e7eb')),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
        ]))
        elements.append(table)

        if len(logs) > 50:
            elements.append(Spacer(1, 5))
            elements.append(Paragraph(
                f"<i>Showing 50 of {len(logs)} audit events</i>",
                self.styles['Footer']
            ))

        elements.append(Spacer(1, 15))
        return elements

    def _build_view_records(self, views: list[ItemView]) -> list:
        """Build view records section."""
        elements = []

        elements.append(Paragraph("View Records", self.styles['SectionHeader']))

        if not views:
            elements.append(Paragraph("<i>No view records</i>", self.styles['FieldValue']))
            elements.append(Spacer(1, 15))
            return elements

        # Table header
        headers = ["Start Time", "Duration", "User", "Front", "Back", "Zoom", "Magnifier"]
        data = [headers]

        for view in views[:20]:  # Limit to 20 entries
            data.append([
                view.view_started_at.strftime("%Y-%m-%d %H:%M") if view.view_started_at else "N/A",
                f"{view.duration_seconds}s" if view.duration_seconds else "-",
                str(view.user_id)[:8] + "..." if view.user_id else "N/A",
                "Yes" if view.front_image_viewed else "No",
                "Yes" if view.back_image_viewed else "No",
                "Yes" if view.zoom_used else "No",
                "Yes" if view.magnifier_used else "No",
            ])

        table = Table(data, colWidths=[1.4 * inch, 0.8 * inch, 1.2 * inch, 0.6 * inch, 0.6 * inch, 0.6 * inch, 0.8 * inch])
        table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f3f4f6')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#374151')),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e5e7eb')),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
        ]))
        elements.append(table)

        elements.append(Spacer(1, 15))
        return elements

    def _build_footer(self, item: CheckItem) -> list:
        """Build document footer."""
        elements = []

        elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#e5e7eb')))
        elements.append(Spacer(1, 10))

        footer_text = f"""
        This audit packet was generated by the Check Review Console.
        Check Item ID: {item.id} | External ID: {item.external_item_id or 'N/A'}
        This document is confidential and intended for authorized personnel only.
        """
        elements.append(Paragraph(footer_text, self.styles['Footer']))

        return elements
