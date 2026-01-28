"""Scheduled Tasks for Item Context Import.

Provides scheduled execution of SFTP imports based on connector
cron configurations.

Usage in main application startup:
    from app.scheduler.item_context_scheduler import start_scheduler, shutdown_scheduler

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        await start_scheduler()
        yield
        await shutdown_scheduler()

Or run standalone:
    python -m app.scheduler.item_context_scheduler
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.models.item_context_connector import (
    ContextConnectorStatus,
    ItemContextConnector,
)
from app.services.item_context_service import ItemContextImportService
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select

logger = logging.getLogger(__name__)

# Global scheduler instance
_scheduler: AsyncIOScheduler | None = None


async def run_scheduled_import(connector_id: str) -> None:
    """
    Execute a scheduled import for a connector.

    This is called by APScheduler at the configured cron time.
    """
    logger.info(f"Starting scheduled import for connector {connector_id}")

    async with AsyncSessionLocal() as db:
        # Get connector
        result = await db.execute(
            select(ItemContextConnector).where(ItemContextConnector.id == connector_id)
        )
        connector = result.scalar_one_or_none()

        if not connector:
            logger.error(f"Connector {connector_id} not found")
            return

        if not connector.is_enabled or not connector.schedule_enabled:
            logger.warning(f"Connector {connector_id} is disabled, skipping import")
            return

        # Run import
        try:
            service = ItemContextImportService(db)
            imports = await service.run_import(
                connector=connector,
                triggered_by="scheduled",
            )

            # Log results
            for imp in imports:
                logger.info(
                    f"Import completed for {connector.name}: "
                    f"file={imp.file_name}, status={imp.status}, "
                    f"applied={imp.applied_records}/{imp.total_records}"
                )

        except Exception as e:
            logger.exception(f"Scheduled import failed for connector {connector_id}: {e}")


def create_cron_trigger(cron_expression: str, timezone_str: str) -> CronTrigger:
    """
    Create an APScheduler CronTrigger from a cron expression.

    Supports standard 5-field cron: minute hour day month weekday
    Example: "0 6 * * *" = 6:00 AM daily
    """
    parts = cron_expression.split()

    if len(parts) != 5:
        raise ValueError(
            f"Invalid cron expression: {cron_expression}. "
            "Expected 5 fields: minute hour day month weekday"
        )

    return CronTrigger(
        minute=parts[0],
        hour=parts[1],
        day=parts[2],
        month=parts[3],
        day_of_week=parts[4],
        timezone=timezone_str,
    )


async def sync_connector_schedules() -> None:
    """
    Sync scheduler jobs with database connector configurations.

    - Adds jobs for newly enabled connectors
    - Removes jobs for disabled connectors
    - Updates jobs when cron expressions change
    """
    global _scheduler

    if not _scheduler:
        logger.warning("Scheduler not initialized")
        return

    async with AsyncSessionLocal() as db:
        # Get all enabled connectors with schedules
        result = await db.execute(
            select(ItemContextConnector).where(
                ItemContextConnector.is_enabled == True,
                ItemContextConnector.schedule_enabled == True,
                ItemContextConnector.schedule_cron.isnot(None),
            )
        )
        connectors = result.scalars().all()

        # Track which connector IDs should have jobs
        active_connector_ids = set()

        for connector in connectors:
            job_id = f"item_context_import_{connector.id}"
            active_connector_ids.add(connector.id)

            # Check if job exists
            existing_job = _scheduler.get_job(job_id)

            try:
                trigger = create_cron_trigger(connector.schedule_cron, connector.schedule_timezone)

                if existing_job:
                    # Update existing job
                    _scheduler.reschedule_job(job_id, trigger=trigger)
                    logger.info(f"Updated schedule for connector {connector.name}")
                else:
                    # Add new job
                    _scheduler.add_job(
                        run_scheduled_import,
                        trigger=trigger,
                        args=[connector.id],
                        id=job_id,
                        name=f"Import: {connector.name}",
                        replace_existing=True,
                    )
                    logger.info(
                        f"Added schedule for connector {connector.name}: {connector.schedule_cron}"
                    )

            except Exception as e:
                logger.error(f"Failed to schedule connector {connector.name}: {e}")

        # Remove jobs for connectors that are no longer active
        for job in _scheduler.get_jobs():
            if job.id.startswith("item_context_import_"):
                connector_id = job.id.replace("item_context_import_", "")
                if connector_id not in active_connector_ids:
                    _scheduler.remove_job(job.id)
                    logger.info(f"Removed schedule for connector {connector_id}")


async def start_scheduler() -> None:
    """
    Start the item context import scheduler.

    Call this during application startup.
    """
    global _scheduler

    if _scheduler is not None:
        logger.warning("Scheduler already running")
        return

    _scheduler = AsyncIOScheduler()

    # Add a job to sync schedules every 5 minutes
    # This picks up configuration changes without restart
    _scheduler.add_job(
        sync_connector_schedules,
        "interval",
        minutes=5,
        id="sync_connector_schedules",
        name="Sync Connector Schedules",
    )

    _scheduler.start()
    logger.info("Item context scheduler started")

    # Initial sync
    await sync_connector_schedules()


async def shutdown_scheduler() -> None:
    """
    Shutdown the scheduler gracefully.

    Call this during application shutdown.
    """
    global _scheduler

    if _scheduler:
        _scheduler.shutdown(wait=True)
        _scheduler = None
        logger.info("Item context scheduler stopped")


def get_scheduler_status() -> dict[str, Any]:
    """
    Get current scheduler status for monitoring.

    Returns:
        Dictionary with scheduler state and job information
    """
    global _scheduler

    if not _scheduler:
        return {
            "running": False,
            "jobs": [],
        }

    jobs = []
    for job in _scheduler.get_jobs():
        next_run = job.next_run_time
        jobs.append(
            {
                "id": job.id,
                "name": job.name,
                "next_run": next_run.isoformat() if next_run else None,
                "trigger": str(job.trigger),
            }
        )

    return {
        "running": _scheduler.running,
        "jobs": jobs,
    }


# Standalone execution for testing
if __name__ == "__main__":
    import sys

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    async def main():
        print("Starting Item Context Scheduler...")
        await start_scheduler()

        print("\nScheduler Status:")
        status = get_scheduler_status()
        print(f"  Running: {status['running']}")
        print(f"  Jobs: {len(status['jobs'])}")
        for job in status["jobs"]:
            print(f"    - {job['name']}: next run at {job['next_run']}")

        print("\nPress Ctrl+C to stop...")
        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            pass

        await shutdown_scheduler()
        print("Scheduler stopped.")

    asyncio.run(main())
