"""Cross-tenant attack tests.

Adversarial tests that verify a user authenticated for tenant A cannot reach
tenant B's data through the HTTP API. These re-author the security intent of the
old (stale) TestCrossTenantAttacks against the current endpoints, driving every
case through the real request path rather than calling endpoint internals.

Covered attack vectors:
- ID enumeration: directly requesting another tenant's resources by id.
- Parameter tampering: supplying another tenant's ids in mutating requests.
- Batch/listing leakage: list endpoints must never return another tenant's rows.
"""

from datetime import datetime, timezone
from decimal import Decimal

import pytest
from fastapi import status

from app.core.security import create_access_token
from app.models.audit import AuditAction, AuditLog
from app.models.check import CheckItem, CheckStatus, ItemType, RiskLevel
from app.models.queue import Queue, QueueType

TENANT_A = "tenant-attacker"
TENANT_B = "tenant-victim"
VICTIM_ITEM_ID = "victim-check-0001"

# Any request that is blocked (rather than leaking data) is acceptable; 404 is
# preferred (does not reveal existence) but 403 also denies the attack.
BLOCKED = {status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND}


def _headers(tenant_id: str, *, permissions: list[str]) -> dict:
    token = create_access_token(
        subject=f"user-{tenant_id}",
        additional_claims={
            "username": f"user-{tenant_id}",
            "roles": ["supervisor"],
            "permissions": permissions,
            "tenant_id": tenant_id,
        },
    )
    return {"Authorization": f"Bearer {token}"}


def _check_item(item_id: str, tenant_id: str, **overrides) -> CheckItem:
    fields = dict(
        id=item_id,
        tenant_id=tenant_id,
        source_system="test_core",
        external_item_id=f"EXT-{item_id}",
        account_id=f"acct-{item_id}",
        account_number_masked="****0000",
        account_type="consumer",
        amount=Decimal("1000"),
        status=CheckStatus.NEW,
        risk_level=RiskLevel.LOW,
        item_type=ItemType.ON_US,
        presented_date=datetime.now(timezone.utc),
    )
    fields.update(overrides)
    return CheckItem(**fields)


async def _seed_victim_item(db_session) -> str:
    """Seed a tenant B (victim) check item and return its id."""
    db_session.add(_check_item(VICTIM_ITEM_ID, TENANT_B))
    await db_session.commit()
    return VICTIM_ITEM_ID


