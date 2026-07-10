"""
Integration tests for decision endpoints.

Tests cover:
- Creating decisions (approve, reject, return, escalate)
- Dual control workflow
- Evidence snapshot generation
- AI flag acknowledgment
- Entitlement checking
- Decision history
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from fastapi import status

from app.core.security import create_access_token
from app.models.check import CheckItem, CheckStatus, ItemType, RiskLevel
from app.models.decision import Decision, DecisionAction, DecisionType, ReasonCode
from app.models.queue import ApprovalEntitlement, ApprovalEntitlementType
from app.models.user import User


def _approve_entitlement(user_id: str, tenant_id: str) -> ApprovalEntitlement:
    """An unrestricted APPROVE entitlement so dual-control approval is allowed."""
    return ApprovalEntitlement(
        tenant_id=tenant_id,
        user_id=user_id,
        entitlement_type=ApprovalEntitlementType.APPROVE,
        is_active=True,
        effective_from=datetime.now(timezone.utc) - timedelta(days=1),
        max_amount=Decimal("100000000"),
    )


@pytest.fixture
def reviewer_token(test_tenant_id, test_user_id):
    """Create a token with reviewer permissions."""
    return create_access_token(
        subject=test_user_id,
        additional_claims={
            "username": "reviewer",
            "roles": ["reviewer"],
            "permissions": ["check_item:view", "check_item:review"],
            "tenant_id": test_tenant_id,
        },
    )


@pytest.fixture
def approver_token(test_tenant_id):
    """Create a token with approver permissions."""
    return create_access_token(
        subject="approver-id",
        additional_claims={
            "username": "approver",
            "roles": ["supervisor"],
            "permissions": ["check_item:view", "check_item:review", "check_item:approve"],
            "tenant_id": test_tenant_id,
        },
    )


@pytest.fixture
def reviewer_headers(reviewer_token):
    """Auth headers for reviewer."""
    return {"Authorization": f"Bearer {reviewer_token}"}


@pytest.fixture
def approver_headers(approver_token):
    """Auth headers for approver."""
    return {"Authorization": f"Bearer {approver_token}"}


class TestCreateDecision:
    """Tests for creating decisions."""

    @pytest.mark.asyncio
    async def test_approve_decision(self, client, db_session, test_tenant_id, reviewer_headers):
        """Test creating an approve decision."""
        item = CheckItem(
            source_system="test_core",
            account_number_masked="****0000",
            account_type="consumer",
            id="check-approve-1",
            tenant_id=test_tenant_id,
            external_item_id="EXT-APP-1",
            account_id="acct-app-1",
            amount=Decimal("1000.00"),
            status=CheckStatus.NEW,
            risk_level=RiskLevel.LOW,
            item_type=ItemType.ON_US,
            presented_date=datetime.now(timezone.utc),
        )
        db_session.add(item)
        await db_session.commit()

        response = client.post(
            "/api/v1/decisions",
            headers=reviewer_headers,
            json={
                "check_item_id": "check-approve-1",
                "decision_type": "review_recommendation",
                "action": "approve",
                "notes": "Verified all details",
            },
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["action"] == "approve"
        assert data["check_item_id"] == "check-approve-1"

    @pytest.mark.asyncio
    async def test_reject_decision(self, client, db_session, test_tenant_id, reviewer_headers):
        """Test creating a reject decision."""
        item = CheckItem(
            source_system="test_core",
            account_number_masked="****0000",
            account_type="consumer",
            id="check-reject-1",
            tenant_id=test_tenant_id,
            external_item_id="EXT-REJ-1",
            account_id="acct-rej-1",
            amount=Decimal("1000.00"),
            status=CheckStatus.NEW,
            risk_level=RiskLevel.HIGH,
            item_type=ItemType.ON_US,
            presented_date=datetime.now(timezone.utc),
        )
        db_session.add(item)
        await db_session.commit()

        response = client.post(
            "/api/v1/decisions",
            headers=reviewer_headers,
            json={
                "check_item_id": "check-reject-1",
                "decision_type": "review_recommendation",
                "action": "reject",
                "notes": "Suspicious activity detected",
            },
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["action"] == "reject"

    @pytest.mark.asyncio
    async def test_escalate_decision(self, client, db_session, test_tenant_id, reviewer_headers):
        """Test creating an escalate decision."""
        item = CheckItem(
            source_system="test_core",
            account_number_masked="****0000",
            account_type="consumer",
            id="check-escalate-1",
            tenant_id=test_tenant_id,
            external_item_id="EXT-ESC-1",
            account_id="acct-esc-1",
            amount=Decimal("50000.00"),
            status=CheckStatus.NEW,
            risk_level=RiskLevel.CRITICAL,
            item_type=ItemType.ON_US,
            presented_date=datetime.now(timezone.utc),
        )
        db_session.add(item)
        await db_session.commit()

        response = client.post(
            "/api/v1/decisions",
            headers=reviewer_headers,
            json={
                "check_item_id": "check-escalate-1",
                "decision_type": "review_recommendation",
                "action": "escalate",
                "notes": "High value item requires manager review",
            },
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["action"] == "escalate"

    @pytest.mark.asyncio
    async def test_decision_item_not_found(self, client, reviewer_headers):
        """Test decision for non-existent item."""
        response = client.post(
            "/api/v1/decisions",
            headers=reviewer_headers,
            json={
                "check_item_id": "nonexistent-item",
                "decision_type": "review_recommendation",
                "action": "approve",
            },
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestDualControlWorkflow:
    """Tests for dual control workflow."""

    @pytest.mark.asyncio
    async def test_dual_control_triggered(
        self, client, db_session, test_tenant_id, reviewer_headers
    ):
        """Test that dual control is triggered for high-value items."""
        # Create high-value item that requires dual control
        item = CheckItem(
            source_system="test_core",
            account_number_masked="****0000",
            account_type="consumer",
            id="check-dual-1",
            tenant_id=test_tenant_id,
            external_item_id="EXT-DUAL-1",
            account_id="acct-dual-1",
            amount=Decimal("100000.00"),  # High value
            status=CheckStatus.NEW,
            risk_level=RiskLevel.HIGH,
            item_type=ItemType.ON_US,
            presented_date=datetime.now(timezone.utc),
            requires_dual_control=True,
        )
        db_session.add(item)
        await db_session.commit()

        response = client.post(
            "/api/v1/decisions",
            headers=reviewer_headers,
            json={
                "check_item_id": "check-dual-1",
                "decision_type": "review_recommendation",
                "action": "approve",
            },
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["is_dual_control_required"] is True
        assert data["new_status"] == "pending_dual_control"

    @pytest.mark.asyncio
    async def test_dual_control_approval(self, client, db_session, test_tenant_id, test_user_id):
        """Test approving a dual control decision."""
        # Create item in pending dual control state
        item = CheckItem(
            source_system="test_core",
            account_number_masked="****0000",
            account_type="consumer",
            id="check-dc-approve",
            tenant_id=test_tenant_id,
            external_item_id="EXT-DC-A",
            account_id="acct-dc-a",
            amount=Decimal("50000.00"),
            status=CheckStatus.PENDING_DUAL_CONTROL,
            risk_level=RiskLevel.HIGH,
            item_type=ItemType.ON_US,
            presented_date=datetime.now(timezone.utc),
        )
        db_session.add(item)

        # Create pending decision
        decision = Decision(
            id="decision-dc-1",
            tenant_id=test_tenant_id,
            check_item_id="check-dc-approve",
            user_id=test_user_id,
            decision_type=DecisionType.REVIEW_RECOMMENDATION,
            action=DecisionAction.APPROVE,
            is_dual_control_required=True,
        )
        db_session.add(decision)

        item.pending_dual_control_decision_id = decision.id
        db_session.add(_approve_entitlement("different-approver", test_tenant_id))
        await db_session.commit()

        # Approve as different user
        approver_token = create_access_token(
            subject="different-approver",
            additional_claims={
                "username": "approver2",
                "roles": ["supervisor"],
                "permissions": ["check_item:view", "check_item:approve"],
                "tenant_id": test_tenant_id,
            },
        )

        response = client.post(
            "/api/v1/decisions/dual-control",
            headers={"Authorization": f"Bearer {approver_token}"},
            json={
                "decision_id": "decision-dc-1",
                "approve": True,
                "notes": "Verified and approved",
            },
        )

        assert response.status_code == status.HTTP_200_OK

    @pytest.mark.asyncio
    async def test_dual_control_rejection_not_commit_eligible(
        self, client, db_session, test_tenant_id, test_user_id
    ):
        """A rejected dual-control decision must never become commit-eligible.

        Regression: the approval stamp (dual_control_approved_at / approver_id)
        was previously set before the approve/reject branch, so a rejected
        decision still satisfied create_batch's eligibility filter and could be
        released to the bank core.
        """
        from sqlalchemy import select

        item = CheckItem(
            source_system="test_core",
            account_number_masked="****0000",
            account_type="consumer",
            id="check-dc-reject",
            tenant_id=test_tenant_id,
            external_item_id="EXT-DC-R",
            account_id="acct-dc-r",
            amount=Decimal("50000.00"),
            status=CheckStatus.PENDING_DUAL_CONTROL,
            risk_level=RiskLevel.HIGH,
            item_type=ItemType.ON_US,
            presented_date=datetime.now(timezone.utc),
        )
        db_session.add(item)

        decision = Decision(
            id="decision-dc-reject",
            tenant_id=test_tenant_id,
            check_item_id="check-dc-reject",
            user_id=test_user_id,
            decision_type=DecisionType.REVIEW_RECOMMENDATION,
            action=DecisionAction.APPROVE,
            is_dual_control_required=True,
        )
        db_session.add(decision)

        item.pending_dual_control_decision_id = decision.id
        db_session.add(_approve_entitlement("different-approver", test_tenant_id))
        await db_session.commit()

        approver_token = create_access_token(
            subject="different-approver",
            additional_claims={
                "username": "approver2",
                "roles": ["supervisor"],
                "permissions": ["check_item:view", "check_item:approve"],
                "tenant_id": test_tenant_id,
            },
        )

        response = client.post(
            "/api/v1/decisions/dual-control",
            headers={"Authorization": f"Bearer {approver_token}"},
            json={
                "decision_id": "decision-dc-reject",
                "approve": False,
                "notes": "Rejected on second review",
            },
        )
        assert response.status_code == status.HTTP_200_OK

        # The decision must be left unapproved so it cannot enter a commit batch,
        # and the item must return to review.
        await db_session.refresh(decision)
        await db_session.refresh(item)
        assert decision.dual_control_approved_at is None
        assert decision.dual_control_approver_id is None
        assert item.status == CheckStatus.IN_REVIEW

    @pytest.mark.asyncio
    async def test_self_approval_blocked(
        self, client, db_session, test_tenant_id, test_user_id, reviewer_headers
    ):
        """Test that users cannot approve their own decisions."""
        item = CheckItem(
            source_system="test_core",
            account_number_masked="****0000",
            account_type="consumer",
            id="check-self-approve",
            tenant_id=test_tenant_id,
            external_item_id="EXT-SELF",
            account_id="acct-self",
            amount=Decimal("50000.00"),
            status=CheckStatus.PENDING_DUAL_CONTROL,
            risk_level=RiskLevel.HIGH,
            item_type=ItemType.ON_US,
            presented_date=datetime.now(timezone.utc),
        )
        db_session.add(item)

        decision = Decision(
            id="decision-self-1",
            tenant_id=test_tenant_id,
            check_item_id="check-self-approve",
            user_id=test_user_id,  # Same as token user
            decision_type=DecisionType.REVIEW_RECOMMENDATION,
            action=DecisionAction.APPROVE,
            is_dual_control_required=True,
        )
        db_session.add(decision)

        item.pending_dual_control_decision_id = decision.id
        db_session.add(_approve_entitlement(test_user_id, test_tenant_id))
        await db_session.commit()

        # Same user, but with approve permission + entitlement so the request
        # reaches the self-approval guard (rather than being denied earlier).
        approver_token = create_access_token(
            subject=test_user_id,
            additional_claims={
                "username": "selfapprover",
                "roles": ["supervisor"],
                "permissions": ["check_item:view", "check_item:review", "check_item:approve"],
                "tenant_id": test_tenant_id,
            },
        )

        response = client.post(
            "/api/v1/decisions/dual-control",
            headers={"Authorization": f"Bearer {approver_token}"},  # Same user
            json={
                "decision_id": "decision-self-1",
                "approve": True,
            },
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "dual control" in response.json()["message"].lower()


class TestAIFlagAcknowledgment:
    """Tests for AI flag acknowledgment requirement."""

    @pytest.mark.asyncio
    async def test_ai_flags_must_be_acknowledged(
        self, client, db_session, test_tenant_id, reviewer_headers
    ):
        """Test that AI flags must be acknowledged before decision."""
        item = CheckItem(
            source_system="test_core",
            account_number_masked="****0000",
            account_type="consumer",
            id="check-ai-flags",
            tenant_id=test_tenant_id,
            external_item_id="EXT-AI",
            account_id="acct-ai",
            amount=Decimal("1000.00"),
            status=CheckStatus.NEW,
            risk_level=RiskLevel.MEDIUM,
            item_type=ItemType.ON_US,
            presented_date=datetime.now(timezone.utc),
            has_ai_flags=True,
            risk_flags='["suspicious_signature", "amount_anomaly"]',
        )
        db_session.add(item)
        await db_session.commit()

        # Try without acknowledging AI
        response = client.post(
            "/api/v1/decisions",
            headers=reviewer_headers,
            json={
                "check_item_id": "check-ai-flags",
                "decision_type": "review_recommendation",
                "action": "approve",
                "ai_assisted": False,
            },
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "risk signals" in response.json()["message"]

    @pytest.mark.asyncio
    async def test_ai_flags_acknowledged(
        self, client, db_session, test_tenant_id, reviewer_headers
    ):
        """Test decision with AI flags properly acknowledged."""
        item = CheckItem(
            source_system="test_core",
            account_number_masked="****0000",
            account_type="consumer",
            id="check-ai-ack",
            tenant_id=test_tenant_id,
            external_item_id="EXT-AI-ACK",
            account_id="acct-ai-ack",
            amount=Decimal("1000.00"),
            status=CheckStatus.NEW,
            risk_level=RiskLevel.MEDIUM,
            item_type=ItemType.ON_US,
            presented_date=datetime.now(timezone.utc),
            has_ai_flags=True,
            risk_flags='["suspicious_signature"]',
        )
        db_session.add(item)
        await db_session.commit()

        response = client.post(
            "/api/v1/decisions",
            headers=reviewer_headers,
            json={
                "check_item_id": "check-ai-ack",
                "decision_type": "review_recommendation",
                "action": "approve",
                "ai_assisted": True,
                "ai_flags_reviewed": ["suspicious_signature"],
                "notes": "Reviewed AI flags, signature verified authentic",
            },
        )

        assert response.status_code == status.HTTP_200_OK


class TestDecisionHistory:
    """Tests for decision history retrieval."""

    @pytest.mark.asyncio
    async def test_get_decision_history(
        self, client, db_session, test_tenant_id, reviewer_headers, test_user_id
    ):
        """Test getting decision history for an item."""
        item = CheckItem(
            source_system="test_core",
            account_number_masked="****0000",
            account_type="consumer",
            id="check-history",
            tenant_id=test_tenant_id,
            external_item_id="EXT-HIST",
            account_id="acct-hist",
            amount=Decimal("1000.00"),
            status=CheckStatus.APPROVED,
            risk_level=RiskLevel.LOW,
            item_type=ItemType.ON_US,
            presented_date=datetime.now(timezone.utc),
        )
        db_session.add(item)

        # Create test user for decisions
        user = User(
            id=test_user_id,
            tenant_id=test_tenant_id,
            email="histuser@example.com",
            username="histuser",
            full_name="History User",
            hashed_password="hashed",
            is_active=True,
        )
        db_session.add(user)

        # Create multiple decisions
        for i in range(3):
            decision = Decision(
                id=f"decision-hist-{i}",
                tenant_id=test_tenant_id,
                check_item_id="check-history",
                user_id=test_user_id,
                decision_type=DecisionType.REVIEW_RECOMMENDATION,
                action=DecisionAction.HOLD if i < 2 else DecisionAction.APPROVE,
            )
            db_session.add(decision)
        await db_session.commit()

        response = client.get(
            "/api/v1/decisions/check-history/history",
            headers=reviewer_headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 3

    @pytest.mark.asyncio
    async def test_get_decision_history_tolerates_reduced_evidence_snapshot(
        self, client, db_session, test_tenant_id, reviewer_headers, test_user_id
    ):
        """History must not 500 on integrity-only evidence snapshots.

        Decisions recorded through the review flow store a full EvidenceSnapshot,
        but other paths (the demo seed's hash-chain sealing, legacy rows) store a
        reduced, integrity-only dict that lacks the rich context fields. The
        endpoint must surface those as ``evidence_snapshot: null`` instead of
        raising a 500 when rehydrating into the schema.
        """
        item = CheckItem(
            source_system="test_core",
            account_number_masked="****0000",
            account_type="consumer",
            id="check-reduced-evi",
            tenant_id=test_tenant_id,
            external_item_id="EXT-REDUCED",
            account_id="acct-reduced",
            amount=Decimal("1000.00"),
            status=CheckStatus.APPROVED,
            risk_level=RiskLevel.LOW,
            item_type=ItemType.ON_US,
            presented_date=datetime.now(timezone.utc),
        )
        db_session.add(item)
        db_session.add(
            User(
                id=test_user_id,
                tenant_id=test_tenant_id,
                email="reduceduser@example.com",
                username="reduceduser",
                full_name="Reduced User",
                hashed_password="hashed",
                is_active=True,
            )
        )
        # Reduced/sealed snapshot shape as written by the demo seed: carries a
        # valid cryptographic seal but none of the full-schema context fields.
        db_session.add(
            Decision(
                id="decision-reduced",
                tenant_id=test_tenant_id,
                check_item_id="check-reduced-evi",
                user_id=test_user_id,
                decision_type=DecisionType.REVIEW_RECOMMENDATION,
                action=DecisionAction.APPROVE,
                evidence_snapshot={
                    "decision_id": "decision-reduced",
                    "check_item_id": "check-reduced-evi",
                    "action": "approve",
                    "amount": "1000.00",
                    "evidence_hash": "abc123",
                    "previous_evidence_hash": None,
                },
            )
        )
        await db_session.commit()

        response = client.get(
            "/api/v1/decisions/check-reduced-evi/history",
            headers=reviewer_headers,
        )

        assert response.status_code == status.HTTP_200_OK, response.text
        data = response.json()
        assert len(data) == 1
        assert data[0]["evidence_snapshot"] is None


class TestReasonCodes:
    """Tests for reason codes."""

    @pytest.mark.asyncio
    async def test_list_reason_codes(self, client, db_session, reviewer_headers):
        """Test listing available reason codes."""
        # Create test reason codes
        codes = [
            ReasonCode(
                id="code-1",
                code="VERIFIED_SIGNATURE",
                description="Signature verified",
                category="approval",
                decision_type="approve",
                is_active=True,
                display_order=1,
            ),
            ReasonCode(
                id="code-2",
                code="SUSPICIOUS_ACTIVITY",
                description="Suspicious activity detected",
                category="rejection",
                decision_type="reject",
                is_active=True,
                display_order=2,
            ),
        ]
        for code in codes:
            db_session.add(code)
        await db_session.commit()

        response = client.get(
            "/api/v1/decisions/reason-codes",
            headers=reviewer_headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 2


class TestEvidenceChainVerification:
    """Tests for evidence chain verification."""

    @pytest.mark.asyncio
    async def test_verify_evidence_chain(self, client, db_session, test_tenant_id, test_user_id):
        """Test evidence chain verification endpoint."""
        item = CheckItem(
            source_system="test_core",
            account_number_masked="****0000",
            account_type="consumer",
            id="check-evidence",
            tenant_id=test_tenant_id,
            external_item_id="EXT-EVI",
            account_id="acct-evi",
            amount=Decimal("1000.00"),
            status=CheckStatus.APPROVED,
            risk_level=RiskLevel.LOW,
            item_type=ItemType.ON_US,
            presented_date=datetime.now(timezone.utc),
        )
        db_session.add(item)

        # Create decision with evidence
        decision = Decision(
            id="decision-evidence",
            tenant_id=test_tenant_id,
            check_item_id="check-evidence",
            user_id=test_user_id,
            decision_type=DecisionType.REVIEW_RECOMMENDATION,
            action=DecisionAction.APPROVE,
            evidence_snapshot={
                "snapshot_version": "1.0",
                "check_context": {"amount": "1000.00"},
            },
        )
        db_session.add(decision)
        await db_session.commit()

        # Create auditor token
        token = create_access_token(
            subject="auditor-id",
            additional_claims={
                "username": "auditor",
                "roles": ["auditor"],
                "permissions": ["audit:view"],
                "tenant_id": test_tenant_id,
            },
        )

        response = client.get(
            "/api/v1/decisions/check-evidence/verify-evidence-chain",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "chain_valid" in data
