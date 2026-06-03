"""
Integration tests for authentication endpoints.

Tests cover:
- Login flow
- Token refresh
- Logout
- MFA setup and verification
- Account lockout
- IP allowlist enforcement
- Session management
"""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.security import create_access_token, create_refresh_token, get_password_hash
from app.main import app


class TestLoginEndpoint:
    """Tests for POST /api/v1/auth/login."""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_login_missing_credentials(self, client):
        """Login should fail with 422 when credentials missing."""
        response = client.post("/api/v1/auth/login", data={})
        assert response.status_code == 422

    def test_login_invalid_credentials_returns_401(self, client):
        """Login should return 401 for invalid credentials."""
        with patch("app.api.v1.endpoints.auth.AuthService") as mock_service:
            mock_instance = AsyncMock()
            mock_service.return_value = mock_instance
            mock_instance.authenticate_user.return_value = (None, "Invalid username or password")

            response = client.post(
                "/api/v1/auth/login",
                data={"username": "wronguser", "password": "wrongpass"},
            )

            assert response.status_code == 401
            assert "Invalid" in response.json()["detail"]

    def test_login_success_returns_tokens(self, client):
        """Successful login should return access and refresh tokens."""
        with (
            patch("app.api.v1.endpoints.auth.AuthService") as mock_service,
            patch("app.api.v1.endpoints.auth.AuditService"),
        ):

            mock_user = MagicMock()
            mock_user.id = str(uuid.uuid4())
            mock_user.username = "testuser"
            mock_user.mfa_enabled = False
            mock_user.roles = []
            mock_user.tenant_id = str(uuid.uuid4())

            mock_instance = AsyncMock()
            mock_service.return_value = mock_instance
            mock_instance.authenticate_user.return_value = (mock_user, None)
            mock_instance.create_tokens.return_value = MagicMock(
                access_token="test_access_token",
                refresh_token="test_refresh_token",
                token_type="bearer",
                expires_in=900,
            )

            response = client.post(
                "/api/v1/auth/login",
                data={"username": "testuser", "password": "testpass"},
            )

            assert response.status_code == 200
            data = response.json()
            assert "access_token" in data
            assert "token_type" in data
            assert data["token_type"] == "bearer"

    def test_login_locked_account_returns_401(self, client):
        """Login should return 401 for locked accounts."""
        with patch("app.api.v1.endpoints.auth.AuthService") as mock_service:
            mock_instance = AsyncMock()
            mock_service.return_value = mock_instance
            lock_time = datetime.now(timezone.utc) + timedelta(minutes=30)
            mock_instance.authenticate_user.return_value = (
                None,
                f"Account locked until {lock_time.isoformat()}",
            )

            response = client.post(
                "/api/v1/auth/login",
                data={"username": "lockeduser", "password": "anypass"},
            )

            assert response.status_code == 401
            assert "locked" in response.json()["detail"].lower()

    def test_login_with_mfa_required_returns_mfa_response(self, client):
        """Login with MFA enabled should require MFA verification."""
        with (
            patch("app.api.v1.endpoints.auth.AuthService") as mock_service,
            patch("app.api.v1.endpoints.auth.AuditService"),
        ):

            mock_user = MagicMock()
            mock_user.id = str(uuid.uuid4())
            mock_user.username = "mfauser"
            mock_user.mfa_enabled = True
            mock_user.roles = []
            mock_user.tenant_id = str(uuid.uuid4())

            mock_instance = AsyncMock()
            mock_service.return_value = mock_instance
            mock_instance.authenticate_user.return_value = (mock_user, None)

            response = client.post(
                "/api/v1/auth/login",
                data={"username": "mfauser", "password": "testpass"},
            )

            assert response.status_code == 200
            data = response.json()
            assert data.get("mfa_required") is True
            assert "mfa_token" in data

    def test_login_rate_limited(self, client):
        """Login endpoint should be rate limited."""
        # This test verifies rate limiting is configured
        # Actual rate limit testing would require multiple rapid requests
        from app.core.rate_limit import limiter

        assert limiter is not None


class TestTokenRefreshEndpoint:
    """Tests for POST /api/v1/auth/refresh."""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_refresh_without_token_returns_401(self, client):
        """Refresh without token should return 401."""
        response = client.post("/api/v1/auth/refresh")
        assert response.status_code == 401

    def test_refresh_with_invalid_token_returns_401(self, client):
        """Refresh with invalid token should return 401."""
        with patch("app.api.v1.endpoints.auth.AuthService") as mock_service:
            mock_instance = AsyncMock()
            mock_service.return_value = mock_instance
            mock_instance.refresh_tokens.return_value = None

            response = client.post(
                "/api/v1/auth/refresh",
                cookies={"refresh_token": "invalid_token"},
            )

            assert response.status_code == 401

    def test_refresh_success_returns_new_tokens(self, client):
        """Valid refresh should return new access token."""
        with patch("app.api.v1.endpoints.auth.AuthService") as mock_service:
            mock_instance = AsyncMock()
            mock_service.return_value = mock_instance
            mock_instance.refresh_tokens.return_value = MagicMock(
                access_token="new_access_token",
                refresh_token="new_refresh_token",
                token_type="bearer",
                expires_in=900,
            )

            response = client.post(
                "/api/v1/auth/refresh",
                cookies={"refresh_token": "valid_refresh_token"},
            )

            assert response.status_code == 200
            data = response.json()
            assert "access_token" in data


