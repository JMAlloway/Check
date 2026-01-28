"""Connector B - Batch Commit Service.

This service handles:
- Batch creation with dual control enforcement
- Idempotent file generation (CSV, fixed-width, XML)
- Deterministic hashing for reproducibility
- Acknowledgement processing
- Reconciliation reporting

No direct core writes - files are picked up by bank middleware.
"""

import csv
import hashlib
import io
import json
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import uuid4

import defusedxml.ElementTree as ET  # nosec: using defusedxml for XXE protection
from app.models.check import CheckItem, CheckStatus, RiskLevel
from app.models.connector import (
    AcknowledgementStatus,
    BankConnectorConfig,
    BatchAcknowledgement,
    BatchStatus,
    CommitBatch,
    CommitDecisionType,
    CommitRecord,
    ErrorCategory,
    FileFormat,
    HoldReasonCode,
    ReconciliationReport,
    RecordStatus,
)
from app.models.decision import Decision, DecisionAction
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload


class ConnectorError(Exception):
    """Base exception for connector errors."""

    pass


class DualControlViolation(ConnectorError):
    """Raised when dual control requirements are not met."""

    pass


class BatchNotFoundError(ConnectorError):
    """Raised when batch is not found."""

    pass


class BatchStateError(ConnectorError):
    """Raised when batch is in invalid state for operation."""

    pass


class FileGenerationError(ConnectorError):
    """Raised when file generation fails."""

    pass


# =============================================================================
# HASH GENERATION (Idempotency)
# =============================================================================


def generate_decision_hash(
    decision_id: str,
    check_item_id: str,
    decision_type: str,
    amount: Decimal,
    decision_timestamp: datetime,
) -> str:
    """
    Generate unique hash for a decision record.

    This hash ensures idempotency - the same decision always produces
    the same hash, preventing duplicate processing.
    """
    data = (
        f"{decision_id}|{check_item_id}|{decision_type}|{amount}|{decision_timestamp.isoformat()}"
    )
    return hashlib.sha256(data.encode()).hexdigest()


def generate_batch_hash(record_hashes: list[str]) -> str:
    """
    Generate deterministic batch hash from all record hashes.

    Sorting ensures same records always produce same batch hash
    regardless of insertion order.
    """
    sorted_hashes = sorted(record_hashes)
    combined = "|".join(sorted_hashes)
    return hashlib.sha256(combined.encode()).hexdigest()


def generate_file_checksum(content: bytes) -> str:
    """Generate SHA-256 checksum for file content."""
    return hashlib.sha256(content).hexdigest()


# =============================================================================
# EVIDENCE SNAPSHOT
# =============================================================================


