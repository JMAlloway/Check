"""Audit logging service."""

from datetime import datetime, timezone
import json
import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditAction, AuditLog, ItemView


# =============================================================================
# PII Redaction for Audit Logs
# =============================================================================

# Fields that should always be redacted
PII_FIELDS = {
    # Account/routing information
    "account_number", "routing_number", "micr_line", "micr_account", "micr_routing",
    "aba_number", "bank_account",
    # Personal identifiers
    "ssn", "social_security", "tax_id", "ein", "tin",
    # Contact information
    "phone", "phone_number", "mobile", "telephone",
    # Financial data
    "card_number", "credit_card", "debit_card", "cvv", "pin",
    # Authentication secrets
    "password", "hashed_password", "mfa_secret", "secret_key", "api_key",
    # Full address components
    "street_address", "address_line",
}

# Patterns to detect and redact PII values
PII_PATTERNS = [
    # SSN: XXX-XX-XXXX or XXXXXXXXX
    (re.compile(r'\b\d{3}-\d{2}-\d{4}\b'), "[SSN_REDACTED]"),
    (re.compile(r'\b\d{9}\b(?!\d)'), "[SSN_REDACTED]"),
    # Account numbers (9-17 digits, common bank account lengths)
    (re.compile(r'\b\d{9,17}\b'), "[ACCOUNT_REDACTED]"),
    # Routing numbers (9 digits starting with 0-3)
    (re.compile(r'\b[0-3]\d{8}\b'), "[ROUTING_REDACTED]"),
    # Credit card numbers (13-19 digits, possibly with spaces/dashes)
    (re.compile(r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{1,7}\b'), "[CARD_REDACTED]"),
    # Phone numbers (various formats)
    (re.compile(r'\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b'), "[PHONE_REDACTED]"),
    (re.compile(r'\(\d{3}\)\s?\d{3}[-.\s]?\d{4}'), "[PHONE_REDACTED]"),
]


def redact_pii_value(value: Any) -> Any:
    """Redact PII from a single value.

    Handles strings, dicts, and lists recursively.
    """
    if value is None:
        return None

    if isinstance(value, str):
        result = value
        for pattern, replacement in PII_PATTERNS:
            result = pattern.sub(replacement, result)
        return result

    if isinstance(value, dict):
        return redact_pii_dict(value)

    if isinstance(value, list):
        return [redact_pii_value(item) for item in value]

    # For other types (int, float, bool), return as-is
    return value


def redact_pii_dict(data: dict | None) -> dict | None:
    """Redact PII from a dictionary.

    - Redacts values of known PII field names
    - Scans string values for PII patterns
    - Recursively handles nested dicts and lists
    """
    if not data:
        return data

    result = {}
    for key, value in data.items():
        key_lower = key.lower()

        # Check if field name indicates PII
        if key_lower in PII_FIELDS:
            if value is not None:
                # Preserve type indicator but redact value
                if isinstance(value, str) and len(value) > 4:
                    # Show last 4 chars for account numbers
                    result[key] = f"****{value[-4:]}"
                else:
                    result[key] = "[REDACTED]"
            else:
                result[key] = None
        elif isinstance(value, dict):
            result[key] = redact_pii_dict(value)
        elif isinstance(value, list):
            result[key] = [redact_pii_value(item) for item in value]
        elif isinstance(value, str):
            # Scan string values for PII patterns
            result[key] = redact_pii_value(value)
        else:
            result[key] = value

    return result


class AuditService:
    """
    Service for recording and querying audit logs.

    All audit entries are immutable and designed for compliance requirements.
    Implements blockchain-like chain integrity via previous_hash linking.
    """

    # Genesis marker for the first entry in a tenant's audit chain
    GENESIS_HASH = "genesis"

    def __init__(self, db: AsyncSession):
        self.db = db

    async def _get_previous_hash(self, tenant_id: str | None) -> str:
        """Get the integrity_hash of the most recent audit log entry for a tenant.

        This creates the chain link for blockchain-like integrity verification.
        For the first entry in a tenant (or system-level entries), returns "genesis".

        Args:
            tenant_id: The tenant ID to get the previous hash for.
                      If None, looks for system-level entries (tenant_id IS NULL).

        Returns:
            The integrity_hash of the previous entry, or "genesis" if no previous entry.
        """
        if tenant_id:
            query = (
                select(AuditLog.integrity_hash)
                .where(AuditLog.tenant_id == tenant_id)
                .order_by(AuditLog.timestamp.desc(), AuditLog.id.desc())
                .limit(1)
            )
        else:
            # System-level entries (no tenant)
            query = (
                select(AuditLog.integrity_hash)
                .where(AuditLog.tenant_id.is_(None))
                .order_by(AuditLog.timestamp.desc(), AuditLog.id.desc())
                .limit(1)
            )

        result = await self.db.execute(query)
        previous_hash = result.scalar_one_or_none()

        return previous_hash if previous_hash else self.GENESIS_HASH

    async def log(
        self,
        action: AuditAction,
        resource_type: str,
        resource_id: str | None = None,
        user_id: str | None = None,
        username: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        description: str | None = None,
        before_value: dict | None = None,
        after_value: dict | None = None,
        metadata: dict | None = None,
        session_id: str | None = None,
        tenant_id: str | None = None,  # Multi-tenant support
    ) -> AuditLog:
        """
        Create an immutable audit log entry with chain integrity.

        The entry is linked to the previous entry via previous_hash, creating
        a blockchain-like chain that enables detection of any tampering.

        Args:
            action: The type of action being logged
            resource_type: The type of resource (e.g., "check_item", "user")
            resource_id: The ID of the resource being acted upon
            user_id: The ID of the user performing the action
            username: The username (denormalized for historical reference)
            ip_address: The client IP address
            user_agent: The client user agent string
            description: Human-readable description of the action
            before_value: State before the action (for changes)
            after_value: State after the action (for changes)
            metadata: Additional context as JSON
            session_id: The user's session ID
            tenant_id: The tenant ID for multi-tenant isolation

        Returns:
            The created AuditLog entry with integrity_hash and previous_hash set
        """
        # SECURITY: Redact PII from before_value, after_value, and metadata
        # This prevents sensitive data from being stored in audit logs
        redacted_before = redact_pii_dict(before_value) if before_value else None
        redacted_after = redact_pii_dict(after_value) if after_value else None
        redacted_metadata = redact_pii_dict(metadata) if metadata else None

        # Get the previous entry's hash for chain integrity
        previous_hash = await self._get_previous_hash(tenant_id)

        log_entry = AuditLog(
            tenant_id=tenant_id,  # Multi-tenant isolation
            timestamp=datetime.now(timezone.utc),
            user_id=user_id,
            username=username,
            ip_address=ip_address,
            user_agent=user_agent,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            description=description,
            before_value=json.dumps(redacted_before) if redacted_before else None,
            after_value=json.dumps(redacted_after) if redacted_after else None,
            extra_data=json.dumps(redacted_metadata) if redacted_metadata else None,
            session_id=session_id,
            previous_hash=previous_hash,  # Chain link to previous entry
        )

        self.db.add(log_entry)
        await self.db.flush()

        # Compute and store integrity hash after flush (when ID is assigned)
        # This hash includes the previous_hash, completing the chain link
        log_entry.integrity_hash = log_entry.compute_integrity_hash(previous_hash)
        await self.db.flush()

        return log_entry

    async def log_item_viewed(
        self,
        check_item_id: str,
        user_id: str,
        tenant_id: str,  # Multi-tenant required
        username: str | None = None,
        ip_address: str | None = None,
        session_id: str | None = None,
    ) -> ItemView:
        """Start tracking an item view session."""
        view = ItemView(
            tenant_id=tenant_id,  # Multi-tenant isolation
            check_item_id=check_item_id,
            user_id=user_id,
            session_id=session_id,
            view_started_at=datetime.now(timezone.utc),
        )
        self.db.add(view)
        await self.db.flush()

        # Also create audit log entry
        await self.log(
            action=AuditAction.ITEM_VIEWED,
            resource_type="check_item",
            resource_id=check_item_id,
            user_id=user_id,
            username=username,
            ip_address=ip_address,
            session_id=session_id,
            description=f"User viewed check item",
        )

        return view

    async def update_item_view(
        self,
        view_id: str,
        front_image_viewed: bool | None = None,
        back_image_viewed: bool | None = None,
        zoom_used: bool | None = None,
        magnifier_used: bool | None = None,
        history_compared: bool | None = None,
        ai_assists_viewed: bool | None = None,
        context_panel_viewed: bool | None = None,
    ) -> ItemView | None:
        """Update item view tracking with interaction details."""
        result = await self.db.execute(select(ItemView).where(ItemView.id == view_id))
        view = result.scalar_one_or_none()

        if not view:
            return None

        if front_image_viewed is not None:
            view.front_image_viewed = front_image_viewed
        if back_image_viewed is not None:
            view.back_image_viewed = back_image_viewed
        if zoom_used is not None:
            view.zoom_used = zoom_used
        if magnifier_used is not None:
            view.magnifier_used = magnifier_used
        if history_compared is not None:
            view.history_compared = history_compared
        if ai_assists_viewed is not None:
            view.ai_assists_viewed = ai_assists_viewed
        if context_panel_viewed is not None:
            view.context_panel_viewed = context_panel_viewed

        return view

    async def end_item_view(self, view_id: str) -> ItemView | None:
        """End an item view session and calculate duration."""
        result = await self.db.execute(select(ItemView).where(ItemView.id == view_id))
        view = result.scalar_one_or_none()

        if not view:
            return None

        view.view_ended_at = datetime.now(timezone.utc)
        view.duration_seconds = int(
            (view.view_ended_at - view.view_started_at).total_seconds()
        )

        # Save interaction summary
        view.interaction_summary = json.dumps({
            "front_image_viewed": view.front_image_viewed,
            "back_image_viewed": view.back_image_viewed,
            "zoom_used": view.zoom_used,
            "magnifier_used": view.magnifier_used,
            "history_compared": view.history_compared,
            "ai_assists_viewed": view.ai_assists_viewed,
            "context_panel_viewed": view.context_panel_viewed,
            "duration_seconds": view.duration_seconds,
        })

        return view

    async def log_decision(
        self,
        check_item_id: str,
        user_id: str,
        username: str | None,
        decision_type: str,
        action: str,
        reason_codes: list[str],
        notes: str | None,
        ip_address: str | None = None,
        session_id: str | None = None,
        before_status: str | None = None,
        after_status: str | None = None,
    ) -> AuditLog:
        """Log a decision on a check item."""
        return await self.log(
            action=AuditAction.DECISION_MADE,
            resource_type="check_item",
            resource_id=check_item_id,
            user_id=user_id,
            username=username,
            ip_address=ip_address,
            session_id=session_id,
            description=f"User made {decision_type} decision: {action}",
            before_value={"status": before_status} if before_status else None,
            after_value={"status": after_status} if after_status else None,
            metadata={
                "decision_type": decision_type,
                "action": action,
                "reason_codes": reason_codes,
                "notes": notes,
            },
        )

    async def get_item_audit_trail(
        self,
        item_id: str,
        tenant_id: str,  # Multi-tenant required
        limit: int = 100,
    ) -> list[AuditLog]:
        """Get complete audit trail for a check item."""
        # CRITICAL: Filter by tenant_id for multi-tenant security
        result = await self.db.execute(
            select(AuditLog)
            .where(
                AuditLog.tenant_id == tenant_id,
                AuditLog.resource_type == "check_item",
                AuditLog.resource_id == item_id,
            )
            .order_by(AuditLog.timestamp.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_user_activity(
        self,
        user_id: str,
        tenant_id: str,  # Multi-tenant required
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        limit: int = 100,
    ) -> list[AuditLog]:
        """Get audit log entries for a specific user."""
        # CRITICAL: Filter by tenant_id for multi-tenant security
        query = select(AuditLog).where(
            AuditLog.tenant_id == tenant_id,
            AuditLog.user_id == user_id,
        )

        if date_from:
            query = query.where(AuditLog.timestamp >= date_from)
        if date_to:
            query = query.where(AuditLog.timestamp <= date_to)

        query = query.order_by(AuditLog.timestamp.desc()).limit(limit)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def search_audit_logs(
        self,
        tenant_id: str,  # Multi-tenant required
        action: AuditAction | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        user_id: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[AuditLog], int]:
        """Search audit logs with filters."""
        from sqlalchemy import func

        query = select(AuditLog)
        count_query = select(func.count(AuditLog.id))

        # CRITICAL: Always filter by tenant_id for multi-tenant security
        conditions = [AuditLog.tenant_id == tenant_id]
        if action:
            conditions.append(AuditLog.action == action)
        if resource_type:
            conditions.append(AuditLog.resource_type == resource_type)
        if resource_id:
            conditions.append(AuditLog.resource_id == resource_id)
        if user_id:
            conditions.append(AuditLog.user_id == user_id)
        if date_from:
            conditions.append(AuditLog.timestamp >= date_from)
        if date_to:
            conditions.append(AuditLog.timestamp <= date_to)

        from sqlalchemy import and_
        query = query.where(and_(*conditions))
        count_query = count_query.where(and_(*conditions))

        # Get total count
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        # Apply pagination
        query = query.order_by(AuditLog.timestamp.desc())
        query = query.offset((page - 1) * page_size).limit(page_size)

        result = await self.db.execute(query)
        logs = list(result.scalars().all())

        return logs, total

    # =========================================================================
    # Convenience methods for consistent audit logging
    # =========================================================================

    async def log_auth_failure(
        self,
        failure_type: str,
        user_id: str,
        username: str,
        resource: str,
        action: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
        reason: str | None = None,
    ) -> AuditLog:
        """
        Log an authorization failure.

        These are critical for security monitoring and should be:
        - Shipped to SIEM in real-time
        - Subject to anomaly detection rules
        - Reviewed in security audits
        """
        action_map = {
            "permission_denied": AuditAction.AUTH_PERMISSION_DENIED,
            "role_denied": AuditAction.AUTH_ROLE_DENIED,
            "entitlement_denied": AuditAction.AUTH_ENTITLEMENT_DENIED,
            "ip_denied": AuditAction.AUTH_IP_DENIED,
        }
        audit_action = action_map.get(failure_type, AuditAction.UNAUTHORIZED_ACCESS)

        return await self.log(
            action=audit_action,
            resource_type=resource,
            user_id=user_id,
            username=username,
            ip_address=ip_address,
            user_agent=user_agent,
            description=f"Authorization denied: {failure_type} for {action} on {resource}",
            metadata={
                "failure_type": failure_type,
                "requested_action": action,
                "reason": reason,
            },
        )

    async def log_decision_failure(
        self,
        check_item_id: str,
        user_id: str,
        username: str,
        failure_type: str,
        attempted_action: str,
        reason: str,
        ip_address: str | None = None,
    ) -> AuditLog:
        """
        Log a failed decision attempt.

        This captures cases where a user tried to make a decision but was
        blocked by validation, entitlements, or business rules.
        """
        action_map = {
            "validation": AuditAction.DECISION_VALIDATION_FAILED,
            "entitlement": AuditAction.DECISION_ENTITLEMENT_FAILED,
            "general": AuditAction.DECISION_FAILED,
        }
        audit_action = action_map.get(failure_type, AuditAction.DECISION_FAILED)

        return await self.log(
            action=audit_action,
            resource_type="check_item",
            resource_id=check_item_id,
            user_id=user_id,
            username=username,
            ip_address=ip_address,
            description=f"Decision attempt failed: {reason}",
            metadata={
                "failure_type": failure_type,
                "attempted_action": attempted_action,
                "reason": reason,
            },
        )

    async def log_decision_override(
        self,
        check_item_id: str,
        decision_id: str,
        user_id: str,
        username: str,
        override_type: str,
        original_action: str,
        new_action: str,
        justification: str,
        ip_address: str | None = None,
        supervisor_id: str | None = None,
    ) -> AuditLog:
        """
        Log a decision override or reversal.

        Override types:
        - "override": Supervisor overriding a reviewer's decision
        - "reversal": Reversing a previously made decision
        - "amendment": Modifying a decision (e.g., changing return reason)
        """
        action_map = {
            "override": AuditAction.DECISION_OVERRIDDEN,
            "reversal": AuditAction.DECISION_REVERSED,
            "amendment": AuditAction.DECISION_AMENDED,
        }
        audit_action = action_map.get(override_type, AuditAction.DECISION_OVERRIDDEN)

        return await self.log(
            action=audit_action,
            resource_type="decision",
            resource_id=decision_id,
            user_id=user_id,
            username=username,
            ip_address=ip_address,
            description=f"Decision {override_type}: {original_action} → {new_action}",
            before_value={"action": original_action},
            after_value={"action": new_action},
            metadata={
                "check_item_id": check_item_id,
                "override_type": override_type,
                "justification": justification,
                "supervisor_id": supervisor_id,
            },
        )

    async def log_ai_inference(
        self,
        check_item_id: str,
        user_id: str | None,
        username: str | None,
        inference_type: str,
        model_id: str,
        model_version: str,
        result_summary: dict,
        processing_time_ms: int | None = None,
        success: bool = True,
        error: str | None = None,
    ) -> AuditLog:
        """
        Log AI inference usage.

        This is critical for:
        - Model explainability audits
        - Tracking AI influence on decisions
        - Performance monitoring
        - Regulatory compliance (AI in financial decisions)
        """
        if success:
            audit_action = AuditAction.AI_INFERENCE_COMPLETED
            description = f"AI inference completed: {inference_type}"
        else:
            audit_action = AuditAction.AI_INFERENCE_FAILED
            description = f"AI inference failed: {inference_type} - {error}"

        return await self.log(
            action=audit_action,
            resource_type="check_item",
            resource_id=check_item_id,
            user_id=user_id,
            username=username,
            description=description,
            metadata={
                "inference_type": inference_type,
                "model_id": model_id,
                "model_version": model_version,
                "result_summary": result_summary,
                "processing_time_ms": processing_time_ms,
                "success": success,
                "error": error,
            },
        )

    async def log_ai_recommendation_action(
        self,
        check_item_id: str,
        user_id: str,
        username: str,
        recommendation_type: str,
        ai_recommendation: str,
        user_action: str,
        override_reason: str | None = None,
        ip_address: str | None = None,
    ) -> AuditLog:
        """
        Log user action on AI recommendation.

        Captures whether the user:
        - Accepted the AI recommendation
        - Rejected the AI recommendation
        - Overrode the AI recommendation with a different action
        """
        if user_action == ai_recommendation:
            audit_action = AuditAction.AI_RECOMMENDATION_ACCEPTED
        elif user_action == "rejected":
            audit_action = AuditAction.AI_RECOMMENDATION_REJECTED
        else:
            audit_action = AuditAction.AI_RECOMMENDATION_OVERRIDDEN

        return await self.log(
            action=audit_action,
            resource_type="check_item",
            resource_id=check_item_id,
            user_id=user_id,
            username=username,
            ip_address=ip_address,
            description=f"User {audit_action.value.replace('ai_recommendation_', '')}: AI recommended {ai_recommendation}, user chose {user_action}",
            metadata={
                "recommendation_type": recommendation_type,
                "ai_recommendation": ai_recommendation,
                "user_action": user_action,
                "override_reason": override_reason,
            },
        )

    async def log_dual_control(
        self,
        check_item_id: str,
        decision_id: str,
        event_type: str,
        user_id: str,
        username: str,
        original_reviewer_id: str | None = None,
        reason: str | None = None,
        ip_address: str | None = None,
    ) -> AuditLog:
        """
        Log dual control workflow events.

        Event types:
        - "required": Dual control was triggered
        - "approved": Second approver approved
        - "rejected": Second approver rejected
        - "expired": Dual control request expired
        """
        action_map = {
            "required": AuditAction.DUAL_CONTROL_REQUIRED,
            "approved": AuditAction.DUAL_CONTROL_APPROVED,
            "rejected": AuditAction.DUAL_CONTROL_REJECTED,
            "expired": AuditAction.DUAL_CONTROL_EXPIRED,
        }
        audit_action = action_map.get(event_type, AuditAction.DUAL_CONTROL_REQUIRED)

        return await self.log(
            action=audit_action,
            resource_type="decision",
            resource_id=decision_id,
            user_id=user_id,
            username=username,
            ip_address=ip_address,
            description=f"Dual control {event_type} for decision",
            metadata={
                "check_item_id": check_item_id,
                "original_reviewer_id": original_reviewer_id,
                "reason": reason,
            },
        )

    async def log_report_access(
        self,
        report_type: str,
        user_id: str,
        username: str,
        parameters: dict | None = None,
        exported: bool = False,
        ip_address: str | None = None,
    ) -> AuditLog:
        """Log report viewing or export."""
        if exported:
            audit_action = AuditAction.REPORT_EXPORTED
            description = f"User exported {report_type} report"
        else:
            audit_action = AuditAction.REPORT_VIEWED
            description = f"User viewed {report_type} report"

        return await self.log(
            action=audit_action,
            resource_type="report",
            resource_id=report_type,
            user_id=user_id,
            username=username,
            ip_address=ip_address,
            description=description,
            metadata={
                "report_type": report_type,
                "parameters": parameters,
                "exported": exported,
            },
        )

    # =========================================================================
    # Chain Integrity Verification
    # =========================================================================

    async def verify_chain_integrity(
        self,
        tenant_id: str,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        limit: int = 10000,
    ) -> dict:
        """
        Verify the integrity of the audit log chain for a tenant.

        This performs a blockchain-like verification:
        1. Fetches audit logs in chronological order
        2. Verifies each entry's integrity_hash matches its computed hash
        3. Verifies each entry's previous_hash matches the prior entry's integrity_hash
        4. Returns a report of any integrity violations

        Args:
            tenant_id: The tenant ID to verify
            start_date: Optional start date for verification range
            end_date: Optional end date for verification range
            limit: Maximum number of entries to verify (default 10000)

        Returns:
            Dict with verification results:
            {
                "verified": bool,
                "entries_checked": int,
                "first_entry_id": str,
                "last_entry_id": str,
                "violations": [
                    {"entry_id": str, "type": str, "details": str}
                ]
            }
        """
        from sqlalchemy import and_

        # Build query for chronological order
        conditions = [AuditLog.tenant_id == tenant_id]
        if start_date:
            conditions.append(AuditLog.timestamp >= start_date)
        if end_date:
            conditions.append(AuditLog.timestamp <= end_date)

        query = (
            select(AuditLog)
            .where(and_(*conditions))
            .order_by(AuditLog.timestamp.asc(), AuditLog.id.asc())
            .limit(limit)
        )

        result = await self.db.execute(query)
        logs = list(result.scalars().all())

        if not logs:
            return {
                "verified": True,
                "entries_checked": 0,
                "first_entry_id": None,
                "last_entry_id": None,
                "violations": [],
            }

        violations = []
        expected_previous_hash = self.GENESIS_HASH

        for i, log_entry in enumerate(logs):
            # Skip entries without previous_hash (pre-migration records)
            if log_entry.previous_hash is None:
                expected_previous_hash = log_entry.integrity_hash
                continue

            # Verify chain link (previous_hash matches expected)
            if log_entry.previous_hash != expected_previous_hash:
                violations.append({
                    "entry_id": str(log_entry.id),
                    "type": "chain_break",
                    "details": f"Entry {i}: previous_hash mismatch. "
                               f"Expected '{expected_previous_hash[:16]}...', "
                               f"got '{log_entry.previous_hash[:16] if log_entry.previous_hash else 'None'}...'",
                })

            # Verify entry integrity (integrity_hash is correct)
            if not log_entry.verify_integrity():
                violations.append({
                    "entry_id": str(log_entry.id),
                    "type": "integrity_failure",
                    "details": f"Entry {i}: integrity_hash verification failed. "
                               f"Record may have been tampered with.",
                })

            # Update expected previous hash for next iteration
            expected_previous_hash = log_entry.integrity_hash or expected_previous_hash

        return {
            "verified": len(violations) == 0,
            "entries_checked": len(logs),
            "first_entry_id": str(logs[0].id),
            "last_entry_id": str(logs[-1].id),
            "violations": violations,
        }
