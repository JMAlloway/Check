"""Tests for audit-log immutability triggers and the retention purge bypass.

The audit tables are append-only: UPDATE is always rejected, and DELETE is
rejected unless the caller opts in via the app.allow_audit_purge session flag,
which the retention service sets for its purge transaction. These tests run
against the real triggers installed by the test schema fixture.
"""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import delete, text, update
from sqlalchemy.exc import DBAPIError

from app.audit.retention import RetentionPolicy, RetentionService
from app.audit.service import GENESIS_HASH
from app.models.audit import AuditAction, AuditLog


def _make_audit_log(tenant_id: str, *, timestamp: datetime, is_demo: bool = False) -> AuditLog:
    log = AuditLog(
        id=str(uuid4()),
        tenant_id=tenant_id,
        timestamp=timestamp,
        action=AuditAction.LOGIN,
        resource_type="user",
        description="retention/immutability test row",
        is_demo=is_demo,
    )
    log.previous_hash = GENESIS_HASH
    log.integrity_hash = log.compute_integrity_hash()
    return log


@pytest.mark.asyncio
async def test_update_is_blocked(db_session, test_tenant_id):
    """The immutability trigger rejects any UPDATE on audit_logs."""
    log = _make_audit_log(test_tenant_id, timestamp=datetime.now(timezone.utc))
    db_session.add(log)
    await db_session.commit()

    with pytest.raises(DBAPIError):
        await db_session.execute(
            update(AuditLog).where(AuditLog.id == log.id).values(description="tampered")
        )
        await db_session.commit()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_delete_without_flag_is_blocked(db_session, test_tenant_id):
    """A plain DELETE (no purge flag) is rejected by the trigger."""
    log = _make_audit_log(test_tenant_id, timestamp=datetime.now(timezone.utc))
    db_session.add(log)
    await db_session.commit()

    with pytest.raises(DBAPIError):
        await db_session.execute(delete(AuditLog).where(AuditLog.id == log.id))
        await db_session.commit()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_delete_allowed_with_purge_flag(db_session, test_tenant_id):
    """Setting app.allow_audit_purge for the transaction permits the DELETE."""
    log = _make_audit_log(test_tenant_id, timestamp=datetime.now(timezone.utc))
    db_session.add(log)
    await db_session.commit()

    await db_session.execute(text("SET LOCAL app.allow_audit_purge = 'on'"))
    await db_session.execute(delete(AuditLog).where(AuditLog.id == log.id))
    await db_session.commit()

    remaining = await db_session.get(AuditLog, log.id)
    assert remaining is None


@pytest.mark.asyncio
async def test_retention_service_purges_expired_logs(db_session, test_tenant_id):
    """RetentionService purges expired non-demo rows through the trigger."""
    now = datetime.now(timezone.utc)
    expired = _make_audit_log(test_tenant_id, timestamp=now - timedelta(days=10))
    recent = _make_audit_log(test_tenant_id, timestamp=now)
    demo_expired = _make_audit_log(test_tenant_id, timestamp=now - timedelta(days=10), is_demo=True)
    db_session.add_all([expired, recent, demo_expired])
    await db_session.commit()

    service = RetentionService(db_session)
    result = await service._cleanup_audit_logs(
        RetentionPolicy(name="audit_logs", retention_days=1, batch_size=100),
        dry_run=False,
        verify_integrity=False,
    )

    assert result.deleted_count == 1  # only the expired non-demo row
    assert await db_session.get(AuditLog, expired.id) is None
    assert await db_session.get(AuditLog, recent.id) is not None  # within retention
    assert await db_session.get(AuditLog, demo_expired.id) is not None  # demo preserved
