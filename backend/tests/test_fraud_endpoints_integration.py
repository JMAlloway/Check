"""Integration tests for fraud write endpoints.

Regression coverage for bugs found via end-to-end demo:
- write endpoints never called db.commit(), so create/submit/dismiss/config
  silently rolled back (the API returned success but nothing persisted);
- create/submit built the response off the lazy `shared_artifact` relationship,
  triggering an async lazy-load (greenlet error -> 500).
"""

from datetime import datetime, timezone
from decimal import Decimal

import pytest
from fastapi import status
from sqlalchemy import select

from app.core.security import create_access_token
from app.models.check import CheckItem, CheckStatus, ItemType, RiskLevel
from app.models.fraud import FraudEvent, FraudEventStatus, FraudSharedArtifact


@pytest.fixture
def fraud_headers(test_tenant_id):
    """Token with fraud reporting + submission permissions."""
    token = create_access_token(
        subject="fraud-reporter-id",
        additional_claims={
            "username": "fraud_reporter",
            "roles": ["senior_reviewer"],
            "permissions": ["fraud:view", "fraud:create", "fraud:submit"],
            "tenant_id": test_tenant_id,
        },
    )
    return {"Authorization": f"Bearer {token}"}


async def _make_check_item(db_session, tenant_id: str, item_id: str) -> None:
    db_session.add(
        CheckItem(
            id=item_id,
            source_system="test_core",
            account_number_masked="****1234",
            account_type="business",
            tenant_id=tenant_id,
            external_item_id=f"EXT-{item_id}",
            account_id="acct-1",
            amount=Decimal("5000.00"),
            status=CheckStatus.NEW,
            risk_level=RiskLevel.HIGH,
            item_type=ItemType.TRANSIT,
            routing_number="000000001",
            payee_name="Test Payee",
            check_number="1001",
            presented_date=datetime.now(timezone.utc),
        )
    )
    await db_session.commit()


@pytest.mark.asyncio
async def test_create_fraud_event_persists(client, db_session, test_tenant_id, fraud_headers):
    """POST /fraud-events returns 201 and the row is actually committed."""
    await _make_check_item(db_session, test_tenant_id, "chk-fraud-1")

    response = client.post(
        "/api/v1/fraud/fraud-events",
        headers=fraud_headers,
        json={
            "check_item_id": "chk-fraud-1",
            "fraud_type": "counterfeit_check",
            "channel": "branch",
            "amount": "1234.56",
            "event_date": "2026-06-01T00:00:00Z",
            "confidence": 4,
            "sharing_level": 1,
        },
    )

    assert response.status_code == status.HTTP_201_CREATED
    body = response.json()
    assert body["has_shared_artifact"] is False  # not submitted yet

    # Persisted (regression: endpoint used to never commit).
    persisted = (
        await db_session.execute(select(FraudEvent).where(FraudEvent.id == body["id"]))
    ).scalar_one_or_none()
    assert persisted is not None
    assert persisted.status == FraudEventStatus.DRAFT


@pytest.mark.asyncio
async def test_submit_fraud_event_creates_artifact(
    client, db_session, test_tenant_id, fraud_headers
):
    """Submitting at network level creates a persisted shared artifact (no 500)."""
    await _make_check_item(db_session, test_tenant_id, "chk-fraud-2")

    created = client.post(
        "/api/v1/fraud/fraud-events",
        headers=fraud_headers,
        json={
            "check_item_id": "chk-fraud-2",
            "fraud_type": "altered_check",
            "channel": "rdc",
            "amount": "9000.00",
            "event_date": "2026-06-02T00:00:00Z",
            "confidence": 5,
            "sharing_level": 1,
        },
    )
    assert created.status_code == status.HTTP_201_CREATED
    event_id = created.json()["id"]

    submitted = client.post(
        f"/api/v1/fraud/fraud-events/{event_id}/submit",
        headers=fraud_headers,
        json={"sharing_level": 2, "confirm_no_pii": True},
    )

    assert submitted.status_code == status.HTTP_200_OK
    body = submitted.json()
    assert body["status"] == "submitted"
    assert body["has_shared_artifact"] is True  # response reflects the new artifact

    artifact = (
        await db_session.execute(
            select(FraudSharedArtifact).where(FraudSharedArtifact.fraud_event_id == event_id)
        )
    ).scalar_one_or_none()
    assert artifact is not None
    assert artifact.is_active is True
