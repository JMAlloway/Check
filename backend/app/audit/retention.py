"""Audit log retention service.

Implements automated log retention policies for compliance:
- Audit logs: 7 years (2555 days) - regulatory/compliance requirement
- Access logs (item_views): 90 days - operational requirement
- User sessions: 90 days - security requirement

This service should be run periodically via cron or scheduled task.
Example cron entry (run daily at 2 AM):
  0 2 * * * python -m app.audit.retention --run

IMPORTANT: Retention policies are configurable via environment variables.
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import NamedTuple

from sqlalchemy import delete, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.models.audit import AuditLog, ItemView
from app.models.user import UserSession

logger = logging.getLogger("audit.retention")


class RetentionPolicy(NamedTuple):
    """Defines retention policy for a log type."""

    name: str
    retention_days: int
    batch_size: int = 1000


# Default retention policies (can be overridden via settings)
RETENTION_POLICIES = {
    "audit_logs": RetentionPolicy(
        name="audit_logs",
        retention_days=getattr(settings, "AUDIT_LOG_RETENTION_DAYS", 2555),  # 7 years
        batch_size=500,  # Smaller batches for audit logs due to size
    ),
    "item_views": RetentionPolicy(
        name="item_views",
        retention_days=getattr(settings, "ACCESS_LOG_RETENTION_DAYS", 90),
        batch_size=1000,
    ),
    "user_sessions": RetentionPolicy(
        name="user_sessions",
        retention_days=getattr(settings, "SESSION_RETENTION_DAYS", 90),
        batch_size=1000,
    ),
}


class RetentionResult(NamedTuple):
    """Result of a retention operation."""

    table: str
    deleted_count: int
    cutoff_date: datetime
    duration_seconds: float
    error: str | None = None


class RetentionService:
    """Service for managing log retention and cleanup.

    Implements compliance-aware deletion with:
    - Batch processing to avoid long-running transactions
    - Verification of integrity before deletion (optional)
    - Detailed logging for audit trail of deletions
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_retention_stats(self) -> dict:
        """Get current retention statistics for all log types.

        Returns counts of records that would be deleted under current policies.
        """
        stats = {}

        for policy_name, policy in RETENTION_POLICIES.items():
            cutoff = datetime.now(timezone.utc) - timedelta(days=policy.retention_days)

            if policy_name == "audit_logs":
                count = await self._count_audit_logs_before(cutoff)
            elif policy_name == "item_views":
                count = await self._count_item_views_before(cutoff)
            elif policy_name == "user_sessions":
                count = await self._count_sessions_before(cutoff)
            else:
                count = 0

            stats[policy_name] = {
                "retention_days": policy.retention_days,
                "cutoff_date": cutoff.isoformat(),
                "records_to_delete": count,
            }

        return stats

    async def _count_audit_logs_before(self, cutoff: datetime) -> int:
        """Count audit logs before cutoff date."""
        result = await self.db.execute(
            select(func.count(AuditLog.id)).where(AuditLog.timestamp < cutoff)
        )
        return result.scalar() or 0

    async def _count_item_views_before(self, cutoff: datetime) -> int:
        """Count item views before cutoff date."""
        result = await self.db.execute(
            select(func.count(ItemView.id)).where(ItemView.view_started_at < cutoff)
        )
        return result.scalar() or 0

    async def _count_sessions_before(self, cutoff: datetime) -> int:
        """Count user sessions before cutoff date."""
        result = await self.db.execute(
            select(func.count(UserSession.id)).where(UserSession.created_at < cutoff)
        )
        return result.scalar() or 0

    async def run_retention(
        self,
        dry_run: bool = False,
        verify_integrity: bool = True,
    ) -> list[RetentionResult]:
        """Run retention cleanup for all log types.

        Args:
            dry_run: If True, only report what would be deleted without deleting.
            verify_integrity: If True, verify audit log integrity before deletion.

        Returns:
            List of RetentionResult for each policy executed.
        """
        results = []

        for policy_name, policy in RETENTION_POLICIES.items():
            logger.info(
                f"Running retention for {policy_name}",
                extra={
                    "event_type": "audit.retention.start",
                    "policy": policy_name,
                    "retention_days": policy.retention_days,
                    "dry_run": dry_run,
                },
            )

            try:
                if policy_name == "audit_logs":
                    result = await self._cleanup_audit_logs(
                        policy, dry_run, verify_integrity
                    )
                elif policy_name == "item_views":
                    result = await self._cleanup_item_views(policy, dry_run)
                elif policy_name == "user_sessions":
                    result = await self._cleanup_user_sessions(policy, dry_run)
                else:
                    continue

                results.append(result)

                logger.info(
                    f"Retention completed for {policy_name}: {result.deleted_count} records",
                    extra={
                        "event_type": "audit.retention.complete",
                        "policy": policy_name,
                        "deleted_count": result.deleted_count,
                        "cutoff_date": result.cutoff_date.isoformat(),
                        "duration_seconds": result.duration_seconds,
                        "dry_run": dry_run,
                    },
                )

            except Exception as e:
                logger.error(
                    f"Retention failed for {policy_name}: {e}",
                    extra={
                        "event_type": "audit.retention.error",
                        "policy": policy_name,
                        "error": str(e),
                    },
                )
                results.append(
                    RetentionResult(
                        table=policy_name,
                        deleted_count=0,
                        cutoff_date=datetime.now(timezone.utc),
                        duration_seconds=0,
                        error=str(e),
                    )
                )

        return results

    async def _cleanup_audit_logs(
        self,
        policy: RetentionPolicy,
        dry_run: bool,
        verify_integrity: bool,
    ) -> RetentionResult:
        """Clean up audit logs older than retention period.

        Special handling:
        - Verifies integrity hash before deletion if enabled
        - Logs any integrity violations for security investigation
        - Excludes demo data (is_demo=True) from deletion
        """
        start_time = datetime.now(timezone.utc)
        cutoff = start_time - timedelta(days=policy.retention_days)
        total_deleted = 0
        integrity_failures = 0

        if dry_run:
            count = await self._count_audit_logs_before(cutoff)
            return RetentionResult(
                table="audit_logs",
                deleted_count=count,
                cutoff_date=cutoff,
                duration_seconds=0,
            )

        # Delete in batches to avoid long transactions
        while True:
            # Get batch of old records
            result = await self.db.execute(
                select(AuditLog)
                .where(AuditLog.timestamp < cutoff)
                .where(AuditLog.is_demo == False)  # Don't delete demo data
                .limit(policy.batch_size)
            )
            batch = list(result.scalars().all())

            if not batch:
                break

            # Verify integrity if enabled
            if verify_integrity:
                for log in batch:
                    if log.integrity_hash and not log.verify_integrity():
                        integrity_failures += 1
                        logger.warning(
                            f"Integrity verification failed for audit log {log.id}",
                            extra={
                                "event_type": "audit.retention.integrity_failure",
                                "audit_log_id": str(log.id),
                                "timestamp": log.timestamp.isoformat(),
                                "action": log.action.value if log.action else None,
                            },
                        )

            # Delete the batch
            ids_to_delete = [log.id for log in batch]
            await self.db.execute(
                delete(AuditLog).where(AuditLog.id.in_(ids_to_delete))
            )
            await self.db.commit()

            total_deleted += len(batch)

        if integrity_failures > 0:
            logger.warning(
                f"Audit log integrity failures detected during retention: {integrity_failures}",
                extra={
                    "event_type": "audit.retention.integrity_summary",
                    "integrity_failures": integrity_failures,
                    "total_deleted": total_deleted,
                },
            )

        duration = (datetime.now(timezone.utc) - start_time).total_seconds()
        return RetentionResult(
            table="audit_logs",
            deleted_count=total_deleted,
            cutoff_date=cutoff,
            duration_seconds=duration,
        )

    async def _cleanup_item_views(
        self,
        policy: RetentionPolicy,
        dry_run: bool,
    ) -> RetentionResult:
        """Clean up item views older than retention period."""
        start_time = datetime.now(timezone.utc)
        cutoff = start_time - timedelta(days=policy.retention_days)
        total_deleted = 0

        if dry_run:
            count = await self._count_item_views_before(cutoff)
            return RetentionResult(
                table="item_views",
                deleted_count=count,
                cutoff_date=cutoff,
                duration_seconds=0,
            )

        # Delete in batches
        while True:
            result = await self.db.execute(
                select(ItemView.id)
                .where(ItemView.view_started_at < cutoff)
                .where(ItemView.is_demo == False)  # Don't delete demo data
                .limit(policy.batch_size)
            )
            ids = [row[0] for row in result.fetchall()]

            if not ids:
                break

            await self.db.execute(delete(ItemView).where(ItemView.id.in_(ids)))
            await self.db.commit()

            total_deleted += len(ids)

        duration = (datetime.now(timezone.utc) - start_time).total_seconds()
        return RetentionResult(
            table="item_views",
            deleted_count=total_deleted,
            cutoff_date=cutoff,
            duration_seconds=duration,
        )

    async def _cleanup_user_sessions(
        self,
        policy: RetentionPolicy,
        dry_run: bool,
    ) -> RetentionResult:
        """Clean up user sessions older than retention period.

        Only deletes sessions that are:
        - Older than the retention period
        - Already inactive (is_active=False)
        """
        start_time = datetime.now(timezone.utc)
        cutoff = start_time - timedelta(days=policy.retention_days)
        total_deleted = 0

        if dry_run:
            count = await self._count_sessions_before(cutoff)
            return RetentionResult(
                table="user_sessions",
                deleted_count=count,
                cutoff_date=cutoff,
                duration_seconds=0,
            )

        # Delete in batches - only inactive sessions
        while True:
            result = await self.db.execute(
                select(UserSession.id)
                .where(UserSession.created_at < cutoff)
                .where(UserSession.is_active == False)
                .limit(policy.batch_size)
            )
            ids = [row[0] for row in result.fetchall()]

            if not ids:
                break

            await self.db.execute(delete(UserSession).where(UserSession.id.in_(ids)))
            await self.db.commit()

            total_deleted += len(ids)

        duration = (datetime.now(timezone.utc) - start_time).total_seconds()
        return RetentionResult(
            table="user_sessions",
            deleted_count=total_deleted,
            cutoff_date=cutoff,
            duration_seconds=duration,
        )

    async def verify_all_audit_integrity(
        self,
        batch_size: int = 1000,
        max_records: int | None = None,
    ) -> dict:
        """Verify integrity of all audit log records.

        This is a comprehensive check that can be run periodically
        to detect any tampering with the audit trail.

        Returns:
            Dict with verification statistics.
        """
        stats = {
            "total_checked": 0,
            "valid": 0,
            "invalid": 0,
            "no_hash": 0,
            "invalid_ids": [],
        }

        offset = 0
        while True:
            if max_records and stats["total_checked"] >= max_records:
                break

            result = await self.db.execute(
                select(AuditLog)
                .order_by(AuditLog.timestamp.desc())
                .offset(offset)
                .limit(batch_size)
            )
            batch = list(result.scalars().all())

            if not batch:
                break

            for log in batch:
                stats["total_checked"] += 1

                if not log.integrity_hash:
                    stats["no_hash"] += 1
                elif log.verify_integrity():
                    stats["valid"] += 1
                else:
                    stats["invalid"] += 1
                    stats["invalid_ids"].append(str(log.id))

                    logger.warning(
                        f"Audit log integrity verification failed: {log.id}",
                        extra={
                            "event_type": "audit.integrity.verification_failed",
                            "audit_log_id": str(log.id),
                            "timestamp": log.timestamp.isoformat(),
                            "user_id": log.user_id,
                            "action": log.action.value if log.action else None,
                        },
                    )

            offset += batch_size

        logger.info(
            f"Audit integrity verification complete: {stats['valid']}/{stats['total_checked']} valid",
            extra={
                "event_type": "audit.integrity.verification_complete",
                "total_checked": stats["total_checked"],
                "valid": stats["valid"],
                "invalid": stats["invalid"],
                "no_hash": stats["no_hash"],
            },
        )

        return stats


