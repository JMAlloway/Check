"""
Integration tests for user management endpoints.

Tests cover:
- User CRUD operations
- Role management
- Permission management
- Multi-tenant isolation
"""

import pytest
from fastapi import status

from app.core.security import create_access_token, get_password_hash
from app.models.user import User, Role, Permission


@pytest.fixture
def user_admin_token(test_tenant_id):
    """Create a token with user admin permissions."""
    return create_access_token(
        subject="user-admin",
        additional_claims={
            "username": "useradmin",
            "roles": ["admin"],
            "permissions": [
                "user:view",
                "user:create",
                "user:update",
                "role:view",
                "role:create",
                "permission:view",
            ],
            "tenant_id": test_tenant_id,
        },
    )


@pytest.fixture
def admin_headers(user_admin_token):
    """Auth headers for user admin."""
    return {"Authorization": f"Bearer {user_admin_token}"}


class TestListUsers:
    """Tests for listing users."""

    @pytest.mark.asyncio
    async def test_list_users_empty(self, client, admin_headers):
        """Test listing users when none exist."""
        response = client.get(
            "/api/v1/users",
            headers=admin_headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["items"] == []

    @pytest.mark.asyncio
    async def test_list_users_with_data(self, client, db_session, test_tenant_id, admin_headers):
        """Test listing users with data."""
        for i in range(5):
            user = User(
                id=f"user-list-{i}",
                tenant_id=test_tenant_id,
                email=f"user{i}@example.com",
                username=f"user{i}",
                full_name=f"User {i}",
                hashed_password=get_password_hash("password"),
                is_active=True,
            )
            db_session.add(user)
        await db_session.commit()

        response = client.get(
            "/api/v1/users",
            headers=admin_headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total"] == 5

    @pytest.mark.asyncio
    async def test_list_users_filter_active(self, client, db_session, test_tenant_id, admin_headers):
        """Test filtering users by active status."""
        # Create active user
        active_user = User(
            id="user-active",
            tenant_id=test_tenant_id,
            email="active@example.com",
            username="activeuser",
            full_name="Active User",
            hashed_password=get_password_hash("password"),
            is_active=True,
        )
        # Create inactive user
        inactive_user = User(
            id="user-inactive",
            tenant_id=test_tenant_id,
            email="inactive@example.com",
            username="inactiveuser",
            full_name="Inactive User",
            hashed_password=get_password_hash("password"),
            is_active=False,
        )
        db_session.add(active_user)
        db_session.add(inactive_user)
        await db_session.commit()

        response = client.get(
            "/api/v1/users?is_active=true",
            headers=admin_headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["is_active"] is True

    @pytest.mark.asyncio
    async def test_list_users_search(self, client, db_session, test_tenant_id, admin_headers):
        """Test searching users."""
        user1 = User(
            id="user-search-1",
            tenant_id=test_tenant_id,
            email="john.doe@example.com",
            username="johndoe",
            full_name="John Doe",
            hashed_password=get_password_hash("password"),
            is_active=True,
        )
        user2 = User(
            id="user-search-2",
            tenant_id=test_tenant_id,
            email="jane.smith@example.com",
            username="janesmith",
            full_name="Jane Smith",
            hashed_password=get_password_hash("password"),
            is_active=True,
        )
        db_session.add(user1)
        db_session.add(user2)
        await db_session.commit()

        response = client.get(
            "/api/v1/users?search=john",
            headers=admin_headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["username"] == "johndoe"


class TestCreateUser:
    """Tests for creating users."""

    @pytest.mark.asyncio
    async def test_create_user_success(self, client, admin_headers):
        """Test creating a new user."""
        response = client.post(
            "/api/v1/users",
            headers=admin_headers,
            json={
                "email": "newuser@example.com",
                "username": "newuser",
                "full_name": "New User",
                "password": "securepassword123",
                "department": "Operations",
            },
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["username"] == "newuser"
        assert data["email"] == "newuser@example.com"

    @pytest.mark.asyncio
    async def test_create_user_duplicate_email(self, client, db_session, test_tenant_id, admin_headers):
        """Test creating user with duplicate email."""
        existing = User(
            id="existing-user",
            tenant_id=test_tenant_id,
            email="existing@example.com",
            username="existing",
            full_name="Existing User",
            hashed_password=get_password_hash("password"),
            is_active=True,
        )
        db_session.add(existing)
        await db_session.commit()

        response = client.post(
            "/api/v1/users",
            headers=admin_headers,
            json={
                "email": "existing@example.com",
                "username": "newusername",
                "full_name": "New User",
                "password": "password123",
            },
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST


class TestGetUser:
    """Tests for getting a specific user."""

    @pytest.mark.asyncio
    async def test_get_user_success(self, client, db_session, test_tenant_id, admin_headers):
        """Test getting a user by ID."""
        user = User(
            id="user-get-1",
            tenant_id=test_tenant_id,
            email="getuser@example.com",
            username="getuser",
            full_name="Get User",
            hashed_password=get_password_hash("password"),
            is_active=True,
            department="IT",
        )
        db_session.add(user)
        await db_session.commit()

        response = client.get(
            "/api/v1/users/user-get-1",
            headers=admin_headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["id"] == "user-get-1"
        assert data["username"] == "getuser"

    @pytest.mark.asyncio
    async def test_get_user_not_found(self, client, admin_headers):
        """Test getting non-existent user."""
        response = client.get(
            "/api/v1/users/nonexistent",
            headers=admin_headers,
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_get_user_wrong_tenant(self, client, db_session, admin_headers):
        """Test that users from other tenants are not accessible."""
        user = User(
            id="user-other-tenant",
            tenant_id="other-tenant-id",
            email="other@example.com",
            username="otheruser",
            full_name="Other User",
            hashed_password=get_password_hash("password"),
            is_active=True,
        )
        db_session.add(user)
        await db_session.commit()

        response = client.get(
            "/api/v1/users/user-other-tenant",
            headers=admin_headers,
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestUpdateUser:
    """Tests for updating users."""

    @pytest.mark.asyncio
    async def test_update_user_name(self, client, db_session, test_tenant_id, admin_headers):
        """Test updating user name."""
        user = User(
            id="user-update-1",
            tenant_id=test_tenant_id,
            email="update@example.com",
            username="updateuser",
            full_name="Original Name",
            hashed_password=get_password_hash("password"),
            is_active=True,
        )
        db_session.add(user)
        await db_session.commit()

        response = client.patch(
            "/api/v1/users/user-update-1",
            headers=admin_headers,
            json={"full_name": "Updated Name"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["full_name"] == "Updated Name"

    @pytest.mark.asyncio
    async def test_update_user_deactivate(self, client, db_session, test_tenant_id, admin_headers):
        """Test deactivating a user."""
        user = User(
            id="user-deactivate",
            tenant_id=test_tenant_id,
            email="deactivate@example.com",
            username="deactivate",
            full_name="Deactivate User",
            hashed_password=get_password_hash("password"),
            is_active=True,
        )
        db_session.add(user)
        await db_session.commit()

        response = client.patch(
            "/api/v1/users/user-deactivate",
            headers=admin_headers,
            json={"is_active": False},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["is_active"] is False


class TestRoleManagement:
    """Tests for role management."""

    @pytest.mark.asyncio
    async def test_list_roles(self, client, db_session, admin_headers):
        """Test listing all roles."""
        # Create test roles
        for i in range(3):
            role = Role(
                id=f"role-{i}",
                name=f"Role {i}",
                description=f"Description for role {i}",
            )
            db_session.add(role)
        await db_session.commit()

        response = client.get(
            "/api/v1/users/roles/",
            headers=admin_headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 3

    @pytest.mark.asyncio
    async def test_create_role(self, client, admin_headers):
        """Test creating a new role."""
        response = client.post(
            "/api/v1/users/roles/",
            headers=admin_headers,
            json={
                "name": "New Role",
                "description": "A new role for testing",
            },
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["name"] == "New Role"

    @pytest.mark.asyncio
    async def test_create_duplicate_role(self, client, db_session, admin_headers):
        """Test creating duplicate role."""
        role = Role(
            id="existing-role",
            name="Existing Role",
            description="Already exists",
        )
        db_session.add(role)
        await db_session.commit()

        response = client.post(
            "/api/v1/users/roles/",
            headers=admin_headers,
            json={
                "name": "Existing Role",
                "description": "Duplicate",
            },
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST


class TestPermissionManagement:
    """Tests for permission management."""

    @pytest.mark.asyncio
    async def test_list_permissions(self, client, db_session, admin_headers):
        """Test listing all permissions."""
        # Create test permissions
        permissions = [
            Permission(
                id="perm-1",
                name="View Checks",
                resource="check_item",
                action="view",
            ),
            Permission(
                id="perm-2",
                name="Review Checks",
                resource="check_item",
                action="review",
            ),
        ]
        for perm in permissions:
            db_session.add(perm)
        await db_session.commit()

        response = client.get(
            "/api/v1/users/permissions/",
            headers=admin_headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 2


class TestUserRoleAssignment:
    """Tests for assigning roles to users."""

    @pytest.mark.asyncio
    async def test_assign_roles_to_user(self, client, db_session, test_tenant_id, admin_headers):
        """Test assigning roles to a user."""
        user = User(
            id="user-assign-roles",
            tenant_id=test_tenant_id,
            email="assignroles@example.com",
            username="assignroles",
            full_name="Assign Roles User",
            hashed_password=get_password_hash("password"),
            is_active=True,
        )
        role = Role(
            id="role-assign",
            name="Reviewer",
            description="Can review checks",
        )
        db_session.add(user)
        db_session.add(role)
        await db_session.commit()

        response = client.patch(
            "/api/v1/users/user-assign-roles",
            headers=admin_headers,
            json={"role_ids": ["role-assign"]},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["roles"]) == 1


class TestMultiTenantUsers:
    """Tests for multi-tenant user isolation."""

    @pytest.mark.asyncio
    async def test_users_isolated_by_tenant(self, client, db_session):
        """Test that users are isolated between tenants."""
        tenant_a = "user-tenant-a"
        tenant_b = "user-tenant-b"

        # Create users for each tenant
        for i in range(3):
            user_a = User(
                id=f"user-tenant-a-{i}",
                tenant_id=tenant_a,
                email=f"usera{i}@example.com",
                username=f"usera{i}",
                full_name=f"Tenant A User {i}",
                hashed_password=get_password_hash("password"),
                is_active=True,
            )
            db_session.add(user_a)

        for i in range(2):
            user_b = User(
                id=f"user-tenant-b-{i}",
                tenant_id=tenant_b,
                email=f"userb{i}@example.com",
                username=f"userb{i}",
                full_name=f"Tenant B User {i}",
                hashed_password=get_password_hash("password"),
                is_active=True,
            )
            db_session.add(user_b)
        await db_session.commit()

        # Query as tenant A
        token_a = create_access_token(
            subject="admin-a",
            additional_claims={
                "username": "admina",
                "roles": ["admin"],
                "permissions": ["user:view"],
                "tenant_id": tenant_a,
            },
        )

        response = client.get(
            "/api/v1/users",
            headers={"Authorization": f"Bearer {token_a}"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total"] == 3

        # Query as tenant B
        token_b = create_access_token(
            subject="admin-b",
            additional_claims={
                "username": "adminb",
                "roles": ["admin"],
                "permissions": ["user:view"],
                "tenant_id": tenant_b,
            },
        )

        response = client.get(
            "/api/v1/users",
            headers={"Authorization": f"Bearer {token_b}"},
        )

        data = response.json()
        assert data["total"] == 2
