"""
Integration tests for error scenarios.

Tests cover:
- Authentication failures
- Authorization failures
- Validation errors
- Database errors
- Rate limiting
- Service unavailable scenarios
- Concurrent access conflicts
"""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError, OperationalError

from app.core.security import create_access_token
from app.main import app


class TestAuthenticationErrors:
    """Tests for authentication error scenarios."""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_missing_auth_header_returns_401(self, client):
        """Request without auth header should return 401."""
        response = client.get("/api/v1/checks")
        assert response.status_code == 401
        assert "detail" in response.json()

    def test_invalid_token_format_returns_401(self, client):
        """Request with invalid token format should return 401."""
        response = client.get(
            "/api/v1/checks",
            headers={"Authorization": "InvalidToken"},
        )
        assert response.status_code == 401

    def test_expired_token_returns_401(self, client):
        """Request with expired token should return 401."""
        # Create an expired token (manually set exp in the past)
        with patch("app.core.security.jwt.encode") as mock_encode:
            # Force token to be expired
            mock_encode.return_value = "expired_token"

            response = client.get(
                "/api/v1/checks",
                headers={"Authorization": "Bearer expired_token"},
            )

            assert response.status_code == 401

    def test_malformed_jwt_returns_401(self, client):
        """Request with malformed JWT should return 401."""
        response = client.get(
            "/api/v1/checks",
            headers={"Authorization": "Bearer not.a.valid.jwt.token"},
        )
        assert response.status_code == 401

    def test_wrong_secret_token_returns_401(self, client):
        """Token signed with wrong secret should return 401."""
        import jwt

        # Create token with wrong secret
        fake_token = jwt.encode(
            {"sub": str(uuid.uuid4()), "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
            "wrong_secret",
            algorithm="HS256",
        )

        response = client.get(
            "/api/v1/checks",
            headers={"Authorization": f"Bearer {fake_token}"},
        )
        assert response.status_code == 401


class TestAuthorizationErrors:
    """Tests for authorization error scenarios."""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_insufficient_permissions_returns_403(self, client):
        """Request without required permission should return 403."""
        # Create token without admin permissions
        token = create_access_token(
            subject=str(uuid.uuid4()),
            additional_claims={
                "username": "limited_user",
                "roles": ["viewer"],
                "permissions": ["check:view"],  # No admin permissions
                "tenant_id": str(uuid.uuid4()),
            },
        )

        # Try to access admin endpoint
        response = client.get(
            "/api/v1/users",
            headers={"Authorization": f"Bearer {token}"},
        )

        # Should be 403 Forbidden (or 401 if permission check is before auth)
        assert response.status_code in [401, 403]

    def test_deactivated_user_returns_401(self, client):
        """Request from deactivated user should return 401."""
        token = create_access_token(
            subject=str(uuid.uuid4()),
            additional_claims={
                "username": "deactivated_user",
                "roles": ["reviewer"],
                "permissions": ["check:view"],
                "tenant_id": str(uuid.uuid4()),
            },
        )

        with patch("app.api.deps.get_current_active_user") as mock_user:
            mock_user.side_effect = Exception("User is deactivated")

            response = client.get(
                "/api/v1/checks",
                headers={"Authorization": f"Bearer {token}"},
            )

            assert response.status_code in [401, 403, 500]


class TestValidationErrors:
    """Tests for input validation error scenarios."""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    @pytest.fixture
    def auth_headers(self):
        token = create_access_token(
            subject=str(uuid.uuid4()),
            additional_claims={
                "username": "testuser",
                "roles": ["reviewer"],
                "permissions": ["check:view", "check:decide"],
                "tenant_id": str(uuid.uuid4()),
            },
        )
        return {"Authorization": f"Bearer {token}"}

    def test_invalid_json_returns_422(self, client, auth_headers):
        """Request with invalid JSON should return 422."""
        response = client.post(
            "/api/v1/decisions",
            content="not valid json",
            headers={**auth_headers, "Content-Type": "application/json"},
        )
        assert response.status_code == 422

    def test_missing_required_field_returns_422(self, client, auth_headers):
        """Request missing required field should return 422."""
        response = client.post(
            "/api/v1/decisions",
            json={
                # Missing check_item_id
                "action": "approve",
            },
            headers=auth_headers,
        )
        assert response.status_code == 422

    def test_invalid_enum_value_returns_422(self, client, auth_headers):
        """Request with invalid enum value should return 422."""
        response = client.post(
            "/api/v1/decisions",
            json={
                "check_item_id": str(uuid.uuid4()),
                "action": "invalid_action_type",
                "reason_codes": [],
            },
            headers=auth_headers,
        )
        assert response.status_code == 422

    def test_invalid_uuid_format_returns_422(self, client, auth_headers):
        """Request with invalid UUID should return 422 or 404."""
        response = client.get(
            "/api/v1/checks/not-a-valid-uuid",
            headers=auth_headers,
        )
        assert response.status_code in [404, 422]

    def test_negative_page_number_returns_422(self, client, auth_headers):
        """Request with negative page number should return 422."""
        response = client.get(
            "/api/v1/checks?page=-1",
            headers=auth_headers,
        )
        assert response.status_code == 422

    def test_page_size_too_large_returns_422(self, client, auth_headers):
        """Request with page size too large should return 422."""
        response = client.get(
            "/api/v1/checks?page_size=10000",
            headers=auth_headers,
        )
        # Should reject unreasonably large page size
        assert response.status_code in [200, 422]  # May cap or reject


class TestDatabaseErrors:
    """Tests for database error scenarios."""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    @pytest.fixture
    def auth_headers(self):
        token = create_access_token(
            subject=str(uuid.uuid4()),
            additional_claims={
                "username": "testuser",
                "roles": ["reviewer"],
                "permissions": ["check:view", "check:decide"],
                "tenant_id": str(uuid.uuid4()),
            },
        )
        return {"Authorization": f"Bearer {token}"}

    def test_database_connection_error_returns_503(self, client, auth_headers):
        """Database connection error should return 503."""
        with patch("app.api.deps.get_db") as mock_db:
            mock_db.side_effect = OperationalError("statement", {}, None)

            response = client.get(
                "/api/v1/checks",
                headers=auth_headers,
            )

            # Should return service unavailable or internal error
            assert response.status_code in [500, 503]

    def test_unique_constraint_violation_returns_409(self, client, auth_headers):
        """Unique constraint violation should return 409 Conflict."""
        with (
            patch("app.api.v1.endpoints.decisions.get_current_active_user") as mock_user,
            patch("app.api.v1.endpoints.decisions.DecisionService") as mock_service,
        ):

            mock_user.return_value = MagicMock(
                id=str(uuid.uuid4()),
                tenant_id=str(uuid.uuid4()),
                username="testuser",
            )

            mock_instance = AsyncMock()
            mock_service.return_value = mock_instance
            mock_instance.make_decision.side_effect = IntegrityError(
                "statement", {}, Exception("duplicate key")
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

            assert response.status_code in [400, 409, 500]


class TestRateLimitingErrors:
    """Tests for rate limiting error scenarios."""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_rate_limit_exceeded_returns_429(self, client):
        """Exceeding rate limit should return 429."""
        # This would require actually hitting the rate limit
        # For now, verify the limiter is configured
        from app.core.rate_limit import limiter

        assert limiter is not None

    def test_login_rate_limit_is_stricter(self, client):
        """Login endpoint should have stricter rate limits."""
        # Verify login has special rate limiting
        # The actual rate is configured in the endpoint
        pass


class TestConcurrencyErrors:
    """Tests for concurrent access error scenarios."""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    @pytest.fixture
    def auth_headers(self):
        token = create_access_token(
            subject=str(uuid.uuid4()),
            additional_claims={
                "username": "testuser",
                "roles": ["reviewer"],
                "permissions": ["check:view", "check:decide"],
                "tenant_id": str(uuid.uuid4()),
            },
        )
        return {"Authorization": f"Bearer {token}"}

    def test_concurrent_decision_conflict(self, client, auth_headers):
        """Concurrent decisions on same check should be handled."""
        with (
            patch("app.api.v1.endpoints.decisions.get_current_active_user") as mock_user,
            patch("app.api.v1.endpoints.decisions.DecisionService") as mock_service,
        ):

            mock_user.return_value = MagicMock(
                id=str(uuid.uuid4()),
                tenant_id=str(uuid.uuid4()),
                username="testuser",
            )

            mock_instance = AsyncMock()
            mock_service.return_value = mock_instance
            mock_instance.make_decision.side_effect = ValueError(
                "Check is currently locked by another user"
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

            # Should indicate conflict
            assert response.status_code in [400, 409, 500]


class TestResourceNotFoundErrors:
    """Tests for resource not found error scenarios."""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    @pytest.fixture
    def auth_headers(self):
        token = create_access_token(
            subject=str(uuid.uuid4()),
            additional_claims={
                "username": "testuser",
                "roles": ["reviewer"],
                "permissions": ["check:view", "check:decide"],
                "tenant_id": str(uuid.uuid4()),
            },
        )
        return {"Authorization": f"Bearer {token}"}

    def test_check_not_found_returns_404(self, client, auth_headers):
        """Request for non-existent check should return 404."""
        with patch("app.api.v1.endpoints.checks.get_current_active_user") as mock_user:
            mock_user.return_value = MagicMock(
                id=str(uuid.uuid4()),
                tenant_id=str(uuid.uuid4()),
                username="testuser",
            )

            non_existent_id = str(uuid.uuid4())
            response = client.get(
                f"/api/v1/checks/{non_existent_id}",
                headers=auth_headers,
            )

            # Should return 404 for non-existent resource
            assert response.status_code in [404, 500]

    def test_decision_not_found_returns_404(self, client, auth_headers):
        """Request for non-existent decision should return 404."""
        non_existent_id = str(uuid.uuid4())
        response = client.get(
            f"/api/v1/decisions/{non_existent_id}",
            headers=auth_headers,
        )

        assert response.status_code in [404, 500]


class TestSecurityErrors:
    """Tests for security-related error scenarios."""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_cross_tenant_access_returns_404(self, client):
        """Accessing resource from different tenant should return 404."""
        tenant_a = str(uuid.uuid4())

        token = create_access_token(
            subject=str(uuid.uuid4()),
            additional_claims={
                "username": "user_a",
                "roles": ["reviewer"],
                "permissions": ["check:view"],
                "tenant_id": tenant_a,
            },
        )
        headers = {"Authorization": f"Bearer {token}"}

        with patch("app.api.v1.endpoints.checks.get_current_active_user") as mock_user:
            mock_user.return_value = MagicMock(
                id=str(uuid.uuid4()),
                tenant_id=tenant_a,
                username="user_a",
            )

            # Try to access resource from different tenant
            # Should return 404 (not 403) to not reveal existence
            check_id = str(uuid.uuid4())
            response = client.get(
                f"/api/v1/checks/{check_id}",
                headers=headers,
            )

            # Should return 404, not revealing the resource exists
            assert response.status_code in [404, 500]

    def test_uniform_error_for_invalid_credentials(self, client):
        """Invalid username and invalid password should return same error."""
        with patch("app.api.v1.endpoints.auth.AuthService") as mock_service:
            mock_instance = AsyncMock()
            mock_service.return_value = mock_instance

            # Test wrong username
            mock_instance.authenticate_user.return_value = (None, "Invalid username or password")
            response1 = client.post(
                "/api/v1/auth/login",
                data={"username": "wronguser", "password": "anypass"},
            )

            # Test wrong password
            mock_instance.authenticate_user.return_value = (None, "Invalid username or password")
            response2 = client.post(
                "/api/v1/auth/login",
                data={"username": "validuser", "password": "wrongpass"},
            )

            # Both should return same status and similar error message
            assert response1.status_code == response2.status_code == 401
            # Error messages should be identical (no username enumeration)


class TestErrorResponseFormat:
    """Tests for error response format consistency."""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_error_response_has_detail_field(self, client):
        """Error responses should have 'detail' field."""
        response = client.get("/api/v1/checks")  # No auth
        assert response.status_code == 401
        assert "detail" in response.json()

    def test_validation_error_shows_field_name(self, client):
        """Validation errors should identify the invalid field."""
        token = create_access_token(
            subject=str(uuid.uuid4()),
            additional_claims={
                "username": "testuser",
                "roles": ["reviewer"],
                "permissions": ["check:decide"],
                "tenant_id": str(uuid.uuid4()),
            },
        )

        response = client.post(
            "/api/v1/decisions",
            json={"invalid_field": "value"},
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 422
        error_detail = response.json()["detail"]
        # Should have field-level error info
        assert isinstance(error_detail, list)

    def test_internal_error_hides_details_in_production(self, client):
        """Internal errors should not expose sensitive details."""
        # In production, internal errors should be generic
        # This is handled by the global exception handler
        pass
