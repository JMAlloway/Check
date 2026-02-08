"""Audit logging service."""

import json
from datetime import datetime, timezone
from typing import Any

from app.models.audit import AuditAction, AuditLog, ItemView
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class AuditService:
    """
    Service for recording and querying audit logs.

    All audit entries are immutable and designed for compliance requirements.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

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
        Create an immutable audit log entry.

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

        Returns:
            The created AuditLog entry
        """
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
            before_value=json.dumps(before_value) if before_value else None,
            after_value=json.dumps(after_value) if after_value else None,
            extra_data=json.dumps(metadata) if metadata else None,
            session_id=session_id,
        )

        self.db.add(log_entry)
        await self.db.flush()

        # Compute and store integrity hash after flush (ID is now assigned)
        log_entry.integrity_hash = log_entry.compute_integrity_hash()
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
            tenant_id=tenant_id,
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
        view.duration_seconds = int((view.view_ended_at - view.view_started_at).total_seconds())

        # Save interaction summary
        view.interaction_summary = json.dumps(
            {
                "front_image_viewed": view.front_image_viewed,
                "back_image_viewed": view.back_image_viewed,
                "zoom_used": view.zoom_used,
                "magnifier_used": view.magnifier_used,
                "history_compared": view.history_compared,
                "ai_assists_viewed": view.ai_assists_viewed,
                "context_panel_viewed": view.context_panel_viewed,
                "duration_seconds": view.duration_seconds,
            }
        )

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
        tenant_id: str,  # Multi-tenant required
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
            tenant_id=tenant_id,
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
        tenant_id: str | None = None,  # Multi-tenant support (may be None for failed auth)
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
            tenant_id=tenant_id,
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
        tenant_id: str,  # Multi-tenant required
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
            tenant_id=tenant_id,
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
        tenant_id: str,  # Multi-tenant required
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
            tenant_id=tenant_id,
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
        tenant_id: str | None = None,  # Multi-tenant support
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
            tenant_id=tenant_id,
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
        tenant_id: str,  # Multi-tenant required
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
            tenant_id=tenant_id,
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
        tenant_id: str,  # Multi-tenant required
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
            tenant_id=tenant_id,
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
        tenant_id: str,  # Multi-tenant required
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
            tenant_id=tenant_id,
            description=description,
            metadata={
                "report_type": report_type,
                "parameters": parameters,
                "exported": exported,
            },
        )
