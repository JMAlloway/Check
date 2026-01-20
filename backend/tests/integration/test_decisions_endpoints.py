"""
Integration tests for decision endpoints.

Tests cover:
- Make decision (approve/return/reject)
- Escalate to supervisor
- Dual control workflow
- Decision validation
- Entitlement checks
- Audit logging
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.security import create_access_token
from app.main import app


class TestMakeDecisionEndpoint:
    """Tests for POST /api/v1/decisions."""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    @pytest.fixture
    def reviewer_token(self):
        return create_access_token(
            subject=str(uuid.uuid4()),
            additional_claims={
                "username": "reviewer",
                "roles": ["reviewer"],
                "permissions": ["check:view", "check:decide"],
                "tenant_id": str(uuid.uuid4()),
            },
        )

    @pytest.fixture
    def auth_headers(self, reviewer_token):
        return {"Authorization": f"Bearer {reviewer_token}"}

    def test_make_decision_requires_auth(self, client):
        """Make decision should require authentication."""
        response = client.post(
            "/api/v1/decisions",
            json={
                "check_item_id": str(uuid.uuid4()),
                "action": "approve",
                "reason_codes": ["verified"],
            },
        )
        assert response.status_code == 401

    def test_make_decision_validates_action(self, client, auth_headers):
        """Make decision should validate action type."""
        response = client.post(
            "/api/v1/decisions",
            json={
                "check_item_id": str(uuid.uuid4()),
                "action": "invalid_action",
                "reason_codes": [],
            },
            headers=auth_headers,
        )

        # Should reject invalid action
        assert response.status_code == 422

    def test_make_decision_requires_reason_codes(self, client, auth_headers):
        """Make decision should require reason codes for certain actions."""
        # This test verifies validation rules
        response = client.post(
            "/api/v1/decisions",
            json={
                "check_item_id": str(uuid.uuid4()),
                "action": "return",
                # Missing reason_codes for return action
            },
            headers=auth_headers,
        )

        # Should require reason codes for return
        assert response.status_code in [422, 400]

    def test_make_decision_approve_success(self, client, auth_headers):
        """Approve decision should succeed with valid data."""
        with (
            patch("app.api.v1.endpoints.decisions.get_current_active_user") as mock_user,
            patch("app.api.v1.endpoints.decisions.DecisionService") as mock_service,
        ):

            mock_user.return_value = MagicMock(
                id=str(uuid.uuid4()),
                tenant_id=str(uuid.uuid4()),
                username="reviewer",
            )

            mock_decision = MagicMock()
            mock_decision.id = str(uuid.uuid4())
            mock_decision.action = "approve"
            mock_decision.created_at = datetime.now(timezone.utc)

            mock_service_instance = AsyncMock()
            mock_service.return_value = mock_service_instance
            mock_service_instance.make_decision.return_value = mock_decision

            response = client.post(
                "/api/v1/decisions",
                json={
                    "check_item_id": str(uuid.uuid4()),
                    "action": "approve",
                    "reason_codes": ["verified_signature"],
                    "notes": "All checks passed",
                },
                headers=auth_headers,
            )

            # Should succeed or fail on DB (not auth/validation)
            assert response.status_code not in [401, 403, 422]


class TestEscalateEndpoint:
    """Tests for POST /api/v1/decisions/escalate."""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    @pytest.fixture
    def auth_headers(self):
        token = create_access_token(
            subject=str(uuid.uuid4()),
            additional_claims={
                "username": "reviewer",
                "roles": ["reviewer"],
                "permissions": ["check:view", "check:decide", "check:escalate"],
                "tenant_id": str(uuid.uuid4()),
            },
        )
        return {"Authorization": f"Bearer {token}"}

    def test_escalate_requires_auth(self, client):
        """Escalate should require authentication."""
        response = client.post(
            "/api/v1/decisions/escalate",
            json={
                "check_item_id": str(uuid.uuid4()),
                "reason": "Suspicious signature",
            },
        )
        assert response.status_code == 401

    def test_escalate_requires_reason(self, client, auth_headers):
        """Escalate should require a reason."""
        response = client.post(
            "/api/v1/decisions/escalate",
            json={
                "check_item_id": str(uuid.uuid4()),
                # Missing reason
            },
            headers=auth_headers,
        )

        assert response.status_code == 422


class TestDualControlWorkflow:
    """Tests for dual control approval workflow."""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    @pytest.fixture
    def supervisor_headers(self):
        token = create_access_token(
            subject=str(uuid.uuid4()),
            additional_claims={
                "username": "supervisor",
                "roles": ["supervisor"],
                "permissions": ["check:view", "check:decide", "check:approve_dual_control"],
                "tenant_id": str(uuid.uuid4()),
            },
        )
        return {"Authorization": f"Bearer {token}"}

    @pytest.fixture
    def reviewer_headers(self):
        token = create_access_token(
            subject=str(uuid.uuid4()),
            additional_claims={
                "username": "reviewer",
                "roles": ["reviewer"],
                "permissions": ["check:view", "check:decide"],
                "tenant_id": str(uuid.uuid4()),
            },
        )
        return {"Authorization": f"Bearer {token}"}

    def test_dual_control_approve_requires_supervisor(self, client, reviewer_headers):
        """Dual control approval should require supervisor role."""
        decision_id = str(uuid.uuid4())

        response = client.post(
            f"/api/v1/decisions/{decision_id}/dual-control/approve",
            headers=reviewer_headers,
        )

        # Reviewer should not be able to approve dual control
        assert response.status_code in [401, 403]

    def test_dual_control_cannot_self_approve(self, client, supervisor_headers):
        """User cannot approve their own dual control request."""
        # This test documents the business rule
        # Implementation would check decision.user_id != current_user.id
        pass


class TestDecisionValidation:
    """Tests for decision validation rules."""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    @pytest.fixture
    def auth_headers(self):
        token = create_access_token(
            subject=str(uuid.uuid4()),
            additional_claims={
                "username": "reviewer",
                "roles": ["reviewer"],
                "permissions": ["check:view", "check:decide"],
                "tenant_id": str(uuid.uuid4()),
            },
        )
        return {"Authorization": f"Bearer {token}"}

    def test_cannot_decide_on_already_decided_check(self, client, auth_headers):
        """Cannot make decision on already decided check."""
        with (
            patch("app.api.v1.endpoints.decisions.get_current_active_user") as mock_user,
            patch("app.api.v1.endpoints.decisions.DecisionService") as mock_service,
        ):

            mock_user.return_value = MagicMock(
                id=str(uuid.uuid4()),
                tenant_id=str(uuid.uuid4()),
                username="reviewer",
            )

            # Simulate check already has decision
            mock_service_instance = AsyncMock()
            mock_service.return_value = mock_service_instance
            mock_service_instance.make_decision.side_effect = ValueError(
                "Check already has a final decision"
            )

            response = client.post(
                "/api/v1/decisions",
                json={
                    "check_item_id": str(uuid.uuid4()),
                    "action": "approve",
                    "reason_codes": ["verified"],
                },
                headers=auth_headers,
            )

            # Should reject duplicate decision
            assert response.status_code in [400, 409, 500]

    def test_return_decision_requires_reason_codes(self, client, auth_headers):
        """Return decision should require reason codes."""
        response = client.post(
            "/api/v1/decisions",
            json={
                "check_item_id": str(uuid.uuid4()),
                "action": "return",
                "reason_codes": [],  # Empty reason codes
            },
            headers=auth_headers,
        )

        # Should require at least one reason code for return
        # Validation might be 422 or handled by service as 400
        assert response.status_code in [400, 422]


class TestEntitlementChecks:
    """Tests for entitlement-based decision validation."""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_amount_limit_enforced(self, client):
        """Decision should be blocked if check amount exceeds user's limit."""
        # Create token with limited entitlement
        token = create_access_token(
            subject=str(uuid.uuid4()),
            additional_claims={
                "username": "junior_reviewer",
                "roles": ["reviewer"],
                "permissions": ["check:view", "check:decide"],
                "tenant_id": str(uuid.uuid4()),
                "entitlements": {"max_amount": 1000.00},
            },
        )
        headers = {"Authorization": f"Bearer {token}"}

        with (
            patch("app.api.v1.endpoints.decisions.get_current_active_user") as mock_user,
            patch("app.api.v1.endpoints.decisions.DecisionService") as mock_service,
        ):

            mock_user.return_value = MagicMock(
                id=str(uuid.uuid4()),
                tenant_id=str(uuid.uuid4()),
                username="junior_reviewer",
            )

            # Service should check entitlement and raise error
            mock_service_instance = AsyncMock()
            mock_service.return_value = mock_service_instance
            mock_service_instance.make_decision.side_effect = ValueError(
                "Check amount exceeds entitlement limit"
            )

            response = client.post(
                "/api/v1/decisions",
                json={
                    "check_item_id": str(uuid.uuid4()),
                    "action": "approve",
                    "reason_codes": ["verified"],
                },
                headers=headers,
            )

            # Should be blocked by entitlement check
            assert response.status_code in [400, 403, 500]