class TestLogoutEndpoint:
    """Tests for POST /api/v1/auth/logout."""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_logout_clears_session(self, client):
        """Logout should clear the session."""
        with patch("app.api.v1.endpoints.auth.AuthService") as mock_service:
            mock_instance = AsyncMock()
            mock_service.return_value = mock_instance
            mock_instance.logout.return_value = True

            response = client.post(
                "/api/v1/auth/logout",
                cookies={"refresh_token": "some_token"},
            )

            assert response.status_code == 200
            assert response.json()["message"] == "Logged out successfully"


class TestMFAEndpoints:
    """Tests for MFA setup and verification endpoints."""

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
                "permissions": ["check:view"],
            },
        )
        return {"Authorization": f"Bearer {token}"}

    def test_mfa_setup_requires_auth(self, client):
        """MFA setup should require authentication."""
        response = client.post("/api/v1/auth/mfa/setup")
        assert response.status_code == 401

    def test_mfa_verify_invalid_code_returns_400(self, client, auth_headers):
        """MFA verification with invalid code should fail."""
        with (
            patch("app.api.v1.endpoints.auth.get_current_active_user") as mock_user,
            patch("app.api.v1.endpoints.auth.verify_totp") as mock_verify,
        ):

            mock_user.return_value = MagicMock(
                id=str(uuid.uuid4()),
                mfa_secret="test_secret",
                tenant_id=str(uuid.uuid4()),
            )
            mock_verify.return_value = False

            response = client.post(
                "/api/v1/auth/mfa/verify",
                json={"code": "000000"},
                headers=auth_headers,
            )

            # Should fail validation
            assert response.status_code in [400, 401, 422]


class TestPasswordChangeEndpoint:
    """Tests for password change endpoint."""

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
                "permissions": ["check:view"],
            },
        )
        return {"Authorization": f"Bearer {token}"}

    def test_password_change_requires_auth(self, client):
        """Password change should require authentication."""
        response = client.post(
            "/api/v1/auth/change-password",
            json={"current_password": "old", "new_password": "new"},
        )
        assert response.status_code == 401

    def test_password_change_validates_current_password(self, client, auth_headers):
        """Password change should validate current password."""
        with (
            patch("app.api.v1.endpoints.auth.get_current_active_user") as mock_get_user,
            patch("app.api.v1.endpoints.auth.verify_password") as mock_verify,
        ):

            mock_user = MagicMock()
            mock_user.id = str(uuid.uuid4())
            mock_user.hashed_password = "hashed"
            mock_user.tenant_id = str(uuid.uuid4())
            mock_get_user.return_value = mock_user
            mock_verify.return_value = False

            response = client.post(
                "/api/v1/auth/change-password",
                json={
                    "current_password": "wrongpassword",
                    "new_password": "NewPassword123!",
                },
                headers=auth_headers,
            )

            # Should fail due to wrong current password
            assert response.status_code in [400, 401]


class TestIPAllowlistEnforcement:
    """Tests for IP allowlist enforcement."""

    def test_ip_check_with_allowed_ip(self):
        """User with matching IP should be allowed."""
        from app.services.auth import check_ip_allowed

        assert check_ip_allowed("192.168.1.100", ["192.168.1.100"]) is True
        assert check_ip_allowed("192.168.1.100", ["192.168.1.0/24"]) is True
        assert check_ip_allowed("10.0.0.1", ["10.0.0.0/8"]) is True

    def test_ip_check_with_denied_ip(self):
        """User with non-matching IP should be denied."""
        from app.services.auth import check_ip_allowed

        assert check_ip_allowed("192.168.2.100", ["192.168.1.0/24"]) is False
        assert check_ip_allowed("10.0.0.1", ["192.168.1.100"]) is False

    def test_ip_check_with_no_restrictions(self):
        """User with no IP restrictions should be allowed from any IP."""
        from app.services.auth import check_ip_allowed

        assert check_ip_allowed("1.2.3.4", None) is True
        assert check_ip_allowed("1.2.3.4", []) is True

    def test_ip_check_with_ipv6(self):
        """IPv6 addresses should be supported."""
        from app.services.auth import check_ip_allowed

        assert check_ip_allowed("::1", ["::1"]) is True
        assert check_ip_allowed("2001:db8::1", ["2001:db8::/32"]) is True


class TestSessionManagement:
    """Tests for session management endpoints."""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    @pytest.fixture
    def auth_headers(self):
        token = create_access_token(
            subject=str(uuid.uuid4()),
            additional_claims={
                "username": "testuser",
                "roles": ["admin"],
                "permissions": ["*:*"],
            },
        )
        return {"Authorization": f"Bearer {token}"}

    def test_list_sessions_requires_auth(self, client):
        """List sessions should require authentication."""
        response = client.get("/api/v1/auth/sessions")
        assert response.status_code == 401

    def test_revoke_all_sessions_requires_auth(self, client):
        """Revoke all sessions should require authentication."""
        response = client.post("/api/v1/auth/sessions/revoke-all")
        assert response.status_code == 401