class TestIdEnumerationAttack:
    """Attacker knows a victim resource id and requests it directly."""

    @pytest.mark.asyncio
    async def test_cannot_read_other_tenant_check_item(self, client, db_session):
        await _seed_victim_item(db_session)
        response = client.get(
            f"/api/v1/checks/{VICTIM_ITEM_ID}",
            headers=_headers(TENANT_A, permissions=["check_item:view"]),
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_cannot_read_other_tenant_check_history(self, client, db_session):
        await _seed_victim_item(db_session)
        response = client.get(
            f"/api/v1/checks/{VICTIM_ITEM_ID}/history",
            headers=_headers(TENANT_A, permissions=["check_item:view"]),
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_cannot_read_other_tenant_audit_trail(self, client, db_session):
        # Seed the victim item and its audit log in a single commit (the setup
        # session's FK-bypass does not persist across commit boundaries).
        db_session.add(_check_item(VICTIM_ITEM_ID, TENANT_B))
        db_session.add(
            AuditLog(
                id="victim-audit-1",
                tenant_id=TENANT_B,
                timestamp=datetime.now(timezone.utc),
                action=AuditAction.ITEM_VIEWED,
                resource_type="check_item",
                resource_id=VICTIM_ITEM_ID,
                user_id="user-victim",
                username="victim",
            )
        )
        await db_session.commit()

        response = client.get(
            f"/api/v1/audit/items/{VICTIM_ITEM_ID}",
            headers=_headers(TENANT_A, permissions=["audit:view"]),
        )
        # Never the victim's log: blocked, or an empty trail.
        assert response.status_code in BLOCKED | {status.HTTP_200_OK}
        if response.status_code == status.HTTP_200_OK:
            assert response.json() == []

    @pytest.mark.asyncio
    async def test_cannot_read_other_tenant_queue(self, client, db_session):
        db_session.add(
            Queue(
                id="victim-queue-1",
                tenant_id=TENANT_B,
                name="Victim Queue",
                queue_type=QueueType.STANDARD,
            )
        )
        await db_session.commit()

        response = client.get(
            "/api/v1/queues/victim-queue-1",
            headers=_headers(TENANT_A, permissions=["queue:view"]),
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestParameterTamperingAttack:
    """Attacker supplies a victim resource id in a mutating request."""

    @pytest.mark.asyncio
    async def test_cannot_create_decision_on_other_tenant_item(self, client, db_session):
        await _seed_victim_item(db_session)
        response = client.post(
            "/api/v1/decisions",
            headers=_headers(TENANT_A, permissions=["check_item:view", "check_item:review"]),
            json={
                "check_item_id": VICTIM_ITEM_ID,
                "decision_type": "review_recommendation",
                "action": "approve",
            },
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_cannot_assign_reviewer_on_other_tenant_item(self, client, db_session):
        await _seed_victim_item(db_session)
        response = client.post(
            f"/api/v1/checks/{VICTIM_ITEM_ID}/assign?reviewer_id=user-{TENANT_A}",
            headers=_headers(TENANT_A, permissions=["check_item:view", "check_item:assign"]),
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_cannot_update_status_on_other_tenant_item(self, client, db_session):
        await _seed_victim_item(db_session)
        response = client.post(
            f"/api/v1/checks/{VICTIM_ITEM_ID}/status",
            headers=_headers(TENANT_A, permissions=["check_item:view", "check_item:review"]),
            json={"status": "in_review"},
        )
        assert response.status_code in BLOCKED

    @pytest.mark.asyncio
    async def test_victim_item_unchanged_after_tampering(self, client, db_session):
        """After a failed cross-tenant status change, the victim row is intact."""
        await _seed_victim_item(db_session)
        client.post(
            f"/api/v1/checks/{VICTIM_ITEM_ID}/status",
            headers=_headers(TENANT_A, permissions=["check_item:view", "check_item:review"]),
            json={"status": "approved"},
        )
        # The victim can still see its item in its original NEW status.
        response = client.get(
            f"/api/v1/checks/{VICTIM_ITEM_ID}",
            headers=_headers(TENANT_B, permissions=["check_item:view"]),
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["status"] == "new"


class TestBatchListingLeakage:
    """List endpoints must only ever return the caller's tenant rows."""

    @pytest.mark.asyncio
    async def test_check_listing_excludes_other_tenant(self, client, db_session):
        for i in range(3):
            db_session.add(_check_item(f"a-list-{i}", TENANT_A))
        for i in range(4):
            db_session.add(_check_item(f"b-list-{i}", TENANT_B))
        await db_session.commit()

        response = client.get(
            "/api/v1/checks?page_size=100",
            headers=_headers(TENANT_A, permissions=["check_item:view"]),
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total"] == 3
        returned_ids = {item["id"] for item in data["items"]}
        assert returned_ids == {"a-list-0", "a-list-1", "a-list-2"}

    @pytest.mark.asyncio
    async def test_audit_log_listing_excludes_other_tenant(self, client, db_session):
        for tenant, prefix in ((TENANT_A, "a"), (TENANT_B, "b")):
            for i in range(3):
                db_session.add(
                    AuditLog(
                        id=f"{prefix}-audit-{i}",
                        tenant_id=tenant,
                        timestamp=datetime.now(timezone.utc),
                        action=AuditAction.ITEM_VIEWED,
                        resource_type="check_item",
                        resource_id=f"{prefix}-item-{i}",
                        user_id=f"user-{prefix}",
                        username=prefix,
                    )
                )
        await db_session.commit()

        response = client.get(
            "/api/v1/audit/logs?page_size=100",
            headers=_headers(TENANT_A, permissions=["audit:view"]),
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        # Only tenant A's three logs are returned (AuditLogResponse does not
        # expose tenant_id, so isolation is asserted via the resource ids).
        assert data["total"] == 3
        assert all(item["resource_id"].startswith("a-item-") for item in data["items"])

    @pytest.mark.asyncio
    async def test_queue_listing_excludes_other_tenant(self, client, db_session):
        db_session.add(
            Queue(id="a-queue", tenant_id=TENANT_A, name="Queue A", queue_type=QueueType.STANDARD)
        )
        db_session.add(
            Queue(id="b-queue", tenant_id=TENANT_B, name="Queue B", queue_type=QueueType.STANDARD)
        )
        await db_session.commit()

        response = client.get(
            "/api/v1/queues",
            headers=_headers(TENANT_A, permissions=["queue:view"]),
        )
        assert response.status_code == status.HTTP_200_OK
        queue_ids = {q["id"] for q in response.json()}
        assert "a-queue" in queue_ids
        assert "b-queue" not in queue_ids
