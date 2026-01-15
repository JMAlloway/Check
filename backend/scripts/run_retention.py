#!/usr/bin/env python3
"""
Data Retention Cron Job Script

This script runs the automated log retention cleanup according to
configured retention policies.

Retention Policies:
- Audit logs: 7 years (2555 days) - regulatory/compliance requirement
- Access logs (item_views): 90 days - operational requirement
- User sessions: 90 days - security requirement

Usage:
    # Dry run (see what would be deleted):
    python scripts/run_retention.py --dry-run

    # Actual cleanup:
    python scripts/run_retention.py --run

    # Show statistics only:
    python scripts/run_retention.py --stats

    # Verify audit log integrity:
    python scripts/run_retention.py --verify

Cron Entry (recommended - run daily at 2:00 AM):
    0 2 * * * cd /app && python scripts/run_retention.py --run >> /var/log/retention.log 2>&1

Environment Variables:
    DATABASE_URL: PostgreSQL connection string (required)
    AUDIT_LOG_RETENTION_DAYS: Override default audit retention (default: 2555)
    ACCESS_LOG_RETENTION_DAYS: Override default access log retention (default: 90)
    SESSION_RETENTION_DAYS: Override default session retention (default: 90)
"""

import argparse
import asyncio
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add the backend directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.audit.retention import (
    RetentionService,
    run_retention_job,
    get_retention_stats,
    RETENTION_POLICIES,
)
from app.db.session import AsyncSessionLocal

# Configure logging for cron output
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("retention.cron")


async def show_stats() -> int:
    """Show retention statistics without making changes."""
    logger.info("Fetching retention statistics...")
    stats = await get_retention_stats()

    print("\n" + "=" * 60)
    print("DATA RETENTION STATISTICS")
    print("=" * 60)
    print(f"Report generated: {datetime.now(timezone.utc).isoformat()}")
    print()

    for name, data in stats.items():
        print(f"{name}:")
        print(f"  Retention period: {data['retention_days']} days")
        print(f"  Cutoff date: {data['cutoff_date']}")
        print(f"  Records to delete: {data['records_to_delete']:,}")
        print()

    print("=" * 60)
    return 0


async def run_cleanup(dry_run: bool, verify_integrity: bool) -> int:
    """Run retention cleanup."""
    mode = "DRY RUN" if dry_run else "CLEANUP"
    logger.info(f"Starting retention {mode}...")

    results = await run_retention_job(dry_run=dry_run)

    print("\n" + "=" * 60)
    print(f"DATA RETENTION {mode} RESULTS")
    print("=" * 60)
    print(f"Completed: {datetime.now(timezone.utc).isoformat()}")
    print()

    total_deleted = 0
    has_errors = False

    for result in results:
        status_word = "would delete" if dry_run else "deleted"
        print(f"{result.table}:")
        print(f"  {status_word.capitalize()}: {result.deleted_count:,} records")
        print(f"  Cutoff date: {result.cutoff_date.isoformat()}")
        print(f"  Duration: {result.duration_seconds:.2f} seconds")
        if result.error:
            print(f"  ERROR: {result.error}")
            has_errors = True
        print()
        total_deleted += result.deleted_count

    print("-" * 60)
    print(f"Total records {status_word}: {total_deleted:,}")
    print("=" * 60)

    if has_errors:
        logger.error("Retention completed with errors")
        return 1

    logger.info(f"Retention {mode} completed successfully")
    return 0


async def verify_integrity(max_records: int) -> int:
    """Verify audit log integrity."""
    logger.info(f"Verifying audit log integrity (max {max_records:,} records)...")

    async with AsyncSessionLocal() as db:
        service = RetentionService(db)
        stats = await service.verify_all_audit_integrity(max_records=max_records)

    print("\n" + "=" * 60)
    print("AUDIT LOG INTEGRITY VERIFICATION")
    print("=" * 60)
    print(f"Completed: {datetime.now(timezone.utc).isoformat()}")
    print()
    print(f"Total records checked: {stats['total_checked']:,}")
    print(f"Valid (hash matches): {stats['valid']:,}")
    print(f"Invalid (hash mismatch): {stats['invalid']:,}")
    print(f"No hash (legacy records): {stats['no_hash']:,}")

    if stats["invalid"] > 0:
        print()
        print("WARNING: Integrity failures detected!")
        print("Invalid record IDs (first 20):")
        for record_id in stats["invalid_ids"][:20]:
            print(f"  - {record_id}")
        if len(stats["invalid_ids"]) > 20:
            print(f"  ... and {len(stats['invalid_ids']) - 20} more")

    print("=" * 60)

    if stats["invalid"] > 0:
        logger.error(f"Integrity verification found {stats['invalid']} invalid records")
        return 1

    logger.info("Integrity verification passed")
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Run data retention cleanup according to configured policies.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--run",
        action="store_true",
        help="Run actual cleanup (deletes data)",
    )
    group.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be deleted without making changes",
    )
    group.add_argument(
        "--stats",
        action="store_true",
        help="Show retention statistics only",
    )
    group.add_argument(
        "--verify",
        action="store_true",
        help="Verify audit log integrity",
    )

    parser.add_argument(
        "--no-verify-integrity",
        action="store_true",
        help="Skip integrity verification during cleanup",
    )
    parser.add_argument(
        "--max-verify-records",
        type=int,
        default=100000,
        help="Maximum records to verify (default: 100000)",
    )

    args = parser.parse_args()

    # Print current retention policies
    print("\nConfigured Retention Policies:")
    for name, policy in RETENTION_POLICIES.items():
        print(f"  {name}: {policy.retention_days} days")
    print()

    # Run the appropriate action
    if args.stats:
        exit_code = asyncio.run(show_stats())
    elif args.verify:
        exit_code = asyncio.run(verify_integrity(args.max_verify_records))
    else:
        exit_code = asyncio.run(
            run_cleanup(
                dry_run=args.dry_run,
                verify_integrity=not args.no_verify_integrity,
            )
        )

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
