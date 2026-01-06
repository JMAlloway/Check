"""Audit logging service."""

from datetime import datetime, timezone
import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditAction, AuditLog, ItemView


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

        return log_entry

    async def log_item_viewed(
        self,
        check_item_id: str,
        user_id: str,
        username: str | None = None,
        ip_address: str | None = None,
        session_id: str | None = None,
    ) -> ItemView:
        """Start tracking an item view session."""
        view = ItemView(
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
        check_item_id: str,
        limit: int = 100,
    ) -> list[AuditLog]:
        """Get complete audit trail for a check item."""
        result = await self.db.execute(
            select(AuditLog)
            .where(
                AuditLog.resource_type == "check_item",
                AuditLog.resource_id == check_item_id,
            )
            .order_by(AuditLog.timestamp.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_user_activity(
        self,
        user_id: str,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        limit: int = 100,
    ) -> list[AuditLog]:
        """Get audit log entries for a specific user."""
        query = select(AuditLog).where(AuditLog.user_id == user_id)

        if date_from:
            query = query.where(AuditLog.timestamp >= date_from)
        if date_to:
            query = query.where(AuditLog.timestamp <= date_to)

        query = query.order_by(AuditLog.timestamp.desc()).limit(limit)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def search_audit_logs(
        self,
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

        conditions = []
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

        if conditions:
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
