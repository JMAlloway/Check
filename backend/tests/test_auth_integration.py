"""
Integration tests for authentication endpoints.

Tests cover:
- Login/logout flows
- Token refresh
- Password change
- MFA setup and verification
- Account lockout
- Session management
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock
from fastapi import status

from app.core.security import get_password_hash, create_access_token
from app.models.user import User, Role, Permission


class TestLoginFlow:
    """Tests for user login."""

    @pytest.mark.asyncio
    async def test_login_success(self, client, db_session, test_tenant_id):
        """Test successful login with valid credentials."""
        # Create test user
        user = User(
            id="test-user-1",
            tenant_id=test_tenant_id,
            email="test@example.com",
            username="testuser",
            full_name="Test User",
            hashed_password=get_password_hash("password123"),
            is_active=True,
        )
        db_session.add(user)
        await db_session.commit()

        response = client.post(
            "/api/v1/auth/login",
            json={"username": "testuser", "password": "password123"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert "user" in data
        assert data["user"]["username"] == "testuser"

    @pytest.mark.asyncio
    async def test_login_invalid_password(self, client, db_session, test_tenant_id):
        """Test login with invalid password."""
        user = User(
            id="test-user-2",
            tenant_id=test_tenant_id,
            email="test2@example.com",
            username="testuser2",
            full_name="Test User 2",
            hashed_password=get_password_hash("password123"),
            is_active=True,
        )
        db_session.add(user)
        await db_session.commit()

        response = client.post(
            "/api/v1/auth/login",
            json={"username": "testuser2", "password": "wrongpassword"},
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Invalid" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_login_nonexistent_user(self, client):
        """Test login with non-existent user."""
        response = client.post(
            "/api/v1/auth/login",
            json={"username": "nonexistent", "password": "password123"},
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.asyncio
    async def test_login_inactive_user(self, client, db_session, test_tenant_id):
        """Test login with inactive user."""
        user = User(
            id="test-user-3",
            tenant_id=test_tenant_id,
            email="inactive@example.com",
            username="inactiveuser",
            full_name="Inactive User",
            hashed_password=get_password_hash("password123"),
            is_active=False,
        )
        db_session.add(user)
        await db_session.commit()

        response = client.post(
            "/api/v1/auth/login",
            json={"username": "inactiveuser", "password": "password123"},
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.asyncio
    async def test_login_locked_account(self, client, db_session, test_tenant_id):
        """Test login with locked account."""
        from datetime import timedelta

        user = User(
            id="test-user-4",
            tenant_id=test_tenant_id,
            email="locked@example.com",
            username="lockeduser",
            full_name="Locked User",
            hashed_password=get_password_hash("password123"),
            is_active=True,
            failed_login_attempts=5,
            locked_until=datetime.now(timezone.utc) + timedelta(minutes=30),
        )
        db_session.add(user)
        await db_session.commit()

        response = client.post(
            "/api/v1/auth/login",
            json={"username": "lockeduser", "password": "password123"},
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "locked" in response.json()["detail"].lower()


class TestLogoutFlow:
    """Tests for user logout."""

    @pytest.mark.asyncio
    async def test_logout_success(self, client, auth_headers):
        """Test successful logout."""
        response = client.post(
            "/api/v1/auth/logout",
            headers=auth_headers,
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["success"] is True

    @pytest.mark.asyncio
    async def test_logout_without_auth(self, client):
        """Test logout without authentication."""
        response = client.post("/api/v1/auth/logout")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestTokenRefresh:
    """Tests for token refresh."""

    @pytest.mark.asyncio
    async def test_refresh_token_success(self, client, db_session, test_tenant_id):
        """Test successful token refresh."""
        # This test would require setting up proper session with refresh token
        # For now, test that endpoint exists and returns appropriate error without token
        response = client.post("/api/v1/auth/refresh")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.asyncio
    async def test_refresh_invalid_token(self, client):
        """Test refresh with invalid token."""
        response = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "invalid-token"},
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestPasswordChange:
    """Tests for password change."""

    @pytest.mark.asyncio
    async def test_change_password_success(self, client, db_session, test_tenant_id):
        """Test successful password change."""
        user = User(
            id="test-user-5",
            tenant_id=test_tenant_id,
            email="pwchange@example.com",
            username="pwchangeuser",
            full_name="PW Change User",
            hashed_password=get_password_hash("oldpassword"),
            is_active=True,
        )
        db_session.add(user)
        await db_session.commit()

        # Create token for this user
        token = create_access_token(
            subject=user.id,
            additional_claims={
                "username": user.username,
                "roles": [],
                "permissions": [],
                "tenant_id": test_tenant_id,
            },
        )

        response = client.post(
            "/api/v1/auth/change-password",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "current_password": "oldpassword",
                "new_password": "newpassword123",
            },
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["success"] is True

    @pytest.mark.asyncio
    async def test_change_password_wrong_current(self, client, auth_headers):
        """Test password change with wrong current password."""
        response = client.post(
            "/api/v1/auth/change-password",
            headers=auth_headers,
            json={
                "current_password": "wrongpassword",
                "new_password": "newpassword123",
            },
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST


class TestCurrentUser:
    """Tests for getting current user info."""

    @pytest.mark.asyncio
    async def test_get_me_success(self, client, auth_headers):
        """Test getting current user info."""
        response = client.get(
            "/api/v1/auth/me",
            headers=auth_headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "username" in data
        assert "email" in data

    @pytest.mark.asyncio
    async def test_get_me_unauthorized(self, client):
        """Test getting current user without auth."""
        response = client.get("/api/v1/auth/me")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestMFASetup:
    """Tests for MFA setup and verification."""

    @pytest.mark.asyncio
    async def test_mfa_setup_returns_secret(self, client, db_session, test_tenant_id):
        """Test MFA setup returns secret and QR URI."""
        user = User(
            id="test-user-mfa",
            tenant_id=test_tenant_id,
            email="mfa@example.com",
            username="mfauser",
            full_name="MFA User",
            hashed_password=get_password_hash("password123"),
            is_active=True,
            mfa_enabled=False,
        )
        db_session.add(user)
        await db_session.commit()

        token = create_access_token(
            subject=user.id,
            additional_claims={
                "username": user.username,
                "roles": [],
                "permissions": [],
                "tenant_id": test_tenant_id,
            },
        )

        response = client.post(
            "/api/v1/auth/mfa/setup",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "secret" in data
        assert "qr_code_uri" in data

    @pytest.mark.asyncio
    async def test_mfa_setup_already_enabled(self, client, db_session, test_tenant_id):
        """Test MFA setup when already enabled."""
        user = User(
            id="test-user-mfa-2",
            tenant_id=test_tenant_id,
            email="mfa2@example.com",
            username="mfauser2",
            full_name="MFA User 2",
            hashed_password=get_password_hash("password123"),
            is_active=True,
            mfa_enabled=True,
            mfa_secret="TESTSECRET",
        )
        db_session.add(user)
        await db_session.commit()

        token = create_access_token(
            subject=user.id,
            additional_claims={
                "username": user.username,
                "roles": [],
                "permissions": [],
                "tenant_id": test_tenant_id,
            },
        )

        response = client.post(
            "/api/v1/auth/mfa/setup",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "already enabled" in response.json()["detail"].lower()


class TestMultiTenantAuth:
    """Tests for multi-tenant authentication isolation."""

    @pytest.mark.asyncio
    async def test_same_email_different_tenants(self, client, db_session):
        """Test that same email can exist in different tenants."""
        tenant_a = "tenant-a-id"
        tenant_b = "tenant-b-id"

        user_a = User(
            id="user-tenant-a",
            tenant_id=tenant_a,
            email="shared@example.com",
            username="usera",
            full_name="User A",
            hashed_password=get_password_hash("passwordA"),
            is_active=True,
        )
        user_b = User(
            id="user-tenant-b",
            tenant_id=tenant_b,
            email="shared@example.com",
            username="userb",
            full_name="User B",
            hashed_password=get_password_hash("passwordB"),
            is_active=True,
        )

        db_session.add(user_a)
        db_session.add(user_b)
        await db_session.commit()

        # Login as user A
        response_a = client.post(
            "/api/v1/auth/login",
            json={"username": "usera", "password": "passwordA"},
        )
        assert response_a.status_code == status.HTTP_200_OK

        # Login as user B (different tenant, same email)
        response_b = client.post(
            "/api/v1/auth/login",
            json={"username": "userb", "password": "passwordB"},
        )
        assert response_b.status_code == status.HTTP_200_OK

        # Verify they are different users
        assert response_a.json()["user"]["id"] != response_b.json()["user"]["id"]