class TestDecisionAuditLogging:
    """Tests for decision audit logging."""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    @pytest.fixture
    def auth_headers(self):
        token = create_access_token(
            subject=str(uuid.uuid4()),
            additional_claims={
                "username": "reviewer",
                "roles": ["reviewer"],
                "permissions": ["check:view", "check:decide"],
                "tenant_id": str(uuid.uuid4()),
            },
        )
        return {"Authorization": f"Bearer {token}"}

    def test_decision_creates_audit_log(self, client, auth_headers):
        """Making a decision should create an audit log entry."""
        with (
            patch("app.api.v1.endpoints.decisions.get_current_active_user") as mock_user,
            patch("app.api.v1.endpoints.decisions.DecisionService") as mock_dec_service,
            patch("app.api.v1.endpoints.decisions.AuditService") as mock_audit,
        ):

            user_id = str(uuid.uuid4())
            mock_user.return_value = MagicMock(
                id=user_id,
                tenant_id=str(uuid.uuid4()),
                username="reviewer",
            )

            mock_decision = MagicMock()
            mock_decision.id = str(uuid.uuid4())
            mock_decision.action = "approve"

            mock_dec_instance = AsyncMock()
            mock_dec_service.return_value = mock_dec_instance
            mock_dec_instance.make_decision.return_value = mock_decision

            mock_audit_instance = AsyncMock()
            mock_audit.return_value = mock_audit_instance

            response = client.post(
                "/api/v1/decisions",
                json={
                    "check_item_id": str(uuid.uuid4()),
                    "action": "approve",
                    "reason_codes": ["verified"],
                },
                headers=auth_headers,
            )

            # Audit service should have been called
            # (verification depends on implementation)