async def run_retention_job(dry_run: bool = False) -> list[RetentionResult]:
    """Run the retention job as a standalone task.

    This can be called from cron or a scheduled task runner.
    """
    async with AsyncSessionLocal() as db:
        service = RetentionService(db)
        return await service.run_retention(dry_run=dry_run)


async def get_retention_stats() -> dict:
    """Get retention statistics without performing any deletions."""
    async with AsyncSessionLocal() as db:
        service = RetentionService(db)
        return await service.get_retention_stats()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run audit log retention")
    parser.add_argument("--run", action="store_true", help="Run retention cleanup")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be deleted")
    parser.add_argument("--stats", action="store_true", help="Show retention statistics")
    parser.add_argument("--verify", action="store_true", help="Verify audit log integrity")

    args = parser.parse_args()

    if args.stats:
        stats = asyncio.run(get_retention_stats())
        print("Retention Statistics:")
        for name, data in stats.items():
            print(f"  {name}:")
            print(f"    Retention: {data['retention_days']} days")
            print(f"    Cutoff: {data['cutoff_date']}")
            print(f"    Records to delete: {data['records_to_delete']}")
    elif args.run or args.dry_run:
        results = asyncio.run(run_retention_job(dry_run=args.dry_run))
        print("Retention Results:")
        for result in results:
            status = "would delete" if args.dry_run else "deleted"
            print(f"  {result.table}: {status} {result.deleted_count} records")
            if result.error:
                print(f"    Error: {result.error}")
    elif args.verify:
        async def verify():
            async with AsyncSessionLocal() as db:
                service = RetentionService(db)
                return await service.verify_all_audit_integrity()

        stats = asyncio.run(verify())
        print("Integrity Verification Results:")
        print(f"  Total checked: {stats['total_checked']}")
        print(f"  Valid: {stats['valid']}")
        print(f"  Invalid: {stats['invalid']}")
        print(f"  No hash: {stats['no_hash']}")
    else:
        parser.print_help()
