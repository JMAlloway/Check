"""
Integration tests for policy endpoints.

Tests cover:
- Policy CRUD operations
- Policy version management
- Policy activation
- Policy rule evaluation
- Multi-tenant isolation
"""

import pytest
from datetime import datetime, timezone, timedelta
from fastapi import status

from app.core.security import create_access_token
from app.models.policy import Policy, PolicyStatus, PolicyVersion, PolicyRule


@pytest.fixture
def policy_admin_token(test_tenant_id):
    """Create a token with policy admin permissions."""
    return create_access_token(
        subject="policy-admin",
        additional_claims={
            "username": "policyadmin",
            "roles": ["admin"],
            "permissions": [
                "policy:view",
                "policy:create",
                "policy:update",
                "policy:delete",
                "policy:activate",
            ],
            "tenant_id": test_tenant_id,
        },
    )


@pytest.fixture
def policy_headers(policy_admin_token):
    """Auth headers for policy admin."""
    return {"Authorization": f"Bearer {policy_admin_token}"}


class TestListPolicies:
    """Tests for listing policies."""

    @pytest.mark.asyncio
    async def test_list_policies_empty(self, client, policy_headers):
        """Test listing policies when none exist."""
        response = client.get(
            "/api/v1/policies",
            headers=policy_headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data == []

    @pytest.mark.asyncio
    async def test_list_policies_with_data(self, client, db_session, test_tenant_id, policy_headers):
        """Test listing policies with data."""
        # Create test policies
        for i in range(3):
            policy = Policy(
                id=f"policy-list-{i}",
                tenant_id=test_tenant_id,
                name=f"Test Policy {i}",
                description=f"Description for policy {i}",
                status=PolicyStatus.DRAFT,
            )
            db_session.add(policy)
        await db_session.commit()

        response = client.get(
            "/api/v1/policies",
            headers=policy_headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 3

    @pytest.mark.asyncio
    async def test_list_policies_filter_by_status(self, client, db_session, test_tenant_id, policy_headers):
        """Test filtering policies by status."""
        # Create policies with different statuses
        policy_draft = Policy(
            id="policy-draft",
            tenant_id=test_tenant_id,
            name="Draft Policy",
            status=PolicyStatus.DRAFT,
        )
        policy_active = Policy(
            id="policy-active",
            tenant_id=test_tenant_id,
            name="Active Policy",
            status=PolicyStatus.ACTIVE,
        )
        db_session.add(policy_draft)
        db_session.add(policy_active)
        await db_session.commit()

        response = client.get(
            "/api/v1/policies?status_filter=active",
            headers=policy_headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 1
        assert data[0]["status"] == "active"


class TestCreatePolicy:
    """Tests for creating policies."""

    @pytest.mark.asyncio
    async def test_create_policy_basic(self, client, policy_headers):
        """Test creating a basic policy."""
        response = client.post(
            "/api/v1/policies",
            headers=policy_headers,
            json={
                "name": "New Test Policy",
                "description": "A policy for testing",
            },
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["name"] == "New Test Policy"
        assert data["status"] == "draft"

    @pytest.mark.asyncio
    async def test_create_policy_with_initial_version(self, client, policy_headers):
        """Test creating a policy with initial version and rules."""
        response = client.post(
            "/api/v1/policies",
            headers=policy_headers,
            json={
                "name": "Policy with Rules",
                "description": "Has initial rules",
                "initial_version": {
                    "effective_date": datetime.now(timezone.utc).isoformat(),
                    "change_notes": "Initial version",
                    "rules": [
                        {
                            "name": "High Amount Rule",
                            "description": "Flag high value checks",
                            "rule_type": "threshold",
                            "priority": 1,
                            "is_enabled": True,
                            "conditions": [
                                {"field": "amount", "operator": "greater_than", "value": "10000"}
                            ],
                            "actions": [
                                {"action_type": "flag", "params": {"flag": "high_value"}}
                            ],
                            "amount_threshold": 10000,
                        }
                    ],
                },
            },
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["name"] == "Policy with Rules"


class TestGetPolicy:
    """Tests for getting a specific policy."""

    @pytest.mark.asyncio
    async def test_get_policy_success(self, client, db_session, test_tenant_id, policy_headers):
        """Test getting a policy by ID."""
        policy = Policy(
            id="policy-get-1",
            tenant_id=test_tenant_id,
            name="Get Test Policy",
            description="Policy to retrieve",
            status=PolicyStatus.DRAFT,
        )
        db_session.add(policy)
        await db_session.commit()

        response = client.get(
            "/api/v1/policies/policy-get-1",
            headers=policy_headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["id"] == "policy-get-1"
        assert data["name"] == "Get Test Policy"

    @pytest.mark.asyncio
    async def test_get_policy_not_found(self, client, policy_headers):
        """Test getting a non-existent policy."""
        response = client.get(
            "/api/v1/policies/nonexistent",
            headers=policy_headers,
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_get_policy_wrong_tenant(self, client, db_session, policy_headers):
        """Test that policies from other tenants are not accessible."""
        policy = Policy(
            id="policy-other-tenant",
            tenant_id="other-tenant-id",
            name="Other Tenant Policy",
            status=PolicyStatus.ACTIVE,
        )
        db_session.add(policy)
        await db_session.commit()

        response = client.get(
            "/api/v1/policies/policy-other-tenant",
            headers=policy_headers,
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestUpdatePolicy:
    """Tests for updating policies."""

    @pytest.mark.asyncio
    async def test_update_policy_name(self, client, db_session, test_tenant_id, policy_headers):
        """Test updating policy name."""
        policy = Policy(
            id="policy-update-1",
            tenant_id=test_tenant_id,
            name="Original Name",
            status=PolicyStatus.DRAFT,
        )
        db_session.add(policy)
        await db_session.commit()

        response = client.put(
            "/api/v1/policies/policy-update-1",
            headers=policy_headers,
            json={"name": "Updated Name"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["name"] == "Updated Name"

    @pytest.mark.asyncio
    async def test_update_policy_status(self, client, db_session, test_tenant_id, policy_headers):
        """Test updating policy status."""
        policy = Policy(
            id="policy-update-status",
            tenant_id=test_tenant_id,
            name="Status Test",
            status=PolicyStatus.DRAFT,
        )
        db_session.add(policy)
        await db_session.commit()

        response = client.put(
            "/api/v1/policies/policy-update-status",
            headers=policy_headers,
            json={"status": "inactive"},
        )

        assert response.status_code == status.HTTP_200_OK


class TestPolicyVersions:
    """Tests for policy version management."""

    @pytest.mark.asyncio
    async def test_create_policy_version(self, client, db_session, test_tenant_id, policy_headers):
        """Test creating a new policy version."""
        policy = Policy(
            id="policy-version-1",
            tenant_id=test_tenant_id,
            name="Versioned Policy",
            status=PolicyStatus.DRAFT,
        )
        db_session.add(policy)

        version = PolicyVersion(
            id="version-1",
            policy_id="policy-version-1",
            version_number=1,
            effective_date=datetime.now(timezone.utc),
            is_current=True,
        )
        db_session.add(version)
        await db_session.commit()

        response = client.post(
            "/api/v1/policies/policy-version-1/versions",
            headers=policy_headers,
            json={
                "effective_date": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
                "change_notes": "New version with updates",
                "rules": [],
            },
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["version_number"] == 2


class TestActivatePolicy:
    """Tests for policy activation."""

    @pytest.mark.asyncio
    async def test_activate_policy(self, client, db_session, test_tenant_id, policy_headers):
        """Test activating a policy."""
        policy = Policy(
            id="policy-activate",
            tenant_id=test_tenant_id,
            name="Policy to Activate",
            status=PolicyStatus.DRAFT,
        )
        db_session.add(policy)

        version = PolicyVersion(
            id="version-activate",
            policy_id="policy-activate",
            version_number=1,
            effective_date=datetime.now(timezone.utc),
            is_current=False,
        )
        db_session.add(version)
        await db_session.commit()

        response = client.post(
            "/api/v1/policies/policy-activate/activate",
            headers=policy_headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "activated" in data["message"].lower()

    @pytest.mark.asyncio
    async def test_activate_specific_version(self, client, db_session, test_tenant_id, policy_headers):
        """Test activating a specific policy version."""
        policy = Policy(
            id="policy-activate-version",
            tenant_id=test_tenant_id,
            name="Multi-version Policy",
            status=PolicyStatus.DRAFT,
        )
        db_session.add(policy)

        for i in range(3):
            version = PolicyVersion(
                id=f"version-av-{i}",
                policy_id="policy-activate-version",
                version_number=i + 1,
                effective_date=datetime.now(timezone.utc),
                is_current=False,
            )
            db_session.add(version)
        await db_session.commit()

        response = client.post(
            "/api/v1/policies/policy-activate-version/activate?version_id=version-av-1",
            headers=policy_headers,
        )

        assert response.status_code == status.HTTP_200_OK


class TestDeletePolicy:
    """Tests for deleting policies."""

    @pytest.mark.asyncio
    async def test_delete_draft_policy(self, client, db_session, test_tenant_id, policy_headers):
        """Test deleting a draft policy."""
        policy = Policy(
            id="policy-delete",
            tenant_id=test_tenant_id,
            name="Policy to Delete",
            status=PolicyStatus.DRAFT,
        )
        db_session.add(policy)
        await db_session.commit()

        response = client.delete(
            "/api/v1/policies/policy-delete",
            headers=policy_headers,
        )

        assert response.status_code == status.HTTP_200_OK

    @pytest.mark.asyncio
    async def test_delete_active_policy_blocked(self, client, db_session, test_tenant_id, policy_headers):
        """Test that active policies cannot be deleted without force."""
        policy = Policy(
            id="policy-delete-active",
            tenant_id=test_tenant_id,
            name="Active Policy",
            status=PolicyStatus.ACTIVE,
        )
        db_session.add(policy)
        await db_session.commit()

        response = client.delete(
            "/api/v1/policies/policy-delete-active",
            headers=policy_headers,
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.asyncio
    async def test_delete_active_policy_forced(self, client, db_session, test_tenant_id, policy_headers):
        """Test force deleting an active policy."""
        policy = Policy(
            id="policy-force-delete",
            tenant_id=test_tenant_id,
            name="Force Delete Policy",
            status=PolicyStatus.ACTIVE,
        )
        db_session.add(policy)
        await db_session.commit()

        response = client.delete(
            "/api/v1/policies/policy-force-delete?force=true",
            headers=policy_headers,
        )

        assert response.status_code == status.HTTP_200_OK

    @pytest.mark.asyncio
    async def test_delete_default_policy_blocked(self, client, db_session, test_tenant_id, policy_headers):
        """Test that default policies cannot be deleted."""
        policy = Policy(
            id="policy-default",
            tenant_id=test_tenant_id,
            name="Default Policy",
            status=PolicyStatus.ACTIVE,
            is_default=True,
        )
        db_session.add(policy)
        await db_session.commit()

        response = client.delete(
            "/api/v1/policies/policy-default?force=true",
            headers=policy_headers,
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "default" in response.json()["detail"].lower()


class TestMultiTenantPolicies:
    """Tests for multi-tenant policy isolation."""

    @pytest.mark.asyncio
    async def test_policies_isolated_by_tenant(self, client, db_session):
        """Test that policies are isolated between tenants."""
        tenant_a = "policy-tenant-a"
        tenant_b = "policy-tenant-b"

        # Create policies for each tenant
        for i in range(2):
            policy_a = Policy(
                id=f"policy-tenant-a-{i}",
                tenant_id=tenant_a,
                name=f"Tenant A Policy {i}",
                status=PolicyStatus.ACTIVE,
            )
            db_session.add(policy_a)

        policy_b = Policy(
            id="policy-tenant-b-1",
            tenant_id=tenant_b,
            name="Tenant B Policy",
            status=PolicyStatus.ACTIVE,
        )
        db_session.add(policy_b)
        await db_session.commit()

        # Query as tenant A
        token_a = create_access_token(
            subject="user-a",
            additional_claims={
                "username": "usera",
                "roles": ["admin"],
                "permissions": ["policy:view"],
                "tenant_id": tenant_a,
            },
        )

        response = client.get(
            "/api/v1/policies",
            headers={"Authorization": f"Bearer {token_a}"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 2

        # Query as tenant B
        token_b = create_access_token(
            subject="user-b",
            additional_claims={
                "username": "userb",
                "roles": ["admin"],
                "permissions": ["policy:view"],
                "tenant_id": tenant_b,
            },
        )

        response = client.get(
            "/api/v1/policies",
            headers={"Authorization": f"Bearer {token_b}"},
        )

        data = response.json()
        assert len(data) == 1