def build_evidence_snapshot(
    check_item: CheckItem,
    decision: Decision,
    policy_result: dict[str, Any] | None = None,
    ai_flags: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """
    Build evidence snapshot for audit replay.

    Captures the exact state at decision time:
    - Policy evaluation results
    - AI flags displayed
    - Key context values
    - Image references
    """
    snapshot = {
        "snapshot_version": "1.0",
        "captured_at": datetime.now(timezone.utc).isoformat(),
        # Check item context (frozen)
        "check_context": {
            "amount": str(check_item.amount),
            "account_type": check_item.account_type.value if check_item.account_type else None,
            "account_tenure_days": check_item.account_tenure_days,
            "current_balance": (
                str(check_item.current_balance) if check_item.current_balance else None
            ),
            "average_balance_30d": (
                str(check_item.average_balance_30d) if check_item.average_balance_30d else None
            ),
            "avg_check_amount_30d": (
                str(check_item.avg_check_amount_30d) if check_item.avg_check_amount_30d else None
            ),
            "avg_check_amount_90d": (
                str(check_item.avg_check_amount_90d) if check_item.avg_check_amount_90d else None
            ),
            "check_frequency_30d": check_item.check_frequency_30d,
            "returned_item_count_90d": check_item.returned_item_count_90d,
            "exception_count_90d": check_item.exception_count_90d,
            "risk_level": check_item.risk_level.value if check_item.risk_level else None,
            "risk_flags": json.loads(check_item.risk_flags) if check_item.risk_flags else [],
            "upstream_flags": (
                json.loads(check_item.upstream_flags) if check_item.upstream_flags else []
            ),
        },
        # Image references (for reproducibility)
        "images": [
            {
                "id": img.id,
                "type": img.image_type,
                "external_id": img.external_image_id,
                "checksum": None,  # Would be populated from actual image
            }
            for img in (
                check_item.images if hasattr(check_item, "images") and check_item.images else []
            )
        ],
        # Policy evaluation (what rules triggered)
        "policy_evaluation": policy_result or {},
        # AI assistance
        "ai_assistance": {
            "ai_assisted": decision.ai_assisted,
            "ai_risk_score": str(check_item.ai_risk_score) if check_item.ai_risk_score else None,
            "flags_reviewed": (
                json.loads(decision.ai_flags_reviewed) if decision.ai_flags_reviewed else []
            ),
            "flags_displayed": ai_flags or [],
        },
        # Decision details
        "decision": {
            "type": decision.decision_type.value if decision.decision_type else None,
            "action": decision.action.value if decision.action else None,
            "reason_codes": json.loads(decision.reason_codes) if decision.reason_codes else [],
            "notes": decision.notes,
            "policy_version_id": decision.policy_version_id,
        },
    }
    return snapshot


# =============================================================================
# FILE GENERATORS
# =============================================================================


class FileGenerator:
    """Base class for file generators."""

    def __init__(self, config: BankConnectorConfig):
        self.config = config
        self.field_config = config.field_config or {}

    def generate(self, batch: CommitBatch, records: list[CommitRecord]) -> bytes:
        """Generate file content. Override in subclasses."""
        raise NotImplementedError

    def get_file_name(self, batch: CommitBatch) -> str:
        """Generate file name from pattern."""
        now = datetime.now(timezone.utc)
        pattern = self.config.file_name_pattern

        replacements = {
            "{BANK_ID}": self.config.bank_id,
            "{BATCH_ID}": batch.batch_number,
            "{BATCH_UUID}": batch.id,
            "{YYYYMMDD}": now.strftime("%Y%m%d"),
            "{HHMMSS}": now.strftime("%H%M%S"),
            "{YYYYMMDD_HHMMSS}": now.strftime("%Y%m%d_%H%M%S"),
            "{TIMESTAMP}": str(int(now.timestamp())),
        }

        result = pattern
        for key, value in replacements.items():
            result = result.replace(key, value)

        return result

    def _format_record(self, record: CommitRecord) -> dict[str, str]:
        """Format record fields according to config."""
        fields = self.field_config.get("fields", [])
        result = {}

        # Default field mappings
        field_values = {
            "bank_id": self.config.bank_id,
            "batch_id": record.batch.batch_number if record.batch else "",
            "batch_uuid": record.batch_id,
            "item_id": record.item_id,
            "sequence_number": str(record.sequence_number),
            "decision_hash": record.decision_hash,
            "account_number": record.account_number_masked,
            "routing_number": record.routing_number or "",
            "micr_line": record.micr_line or "",
            "transaction_amount": f"{record.transaction_amount:.2f}",
            "decision_type": record.decision_type.value.upper(),
            "hold_amount": f"{record.hold_amount:.2f}" if record.hold_amount else "",
            "hold_start_date": (
                record.hold_start_date.strftime("%Y%m%d") if record.hold_start_date else ""
            ),
            "hold_expiration_date": (
                record.hold_expiration_date.strftime("%Y%m%d")
                if record.hold_expiration_date
                else ""
            ),
            "hold_reason_code": record.hold_reason_code.value if record.hold_reason_code else "",
            "hold_reason_text": record.hold_reason_text or "",
            "reviewer_user_id": record.reviewer_user_id,
            "approver_user_id": record.approver_user_id,
            "decision_timestamp": (
                record.decision_timestamp.strftime("%Y%m%dT%H%M%SZ")
                if record.decision_timestamp
                else ""
            ),
            "decision_reference_id": record.decision_id,
            "notes": (
                (record.notes or "")[: self.config.max_notes_length]
                if self.config.include_notes
                else ""
            ),
        }

        for field in fields:
            name = field.get("name")
            source = field.get("source", name)
            result[name] = field_values.get(source, "")

        return result


class CSVGenerator(FileGenerator):
    """CSV file generator."""

    def generate(self, batch: CommitBatch, records: list[CommitRecord]) -> bytes:
        """Generate CSV file content."""
        output = io.StringIO()
        fields = self.field_config.get("fields", [])
        field_names = [f["name"] for f in fields]

        writer = csv.DictWriter(
            output,
            fieldnames=field_names,
            quoting=csv.QUOTE_MINIMAL,
            lineterminator="\r\n" if self.config.file_line_ending == "CRLF" else "\n",
        )

        # Header row
        if self.config.include_header_row:
            writer.writeheader()

        # Data rows
        for record in records:
            row = self._format_record(record)
            writer.writerow(row)

        # Trailer row (record count, totals)
        if self.config.include_trailer_row:
            total_amount = sum(r.transaction_amount for r in records)
            trailer = {field_names[0]: "TRAILER"} if field_names else {}
            trailer["record_count"] = str(len(records)) if "record_count" in field_names else ""
            trailer["total_amount"] = f"{total_amount:.2f}" if "total_amount" in field_names else ""
            writer.writerow(trailer)

        content = output.getvalue()
        return content.encode(self.config.file_encoding)


class FixedWidthGenerator(FileGenerator):
    """Fixed-width file generator."""

    def generate(self, batch: CommitBatch, records: list[CommitRecord]) -> bytes:
        """Generate fixed-width file content."""
        lines = []
        fields = self.field_config.get("fields", [])
        line_ending = "\r\n" if self.config.file_line_ending == "CRLF" else "\n"

        # Header row
        if self.config.include_header_row:
            header_line = self._build_fixed_header(fields)
            lines.append(header_line)

        # Data rows
        for record in records:
            data = self._format_record(record)
            line = self._build_fixed_line(data, fields)
            lines.append(line)

        # Trailer row
        if self.config.include_trailer_row:
            total_amount = sum(r.transaction_amount for r in records)
            trailer = self._build_fixed_trailer(len(records), total_amount, fields)
            lines.append(trailer)

        content = line_ending.join(lines) + line_ending
        return content.encode(self.config.file_encoding)

    def _build_fixed_header(self, fields: list[dict]) -> str:
        """Build fixed-width header line."""
        parts = []
        for field in fields:
            name = field.get("name", "")
            length = field.get("length", 20)
            align = field.get("align", "left")
            if align == "right":
                parts.append(name[:length].rjust(length))
            else:
                parts.append(name[:length].ljust(length))
        return "".join(parts)

    def _build_fixed_line(self, data: dict[str, str], fields: list[dict]) -> str:
        """Build fixed-width data line."""
        parts = []
        for field in fields:
            name = field.get("name")
            length = field.get("length", 20)
            align = field.get("align", "left")
            pad = field.get("pad", " ")
            value = data.get(name, "")[:length]

            if align == "right":
                parts.append(value.rjust(length, pad))
            else:
                parts.append(value.ljust(length, pad))

        return "".join(parts)

    def _build_fixed_trailer(
        self, record_count: int, total_amount: Decimal, fields: list[dict]
    ) -> str:
        """Build fixed-width trailer line."""
        # Simple trailer format
        trailer_data = {
            "record_type": "TRAILER",
            "record_count": str(record_count),
            "total_amount": f"{total_amount:.2f}",
        }
        return self._build_fixed_line(trailer_data, fields)


class XMLGenerator(FileGenerator):
    """XML file generator."""

    def generate(self, batch: CommitBatch, records: list[CommitRecord]) -> bytes:
        """Generate XML file content."""
        root = ET.Element("CommitBatch")
        root.set("xmlns", "urn:bank:connector:batch:v1")

        # Batch header
        header = ET.SubElement(root, "BatchHeader")
        ET.SubElement(header, "BankId").text = self.config.bank_id
        ET.SubElement(header, "BatchId").text = batch.batch_number
        ET.SubElement(header, "BatchUUID").text = batch.id
        ET.SubElement(header, "GeneratedAt").text = datetime.now(timezone.utc).isoformat()
        ET.SubElement(header, "RecordCount").text = str(len(records))
        ET.SubElement(header, "TotalAmount").text = str(sum(r.transaction_amount for r in records))
        ET.SubElement(header, "BatchHash").text = batch.batch_hash or ""

        # Records
        records_elem = ET.SubElement(root, "Records")
        for record in records:
            record_elem = ET.SubElement(records_elem, "Record")
            record_elem.set("sequenceNumber", str(record.sequence_number))

            data = self._format_record(record)
            for key, value in data.items():
                if value:  # Skip empty values
                    ET.SubElement(record_elem, self._to_pascal_case(key)).text = value

        # Checksum element (will be filled after)
        if self.config.include_checksum:
            ET.SubElement(root, "Checksum").text = "PLACEHOLDER"

        # Generate XML string
        xml_str = ET.tostring(root, encoding="unicode", xml_declaration=True)

        # Add checksum
        if self.config.include_checksum:
            content_for_hash = xml_str.replace("PLACEHOLDER", "")
            checksum = hashlib.sha256(content_for_hash.encode()).hexdigest()
            xml_str = xml_str.replace("PLACEHOLDER", checksum)

        return xml_str.encode(self.config.file_encoding)

    def _to_pascal_case(self, snake_str: str) -> str:
        """Convert snake_case to PascalCase."""
        components = snake_str.split("_")
        return "".join(x.title() for x in components)


def get_file_generator(config: BankConnectorConfig) -> FileGenerator:
    """Factory to get appropriate file generator."""
    generators = {
        FileFormat.CSV: CSVGenerator,
        FileFormat.FIXED_WIDTH: FixedWidthGenerator,
        FileFormat.XML: XMLGenerator,
    }
    generator_class = generators.get(config.file_format, CSVGenerator)
    return generator_class(config)


# =============================================================================
# CONNECTOR SERVICE
# =============================================================================


class ConnectorService:
    """
    Main service for Connector B batch commit operations.

    Handles the complete lifecycle:
    1. Batch creation (from approved decisions)
    2. Dual control approval
    3. File generation
    4. Acknowledgement processing
    5. Reconciliation
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    # -------------------------------------------------------------------------
    # Batch Creation
    # -------------------------------------------------------------------------

    async def create_batch(
        self,
        tenant_id: str,
        bank_config_id: str,
        decision_ids: list[str],
        user_id: str,
        description: str | None = None,
    ) -> CommitBatch:
        """
        Create a new commit batch from approved decisions.

        All decisions must have dual control approval before being
        included in a batch. The batch itself requires separate
        dual control approval before file generation.
        """
        # Get bank config
        config_result = await self.db.execute(
            select(BankConnectorConfig).where(
                BankConnectorConfig.id == bank_config_id,
                BankConnectorConfig.tenant_id == tenant_id,
                BankConnectorConfig.is_active == True,
            )
        )
        bank_config = config_result.scalar_one_or_none()
        if not bank_config:
            raise ConnectorError("Bank configuration not found or inactive")

        # Get decisions with dual control verification
        decisions_result = await self.db.execute(
            select(Decision)
            .options(selectinload(Decision.check_item))
            .where(
                Decision.id.in_(decision_ids),
                Decision.is_dual_control_required == True,
                Decision.dual_control_approved_at.isnot(None),
            )
        )
        decisions = decisions_result.scalars().all()

        if len(decisions) != len(decision_ids):
            missing = set(decision_ids) - {d.id for d in decisions}
            raise DualControlViolation(f"Decisions missing dual control approval: {missing}")

        # Generate batch number
        batch_number = (
            f"B{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:8].upper()}"
        )

        # Create batch
        batch = CommitBatch(
            tenant_id=tenant_id,
            batch_number=batch_number,
            bank_config_id=bank_config_id,
            description=description,
            status=BatchStatus.PENDING,
            total_records=len(decisions),
            created_by_user_id=user_id,
        )
        self.db.add(batch)
        await self.db.flush()

        # Create records
        record_hashes = []
        total_amount = Decimal("0.00")
        decision_counts = {
            "release": 0,
            "hold": 0,
            "return": 0,
            "reject": 0,
            "escalate": 0,
        }
        high_risk_count = 0

        for seq, decision in enumerate(decisions, start=1):
            check_item = decision.check_item

            # Map decision action to commit decision type
            decision_type = self._map_decision_type(decision.action)
            decision_counts[decision_type.value] = decision_counts.get(decision_type.value, 0) + 1

            # Generate decision hash
            decision_hash = generate_decision_hash(
                decision_id=decision.id,
                check_item_id=check_item.id,
                decision_type=decision_type.value,
                amount=check_item.amount,
                decision_timestamp=decision.dual_control_approved_at or decision.created_at,
            )
            record_hashes.append(decision_hash)

            # Build evidence snapshot
            evidence = build_evidence_snapshot(check_item, decision)

            # Check high risk
            if check_item.risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL):
                high_risk_count += 1

            # Create record
            record = CommitRecord(
                batch_id=batch.id,
                sequence_number=seq,
                decision_id=decision.id,
                check_item_id=check_item.id,
                decision_hash=decision_hash,
                status=RecordStatus.PENDING,
                decision_type=decision_type,
                bank_id=bank_config.bank_id,
                account_number_masked=check_item.account_number_masked,
                routing_number=check_item.routing_number,
                item_id=check_item.external_item_id,
                transaction_amount=check_item.amount,
                micr_line=check_item.micr_line,
                reviewer_user_id=decision.user_id,
                approver_user_id=decision.dual_control_approver_id,
                decision_timestamp=decision.dual_control_approved_at or decision.created_at,
                notes=decision.notes if bank_config.include_notes else None,
                evidence_snapshot=evidence,
            )
            self.db.add(record)

            total_amount += check_item.amount

        # Update batch aggregates
        batch.total_amount = total_amount
        batch.release_count = decision_counts["release"]
        batch.hold_count = decision_counts["hold"]
        batch.return_count = decision_counts["return"]
        batch.reject_count = decision_counts["reject"]
        batch.escalate_count = decision_counts["escalate"]
        batch.has_high_risk_items = high_risk_count > 0
        batch.high_risk_count = high_risk_count
        batch.batch_hash = generate_batch_hash(record_hashes)

        await self.db.flush()
        return batch

    def _map_decision_type(self, action: DecisionAction) -> CommitDecisionType:
        """Map decision action to commit decision type."""
        mapping = {
            DecisionAction.APPROVE: CommitDecisionType.RELEASE,
            DecisionAction.RETURN: CommitDecisionType.RETURN,
            DecisionAction.REJECT: CommitDecisionType.REJECT,
            DecisionAction.HOLD: CommitDecisionType.HOLD,
            DecisionAction.ESCALATE: CommitDecisionType.ESCALATE,
        }
        return mapping.get(action, CommitDecisionType.RELEASE)

    # -------------------------------------------------------------------------
    # Batch Approval (Dual Control)
    # -------------------------------------------------------------------------

    async def approve_batch(
        self,
        batch_id: str,
        approver_user_id: str,
        approval_notes: str | None = None,
    ) -> CommitBatch:
        """
        Approve a batch for file generation.

        Enforces dual control - approver must be different from creator.
        """
        batch = await self._get_batch(batch_id)

        if batch.status != BatchStatus.PENDING:
            raise BatchStateError(f"Batch is not pending approval (status: {batch.status})")

        if batch.created_by_user_id == approver_user_id:
            raise DualControlViolation("Cannot approve your own batch (dual control)")

        batch.approver_user_id = approver_user_id
        batch.approved_at = datetime.now(timezone.utc)
        batch.approval_notes = approval_notes
        batch.status = BatchStatus.APPROVED

        await self.db.flush()
        return batch

    async def cancel_batch(
        self,
        batch_id: str,
        user_id: str,
        reason: str,
    ) -> CommitBatch:
        """Cancel a batch before file generation."""
        batch = await self._get_batch(batch_id)

        if batch.status not in (BatchStatus.PENDING, BatchStatus.APPROVED):
            raise BatchStateError(f"Cannot cancel batch in status: {batch.status}")

        batch.status = BatchStatus.CANCELLED
        batch.cancelled_at = datetime.now(timezone.utc)
        batch.cancelled_by_user_id = user_id
        batch.cancellation_reason = reason

        await self.db.flush()
        return batch

    # -------------------------------------------------------------------------
    # File Generation
    # -------------------------------------------------------------------------

    async def generate_file(self, batch_id: str) -> tuple[str, bytes, str]:
        """
        Generate commit file for an approved batch.

        Returns: (file_name, file_content, checksum)
        """
        batch = await self._get_batch(batch_id, include_records=True, include_config=True)

        if batch.status != BatchStatus.APPROVED:
            raise BatchStateError(
                f"Batch is not approved for file generation (status: {batch.status})"
            )

        try:
            batch.status = BatchStatus.GENERATING
            await self.db.flush()

            # Get generator for this bank's format
            generator = get_file_generator(batch.bank_config)

            # Generate file content
            content = generator.generate(batch, batch.records)
            file_name = generator.get_file_name(batch)
            checksum = generate_file_checksum(content)

            # Verify determinism - regenerating should produce same hash
            # (Batch hash should match if records haven't changed)
            record_hashes = [r.decision_hash for r in batch.records]
            regenerated_batch_hash = generate_batch_hash(record_hashes)
            if regenerated_batch_hash != batch.batch_hash:
                raise FileGenerationError("Batch hash mismatch - records may have changed")

            # Update batch
            batch.status = BatchStatus.GENERATED
            batch.file_generated_at = datetime.now(timezone.utc)
            batch.file_name = file_name
            batch.file_checksum = checksum
            batch.file_size_bytes = len(content)
            batch.file_record_count = len(batch.records)

            # Update record statuses
            for record in batch.records:
                record.status = RecordStatus.INCLUDED

            await self.db.flush()
            return file_name, content, checksum

        except Exception as e:
            batch.status = BatchStatus.FAILED
            await self.db.flush()
            raise FileGenerationError(f"File generation failed: {str(e)}") from e

    async def mark_transmitted(
        self,
        batch_id: str,
        transmission_id: str | None = None,
    ) -> CommitBatch:
        """Mark batch as transmitted to bank."""
        batch = await self._get_batch(batch_id, include_records=True)

        if batch.status != BatchStatus.GENERATED:
            raise BatchStateError(f"Batch not ready for transmission (status: {batch.status})")

        batch.status = BatchStatus.TRANSMITTED
        batch.transmitted_at = datetime.now(timezone.utc)
        batch.transmission_id = transmission_id

        # Update record statuses
        for record in batch.records:
            record.status = RecordStatus.TRANSMITTED

        await self.db.flush()
        return batch

    # -------------------------------------------------------------------------
    # Acknowledgement Processing
    # -------------------------------------------------------------------------

    async def process_acknowledgement(
        self,
        batch_id: str,
        ack_data: dict[str, Any],
        user_id: str | None = None,
    ) -> BatchAcknowledgement:
        """
        Process acknowledgement from bank middleware.

        ack_data structure:
        {
            "status": "accepted|rejected|partially_processed",
            "bank_reference_id": "...",
            "records": [
                {"decision_hash": "...", "status": "accepted|rejected", "core_ref": "...", "error": "..."},
                ...
            ]
        }
        """
        batch = await self._get_batch(batch_id, include_records=True)

        if batch.status not in (BatchStatus.TRANSMITTED, BatchStatus.PARTIALLY_PROCESSED):
            raise BatchStateError(f"Batch not awaiting acknowledgement (status: {batch.status})")

        # Parse acknowledgement
        ack_status = AcknowledgementStatus(ack_data.get("status", "pending"))
        record_details = ack_data.get("records", [])

        # Count results
        accepted_count = 0
        rejected_count = 0
        pending_count = 0

        # Build lookup for records
        records_by_hash = {r.decision_hash: r for r in batch.records}

        processed_details = []
        for detail in record_details:
            decision_hash = detail.get("decision_hash")
            record_status = detail.get("status", "pending")

            record = records_by_hash.get(decision_hash)
            if record:
                if record_status == "accepted":
                    record.status = RecordStatus.ACCEPTED
                    record.core_reference_id = detail.get("core_ref")
                    record.processed_at = datetime.now(timezone.utc)
                    accepted_count += 1
                elif record_status == "rejected":
                    record.status = RecordStatus.REJECTED
                    record.error_category = ErrorCategory(
                        detail.get("error_category", "business_rule")
                    )
                    record.error_code = detail.get("error_code")
                    record.error_message = detail.get("error")
                    rejected_count += 1
                else:
                    pending_count += 1

            processed_details.append(
                {
                    "record_id": record.id if record else None,
                    "decision_hash": decision_hash,
                    "status": record_status,
                    "core_ref": detail.get("core_ref"),
                    "error": detail.get("error"),
                }
            )

        # Create acknowledgement record
        ack = BatchAcknowledgement(
            batch_id=batch_id,
            ack_file_received_at=datetime.now(timezone.utc),
            status=ack_status,
            bank_reference_id=ack_data.get("bank_reference_id"),
            bank_batch_id=ack_data.get("bank_batch_id"),
            total_records=len(record_details),
            accepted_count=accepted_count,
            rejected_count=rejected_count,
            pending_count=pending_count,
            record_details=processed_details,
            processed_at=datetime.now(timezone.utc),
            processed_by_user_id=user_id,
            raw_ack_data=ack_data,
        )
        self.db.add(ack)

        # Update batch status
        if ack_status == AcknowledgementStatus.ACCEPTED:
            batch.status = BatchStatus.COMPLETED
        elif ack_status == AcknowledgementStatus.REJECTED:
            batch.status = BatchStatus.FAILED
        else:
            batch.status = BatchStatus.PARTIALLY_PROCESSED

        batch.acknowledged_at = datetime.now(timezone.utc)
        batch.ack_status = ack_status
        batch.ack_reference = ack_data.get("bank_reference_id")
        batch.records_accepted = accepted_count
        batch.records_rejected = rejected_count
        batch.records_pending = pending_count

        await self.db.flush()
        return ack

    # -------------------------------------------------------------------------
    # Reconciliation
    # -------------------------------------------------------------------------

    async def generate_reconciliation_report(
        self,
        tenant_id: str,
        report_date: datetime,
        user_id: str | None = None,
    ) -> ReconciliationReport:
        """Generate daily reconciliation report."""
        # Define period (full day in UTC)
        period_start = report_date.replace(hour=0, minute=0, second=0, microsecond=0)
        period_end = report_date.replace(hour=23, minute=59, second=59, microsecond=999999)

        # Get all batches in period
        batches_result = await self.db.execute(
            select(CommitBatch)
            .options(selectinload(CommitBatch.records))
            .where(
                CommitBatch.tenant_id == tenant_id,
                CommitBatch.created_at >= period_start,
                CommitBatch.created_at <= period_end,
            )
        )
        batches = batches_result.scalars().all()

        # Calculate aggregates
        decisions_approved = sum(
            b.total_records for b in batches if b.status != BatchStatus.CANCELLED
        )
        decisions_amount = sum(b.total_amount for b in batches if b.status != BatchStatus.CANCELLED)

        files_generated = len([b for b in batches if b.file_generated_at])
        files_transmitted = len([b for b in batches if b.transmitted_at])

        records_included = sum(b.file_record_count or 0 for b in batches)
        records_accepted = sum(b.records_accepted or 0 for b in batches)
        records_rejected = sum(b.records_rejected or 0 for b in batches)
        records_pending = sum(b.records_pending or 0 for b in batches)

        # Calculate amounts by type
        release_amount = Decimal("0.00")
        hold_amount = Decimal("0.00")
        return_amount = Decimal("0.00")
        reject_amount = Decimal("0.00")

        for batch in batches:
            for record in batch.records:
                if record.decision_type == CommitDecisionType.RELEASE:
                    release_amount += record.transaction_amount
                elif record.decision_type in (
                    CommitDecisionType.HOLD,
                    CommitDecisionType.EXTEND_HOLD,
                ):
                    hold_amount += record.transaction_amount
                elif record.decision_type == CommitDecisionType.RETURN:
                    return_amount += record.transaction_amount
                elif record.decision_type == CommitDecisionType.REJECT:
                    reject_amount += record.transaction_amount

        # Count exceptions
        exceptions_new = sum(
            1
            for b in batches
            for r in b.records
            if r.status == RecordStatus.REJECTED and r.created_at >= period_start
        )
        exceptions_resolved = sum(
            1
            for b in batches
            for r in b.records
            if r.status == RecordStatus.MANUALLY_RESOLVED
            and r.manually_resolved_at
            and r.manually_resolved_at >= period_start
        )
        exceptions_outstanding = sum(
            1
            for b in batches
            for r in b.records
            if r.status in (RecordStatus.REJECTED, RecordStatus.FAILED)
            and r.manually_resolved_at is None
        )

        # Create report
        report = ReconciliationReport(
            tenant_id=tenant_id,
            report_date=report_date,
            period_start=period_start,
            period_end=period_end,
            decisions_approved=decisions_approved,
            decisions_amount_total=decisions_amount,
            files_generated=files_generated,
            files_transmitted=files_transmitted,
            records_included=records_included,
            records_accepted=records_accepted,
            records_rejected=records_rejected,
            records_pending=records_pending,
            exceptions_new=exceptions_new,
            exceptions_resolved=exceptions_resolved,
            exceptions_outstanding=exceptions_outstanding,
            release_amount=release_amount,
            hold_amount=hold_amount,
            return_amount=return_amount,
            reject_amount=reject_amount,
            batch_ids=[b.id for b in batches],
            generated_at=datetime.now(timezone.utc),
            generated_by_user_id=user_id,
        )
        self.db.add(report)
        await self.db.flush()

        return report

    # -------------------------------------------------------------------------
    # Query Methods
    # -------------------------------------------------------------------------

    async def get_batch(self, batch_id: str) -> CommitBatch | None:
        """Get batch by ID."""
        return await self._get_batch(batch_id, include_records=True)

    async def list_batches(
        self,
        tenant_id: str,
        status: BatchStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[CommitBatch], int]:
        """List batches with optional status filter."""
        query = select(CommitBatch).where(CommitBatch.tenant_id == tenant_id)

        if status:
            query = query.where(CommitBatch.status == status)

        # Count
        count_result = await self.db.execute(select(func.count()).select_from(query.subquery()))
        total = count_result.scalar() or 0

        # Fetch
        query = query.order_by(CommitBatch.created_at.desc()).offset(offset).limit(limit)
        result = await self.db.execute(query)
        batches = result.scalars().all()

        return list(batches), total

    async def get_pending_batches(self, tenant_id: str) -> list[CommitBatch]:
        """Get batches pending approval."""
        result = await self.db.execute(
            select(CommitBatch)
            .where(
                CommitBatch.tenant_id == tenant_id,
                CommitBatch.status == BatchStatus.PENDING,
            )
            .order_by(CommitBatch.created_at)
        )
        return list(result.scalars().all())

    async def get_awaiting_ack_batches(self, tenant_id: str) -> list[CommitBatch]:
        """Get batches awaiting acknowledgement."""
        result = await self.db.execute(
            select(CommitBatch)
            .where(
                CommitBatch.tenant_id == tenant_id,
                CommitBatch.status == BatchStatus.TRANSMITTED,
            )
            .order_by(CommitBatch.transmitted_at)
        )
        return list(result.scalars().all())

    async def get_failed_records(
        self,
        tenant_id: str,
        limit: int = 100,
    ) -> list[CommitRecord]:
        """Get failed records requiring attention."""
        result = await self.db.execute(
            select(CommitRecord)
            .join(CommitBatch)
            .where(
                CommitBatch.tenant_id == tenant_id,
                CommitRecord.status.in_([RecordStatus.REJECTED, RecordStatus.FAILED]),
                CommitRecord.manually_resolved_at.is_(None),
            )
            .order_by(CommitRecord.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def resolve_record(
        self,
        record_id: str,
        user_id: str,
        resolution_notes: str,
    ) -> CommitRecord:
        """Manually resolve a failed record."""
        result = await self.db.execute(select(CommitRecord).where(CommitRecord.id == record_id))
        record = result.scalar_one_or_none()

        if not record:
            raise ConnectorError("Record not found")

        if record.status not in (RecordStatus.REJECTED, RecordStatus.FAILED):
            raise BatchStateError(f"Record not in failed state (status: {record.status})")

        record.status = RecordStatus.MANUALLY_RESOLVED
        record.manually_resolved_at = datetime.now(timezone.utc)
        record.manually_resolved_by_user_id = user_id
        record.resolution_notes = resolution_notes

        await self.db.flush()
        return record

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------

    async def _get_batch(
        self,
        batch_id: str,
        include_records: bool = False,
        include_config: bool = False,
    ) -> CommitBatch:
        """Get batch by ID with optional eager loading."""
        query = select(CommitBatch).where(CommitBatch.id == batch_id)

        if include_records:
            query = query.options(selectinload(CommitBatch.records))
        if include_config:
            query = query.options(selectinload(CommitBatch.bank_config))

        result = await self.db.execute(query)
        batch = result.scalar_one_or_none()

        if not batch:
            raise BatchNotFoundError(f"Batch not found: {batch_id}")

        return batch