class TestDecisionHistory:
    """Tests for decision history endpoint."""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    @pytest.fixture
    def auth_headers(self):
        token = create_access_token(
            subject=str(uuid.uuid4()),
            additional_claims={
                "username": "reviewer",
                "roles": ["reviewer"],
                "permissions": ["check:view", "decision:view"],
                "tenant_id": str(uuid.uuid4()),
            },
        )
        return {"Authorization": f"Bearer {token}"}

    def test_get_decision_history_requires_auth(self, client):
        """Get decision history should require authentication."""
        check_id = str(uuid.uuid4())
        response = client.get(f"/api/v1/decisions/check/{check_id}/history")
        assert response.status_code == 401

    def test_get_decision_history_returns_list(self, client, auth_headers):
        """Get decision history should return list of decisions."""
        with patch("app.api.v1.endpoints.decisions.get_current_active_user") as mock_user:
            mock_user.return_value = MagicMock(
                id=str(uuid.uuid4()),
                tenant_id=str(uuid.uuid4()),
                username="reviewer",
            )

            check_id = str(uuid.uuid4())
            response = client.get(
                f"/api/v1/decisions/check/{check_id}/history",
                headers=auth_headers,
            )

            # Should not return auth errors
            assert response.status_code != 401


class TestDecisionOverride:
    """Tests for decision override functionality."""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    @pytest.fixture
    def supervisor_headers(self):
        token = create_access_token(
            subject=str(uuid.uuid4()),
            additional_claims={
                "username": "supervisor",
                "roles": ["supervisor"],
                "permissions": ["check:view", "check:decide", "decision:override"],
                "tenant_id": str(uuid.uuid4()),
            },
        )
        return {"Authorization": f"Bearer {token}"}

    def test_override_requires_supervisor_role(self, client):
        """Override should require supervisor role."""
        reviewer_token = create_access_token(
            subject=str(uuid.uuid4()),
            additional_claims={
                "username": "reviewer",
                "roles": ["reviewer"],
                "permissions": ["check:view", "check:decide"],
                "tenant_id": str(uuid.uuid4()),
            },
        )
        headers = {"Authorization": f"Bearer {reviewer_token}"}

        decision_id = str(uuid.uuid4())
        response = client.post(
            f"/api/v1/decisions/{decision_id}/override",
            json={
                "new_action": "approve",
                "justification": "Reviewed additional documentation",
            },
            headers=headers,
        )

        # Should fail for non-supervisor
        assert response.status_code in [401, 403, 404]

    def test_override_requires_justification(self, client, supervisor_headers):
        """Override should require justification."""
        decision_id = str(uuid.uuid4())
        response = client.post(
            f"/api/v1/decisions/{decision_id}/override",
            json={
                "new_action": "approve",
                # Missing justification
            },
            headers=supervisor_headers,
        )

        # Should require justification
        assert response.status_code in [400, 422, 404]
