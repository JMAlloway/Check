"""
Integration tests for queue management endpoints.

Tests cover:
- Queue CRUD operations
- Queue statistics
- Queue assignments
- Multi-tenant isolation
"""

from datetime import datetime, timezone
from decimal import Decimal

import pytest
from app.core.security import create_access_token
from app.models.check import CheckItem, CheckStatus, ItemType, RiskLevel
from app.models.queue import Queue, QueueAssignment, QueueType
from app.models.user import User
from fastapi import status


@pytest.fixture
def queue_admin_token(test_tenant_id):
    """Create a token with queue admin permissions."""
    return create_access_token(
        subject="queue-admin",
        additional_claims={
            "username": "queueadmin",
            "roles": ["admin"],
            "permissions": [
                "queue:view",
                "queue:create",
                "queue:update",
                "queue:assign",
            ],
            "tenant_id": test_tenant_id,
        },
    )


@pytest.fixture
def queue_headers(queue_admin_token):
    """Auth headers for queue admin."""
    return {"Authorization": f"Bearer {queue_admin_token}"}


class TestListQueues:
    """Tests for listing queues."""

    @pytest.mark.asyncio
    async def test_list_queues_empty(self, client, queue_headers):
        """Test listing queues when none exist."""
        response = client.get(
            "/api/v1/queues",
            headers=queue_headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data == []

    @pytest.mark.asyncio
    async def test_list_queues_with_data(self, client, db_session, test_tenant_id, queue_headers):
        """Test listing queues with data."""
        for i in range(3):
            queue = Queue(
                id=f"queue-list-{i}",
                tenant_id=test_tenant_id,
                name=f"Queue {i}",
                description=f"Test queue {i}",
                queue_type=QueueType.STANDARD,
                is_active=True,
            )
            db_session.add(queue)
        await db_session.commit()

        response = client.get(
            "/api/v1/queues",
            headers=queue_headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 3

    @pytest.mark.asyncio
    async def test_list_queues_exclude_inactive(
        self, client, db_session, test_tenant_id, queue_headers
    ):
        """Test that inactive queues are excluded by default."""
        queue_active = Queue(
            id="queue-active",
            tenant_id=test_tenant_id,
            name="Active Queue",
            queue_type=QueueType.STANDARD,
            is_active=True,
        )
        queue_inactive = Queue(
            id="queue-inactive",
            tenant_id=test_tenant_id,
            name="Inactive Queue",
            queue_type=QueueType.STANDARD,
            is_active=False,
        )
        db_session.add(queue_active)
        db_session.add(queue_inactive)
        await db_session.commit()

        response = client.get(
            "/api/v1/queues",
            headers=queue_headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "Active Queue"

    @pytest.mark.asyncio
    async def test_list_queues_include_inactive(
        self, client, db_session, test_tenant_id, queue_headers
    ):
        """Test including inactive queues."""
        queue_active = Queue(
            id="queue-active-2",
            tenant_id=test_tenant_id,
            name="Active Queue",
            queue_type=QueueType.STANDARD,
            is_active=True,
        )
        queue_inactive = Queue(
            id="queue-inactive-2",
            tenant_id=test_tenant_id,
            name="Inactive Queue",
            queue_type=QueueType.STANDARD,
            is_active=False,
        )
        db_session.add(queue_active)
        db_session.add(queue_inactive)
        await db_session.commit()

        response = client.get(
            "/api/v1/queues?include_inactive=true",
            headers=queue_headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 2


class TestCreateQueue:
    """Tests for creating queues."""

    @pytest.mark.asyncio
    async def test_create_queue_basic(self, client, queue_headers):
        """Test creating a basic queue."""
        response = client.post(
            "/api/v1/queues",
            headers=queue_headers,
            json={
                "name": "New Queue",
                "description": "A new test queue",
                "queue_type": "standard",
                "sla_hours": 24,
            },
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["name"] == "New Queue"
        assert data["sla_hours"] == 24

    @pytest.mark.asyncio
    async def test_create_queue_high_priority(self, client, queue_headers):
        """Test creating a high priority queue."""
        response = client.post(
            "/api/v1/queues",
            headers=queue_headers,
            json={
                "name": "High Priority Queue",
                "description": "Urgent items",
                "queue_type": "high_priority",
                "sla_hours": 4,
                "warning_threshold_minutes": 180,
            },
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["queue_type"] == "high_priority"


class TestGetQueue:
    """Tests for getting a specific queue."""

    @pytest.mark.asyncio
    async def test_get_queue_success(self, client, db_session, test_tenant_id, queue_headers):
        """Test getting a queue by ID."""
        queue = Queue(
            id="queue-get-1",
            tenant_id=test_tenant_id,
            name="Get Test Queue",
            description="Queue to retrieve",
            queue_type=QueueType.STANDARD,
            sla_hours=24,
            is_active=True,
        )
        db_session.add(queue)
        await db_session.commit()

        response = client.get(
            "/api/v1/queues/queue-get-1",
            headers=queue_headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["id"] == "queue-get-1"
        assert data["name"] == "Get Test Queue"

    @pytest.mark.asyncio
    async def test_get_queue_not_found(self, client, queue_headers):
        """Test getting a non-existent queue."""
        response = client.get(
            "/api/v1/queues/nonexistent",
            headers=queue_headers,
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_get_queue_wrong_tenant(self, client, db_session, queue_headers):
        """Test that queues from other tenants are not accessible."""
        queue = Queue(
            id="queue-other-tenant",
            tenant_id="other-tenant-id",
            name="Other Tenant Queue",
            queue_type=QueueType.STANDARD,
            is_active=True,
        )
        db_session.add(queue)
        await db_session.commit()

        response = client.get(
            "/api/v1/queues/queue-other-tenant",
            headers=queue_headers,
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestUpdateQueue:
    """Tests for updating queues."""

    @pytest.mark.asyncio
    async def test_update_queue_name(self, client, db_session, test_tenant_id, queue_headers):
        """Test updating queue name."""
        queue = Queue(
            id="queue-update-1",
            tenant_id=test_tenant_id,
            name="Original Name",
            queue_type=QueueType.STANDARD,
            is_active=True,
        )
        db_session.add(queue)
        await db_session.commit()

        response = client.patch(
            "/api/v1/queues/queue-update-1",
            headers=queue_headers,
            json={"name": "Updated Name"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["name"] == "Updated Name"

    @pytest.mark.asyncio
    async def test_update_queue_deactivate(self, client, db_session, test_tenant_id, queue_headers):
        """Test deactivating a queue."""
        queue = Queue(
            id="queue-deactivate",
            tenant_id=test_tenant_id,
            name="Deactivate Queue",
            queue_type=QueueType.STANDARD,
            is_active=True,
        )
        db_session.add(queue)
        await db_session.commit()

        response = client.patch(
            "/api/v1/queues/queue-deactivate",
            headers=queue_headers,
            json={"is_active": False},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["is_active"] is False


class TestQueueStats:
    """Tests for queue statistics."""

    @pytest.mark.asyncio
    async def test_get_queue_stats(self, client, db_session, test_tenant_id, queue_headers):
        """Test getting queue statistics."""
        queue = Queue(
            id="queue-stats",
            tenant_id=test_tenant_id,
            name="Stats Queue",
            queue_type=QueueType.STANDARD,
            is_active=True,
        )
        db_session.add(queue)

        # Create check items in this queue
        for i in range(5):
            item = CheckItem(
                id=f"check-stats-{i}",
                tenant_id=test_tenant_id,
                external_item_id=f"EXT-STATS-{i}",
                account_id=f"acct-stats-{i}",
                amount=Decimal("1000"),
                status=CheckStatus.NEW,
                risk_level=RiskLevel.MEDIUM,
                item_type=ItemType.ON_US,
                presented_date=datetime.now(timezone.utc),
                queue_id="queue-stats",
            )
            db_session.add(item)
        await db_session.commit()

        response = client.get(
            "/api/v1/queues/queue-stats/stats",
            headers=queue_headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["queue_id"] == "queue-stats"
        assert data["total_items"] == 5

    @pytest.mark.asyncio
    async def test_get_queue_stats_empty(self, client, db_session, test_tenant_id, queue_headers):
        """Test getting stats for empty queue."""
        queue = Queue(
            id="queue-empty-stats",
            tenant_id=test_tenant_id,
            name="Empty Queue",
            queue_type=QueueType.STANDARD,
            is_active=True,
        )
        db_session.add(queue)
        await db_session.commit()

        response = client.get(
            "/api/v1/queues/queue-empty-stats/stats",
            headers=queue_headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total_items"] == 0


class TestQueueAssignments:
    """Tests for queue assignments."""

    @pytest.mark.asyncio
    async def test_get_queue_assignments(self, client, db_session, test_tenant_id, queue_headers):
        """Test getting queue assignments."""
        queue = Queue(
            id="queue-assignments",
            tenant_id=test_tenant_id,
            name="Assignments Queue",
            queue_type=QueueType.STANDARD,
            is_active=True,
        )
        db_session.add(queue)

        user = User(
            id="assigned-user",
            tenant_id=test_tenant_id,
            email="assigned@example.com",
            username="assigned",
            full_name="Assigned User",
            hashed_password="hashed",
            is_active=True,
        )
        db_session.add(user)

        assignment = QueueAssignment(
            id="assignment-1",
            queue_id="queue-assignments",
            user_id="assigned-user",
            can_review=True,
            can_approve=False,
            is_active=True,
            assigned_at=datetime.now(timezone.utc),
            assigned_by_id="admin-user",
        )
        db_session.add(assignment)
        await db_session.commit()

        response = client.get(
            "/api/v1/queues/queue-assignments/assignments",
            headers=queue_headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 1
        assert data[0]["can_review"] is True

    @pytest.mark.asyncio
    async def test_create_queue_assignment(self, client, db_session, test_tenant_id, queue_headers):
        """Test creating a queue assignment."""
        queue = Queue(
            id="queue-new-assign",
            tenant_id=test_tenant_id,
            name="New Assignment Queue",
            queue_type=QueueType.STANDARD,
            is_active=True,
        )
        db_session.add(queue)

        user = User(
            id="new-assigned-user",
            tenant_id=test_tenant_id,
            email="newassigned@example.com",
            username="newassigned",
            full_name="New Assigned User",
            hashed_password="hashed",
            is_active=True,
        )
        db_session.add(user)
        await db_session.commit()

        response = client.post(
            "/api/v1/queues/queue-new-assign/assignments",
            headers=queue_headers,
            json={
                "user_id": "new-assigned-user",
                "can_review": True,
                "can_approve": True,
                "max_concurrent_items": 10,
            },
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["user_id"] == "new-assigned-user"
        assert data["can_review"] is True
        assert data["can_approve"] is True

    @pytest.mark.asyncio
    async def test_update_existing_assignment(
        self, client, db_session, test_tenant_id, queue_headers
    ):
        """Test updating an existing queue assignment."""
        queue = Queue(
            id="queue-update-assign",
            tenant_id=test_tenant_id,
            name="Update Assignment Queue",
            queue_type=QueueType.STANDARD,
            is_active=True,
        )
        db_session.add(queue)

        user = User(
            id="update-assigned-user",
            tenant_id=test_tenant_id,
            email="updateassigned@example.com",
            username="updateassigned",
            full_name="Update Assigned User",
            hashed_password="hashed",
            is_active=True,
        )
        db_session.add(user)

        assignment = QueueAssignment(
            id="assignment-update",
            queue_id="queue-update-assign",
            user_id="update-assigned-user",
            can_review=True,
            can_approve=False,
            is_active=True,
            assigned_at=datetime.now(timezone.utc),
            assigned_by_id="admin-user",
        )
        db_session.add(assignment)
        await db_session.commit()

        # Update assignment to add approve permission
        response = client.post(
            "/api/v1/queues/queue-update-assign/assignments",
            headers=queue_headers,
            json={
                "user_id": "update-assigned-user",
                "can_review": True,
                "can_approve": True,
            },
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["can_approve"] is True


class TestMultiTenantQueues:
    """Tests for multi-tenant queue isolation."""

    @pytest.mark.asyncio
    async def test_queues_isolated_by_tenant(self, client, db_session):
        """Test that queues are isolated between tenants."""
        tenant_a = "queue-tenant-a"
        tenant_b = "queue-tenant-b"

        # Create queues for each tenant
        for i in range(3):
            queue_a = Queue(
                id=f"queue-tenant-a-{i}",
                tenant_id=tenant_a,
                name=f"Tenant A Queue {i}",
                queue_type=QueueType.STANDARD,
                is_active=True,
            )
            db_session.add(queue_a)

        queue_b = Queue(
            id="queue-tenant-b-1",
            tenant_id=tenant_b,
            name="Tenant B Queue",
            queue_type=QueueType.STANDARD,
            is_active=True,
        )
        db_session.add(queue_b)
        await db_session.commit()

        # Query as tenant A
        token_a = create_access_token(
            subject="admin-a",
            additional_claims={
                "username": "admina",
                "roles": ["admin"],
                "permissions": ["queue:view"],
                "tenant_id": tenant_a,
            },
        )

        response = client.get(
            "/api/v1/queues",
            headers={"Authorization": f"Bearer {token_a}"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 3

        # Query as tenant B
        token_b = create_access_token(
            subject="admin-b",
            additional_claims={
                "username": "adminb",
                "roles": ["admin"],
                "permissions": ["queue:view"],
                "tenant_id": tenant_b,
            },
        )

        response = client.get(
            "/api/v1/queues",
            headers={"Authorization": f"Bearer {token_b}"},
        )

        data = response.json()
        assert len(data) == 1
