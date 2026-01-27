"""
Integration tests for check item endpoints.

Tests cover:
- Listing check items with filtering
- Getting check item details
- Check item assignment
- Status updates
- Queue navigation (adjacent items)
- Multi-tenant isolation
"""

import pytest
from datetime import datetime, timezone
from decimal import Decimal
from fastapi import status

from app.core.security import create_access_token
from app.models.check import CheckItem, CheckStatus, RiskLevel, ItemType
from app.models.user import User, Role, Permission


@pytest.fixture
def reviewer_token(test_tenant_id, test_user_id):
    """Create a token with reviewer permissions."""
    return create_access_token(
        subject=test_user_id,
        additional_claims={
            "username": "reviewer",
            "roles": ["reviewer"],
            "permissions": ["check_item:view", "check_item:review", "check_item:assign"],
            "tenant_id": test_tenant_id,
        },
    )


@pytest.fixture
def reviewer_headers(reviewer_token):
    """Auth headers for reviewer."""
    return {"Authorization": f"Bearer {reviewer_token}"}


class TestListCheckItems:
    """Tests for listing check items."""

    @pytest.mark.asyncio
    async def test_list_items_empty(self, client, reviewer_headers):
        """Test listing items when none exist."""
        response = client.get(
            "/api/v1/checks",
            headers=reviewer_headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0

    @pytest.mark.asyncio
    async def test_list_items_with_data(self, client, db_session, test_tenant_id, reviewer_headers):
        """Test listing items with data."""
        # Create test check items
        for i in range(5):
            item = CheckItem(
                id=f"check-item-{i}",
                tenant_id=test_tenant_id,
                external_item_id=f"EXT-{i}",
                account_id=f"acct-{i}",
                amount=Decimal(str(1000 + i * 100)),
                status=CheckStatus.NEW,
                risk_level=RiskLevel.MEDIUM,
                item_type=ItemType.ON_US,
                presented_date=datetime.now(timezone.utc),
            )
            db_session.add(item)
        await db_session.commit()

        response = client.get(
            "/api/v1/checks",
            headers=reviewer_headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total"] == 5
        assert len(data["items"]) == 5

    @pytest.mark.asyncio
    async def test_list_items_filter_by_status(self, client, db_session, test_tenant_id, reviewer_headers):
        """Test filtering items by status."""
        # Create items with different statuses
        statuses = [CheckStatus.NEW, CheckStatus.IN_REVIEW, CheckStatus.APPROVED]
        for i, s in enumerate(statuses):
            item = CheckItem(
                id=f"check-status-{i}",
                tenant_id=test_tenant_id,
                external_item_id=f"EXT-S-{i}",
                account_id=f"acct-s-{i}",
                amount=Decimal("1000"),
                status=s,
                risk_level=RiskLevel.LOW,
                item_type=ItemType.ON_US,
                presented_date=datetime.now(timezone.utc),
            )
            db_session.add(item)
        await db_session.commit()

        response = client.get(
            "/api/v1/checks?status=new",
            headers=reviewer_headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["status"] == "new"

    @pytest.mark.asyncio
    async def test_list_items_filter_by_risk_level(self, client, db_session, test_tenant_id, reviewer_headers):
        """Test filtering items by risk level."""
        risk_levels = [RiskLevel.LOW, RiskLevel.HIGH, RiskLevel.CRITICAL]
        for i, r in enumerate(risk_levels):
            item = CheckItem(
                id=f"check-risk-{i}",
                tenant_id=test_tenant_id,
                external_item_id=f"EXT-R-{i}",
                account_id=f"acct-r-{i}",
                amount=Decimal("1000"),
                status=CheckStatus.NEW,
                risk_level=r,
                item_type=ItemType.ON_US,
                presented_date=datetime.now(timezone.utc),
            )
            db_session.add(item)
        await db_session.commit()

        response = client.get(
            "/api/v1/checks?risk_level=critical",
            headers=reviewer_headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total"] == 1

    @pytest.mark.asyncio
    async def test_list_items_pagination(self, client, db_session, test_tenant_id, reviewer_headers):
        """Test pagination of check items."""
        for i in range(25):
            item = CheckItem(
                id=f"check-page-{i}",
                tenant_id=test_tenant_id,
                external_item_id=f"EXT-P-{i}",
                account_id=f"acct-p-{i}",
                amount=Decimal("1000"),
                status=CheckStatus.NEW,
                risk_level=RiskLevel.LOW,
                item_type=ItemType.ON_US,
                presented_date=datetime.now(timezone.utc),
            )
            db_session.add(item)
        await db_session.commit()

        # Get first page
        response = client.get(
            "/api/v1/checks?page=1&page_size=10",
            headers=reviewer_headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["items"]) == 10
        assert data["total"] == 25
        assert data["total_pages"] == 3
        assert data["has_next"] is True
        assert data["has_previous"] is False

        # Get second page
        response = client.get(
            "/api/v1/checks?page=2&page_size=10",
            headers=reviewer_headers,
        )

        data = response.json()
        assert data["has_previous"] is True


class TestGetCheckItem:
    """Tests for getting a specific check item."""

    @pytest.mark.asyncio
    async def test_get_item_success(self, client, db_session, test_tenant_id, reviewer_headers):
        """Test getting a check item by ID."""
        item = CheckItem(
            id="check-get-1",
            tenant_id=test_tenant_id,
            external_item_id="EXT-GET-1",
            account_id="acct-get-1",
            amount=Decimal("5000.00"),
            status=CheckStatus.NEW,
            risk_level=RiskLevel.MEDIUM,
            item_type=ItemType.ON_US,
            presented_date=datetime.now(timezone.utc),
            payee_name="Test Payee",
            check_number="1001",
        )
        db_session.add(item)
        await db_session.commit()

        response = client.get(
            "/api/v1/checks/check-get-1",
            headers=reviewer_headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["id"] == "check-get-1"
        assert data["amount"] == "5000.00"
        assert data["payee_name"] == "Test Payee"

    @pytest.mark.asyncio
    async def test_get_item_not_found(self, client, reviewer_headers):
        """Test getting non-existent check item."""
        response = client.get(
            "/api/v1/checks/nonexistent-id",
            headers=reviewer_headers,
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_get_item_wrong_tenant(self, client, db_session, reviewer_headers):
        """Test that items from other tenants are not accessible."""
        item = CheckItem(
            id="check-other-tenant",
            tenant_id="other-tenant-id",
            external_item_id="EXT-OTHER",
            account_id="acct-other",
            amount=Decimal("1000"),
            status=CheckStatus.NEW,
            risk_level=RiskLevel.LOW,
            item_type=ItemType.ON_US,
            presented_date=datetime.now(timezone.utc),
        )
        db_session.add(item)
        await db_session.commit()

        response = client.get(
            "/api/v1/checks/check-other-tenant",
            headers=reviewer_headers,
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestCheckItemAssignment:
    """Tests for check item assignment."""

    @pytest.mark.asyncio
    async def test_assign_reviewer(self, client, db_session, test_tenant_id, reviewer_headers):
        """Test assigning a reviewer to a check item."""
        item = CheckItem(
            id="check-assign-1",
            tenant_id=test_tenant_id,
            external_item_id="EXT-ASSIGN-1",
            account_id="acct-assign-1",
            amount=Decimal("1000"),
            status=CheckStatus.NEW,
            risk_level=RiskLevel.LOW,
            item_type=ItemType.ON_US,
            presented_date=datetime.now(timezone.utc),
        )
        db_session.add(item)
        await db_session.commit()

        response = client.post(
            "/api/v1/checks/check-assign-1/assign?reviewer_id=reviewer-123",
            headers=reviewer_headers,
        )

        assert response.status_code == status.HTTP_200_OK

    @pytest.mark.asyncio
    async def test_assign_nonexistent_item(self, client, reviewer_headers):
        """Test assigning to non-existent item."""
        response = client.post(
            "/api/v1/checks/nonexistent/assign?reviewer_id=reviewer-123",
            headers=reviewer_headers,
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestCheckStatusUpdate:
    """Tests for check status updates."""

    @pytest.mark.asyncio
    async def test_update_status(self, client, db_session, test_tenant_id):
        """Test updating check item status."""
        item = CheckItem(
            id="check-status-update",
            tenant_id=test_tenant_id,
            external_item_id="EXT-STATUS",
            account_id="acct-status",
            amount=Decimal("1000"),
            status=CheckStatus.NEW,
            risk_level=RiskLevel.LOW,
            item_type=ItemType.ON_US,
            presented_date=datetime.now(timezone.utc),
        )
        db_session.add(item)
        await db_session.commit()

        # Create token with update permission
        token = create_access_token(
            subject="user-update",
            additional_claims={
                "username": "updater",
                "roles": ["supervisor"],
                "permissions": ["check_item:view", "check_item:update"],
                "tenant_id": test_tenant_id,
            },
        )

        response = client.post(
            "/api/v1/checks/check-status-update/status?status=in_review",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == status.HTTP_200_OK


class TestMyQueue:
    """Tests for getting user's assigned queue."""

    @pytest.mark.asyncio
    async def test_my_queue_empty(self, client, reviewer_headers):
        """Test getting empty queue."""
        response = client.get(
            "/api/v1/checks/my-queue",
            headers=reviewer_headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["items"] == []

    @pytest.mark.asyncio
    async def test_my_queue_with_assigned_items(
        self, client, db_session, test_tenant_id, test_user_id, reviewer_headers
    ):
        """Test getting queue with assigned items."""
        item = CheckItem(
            id="check-my-queue",
            tenant_id=test_tenant_id,
            external_item_id="EXT-MY-Q",
            account_id="acct-my-q",
            amount=Decimal("1000"),
            status=CheckStatus.NEW,
            risk_level=RiskLevel.LOW,
            item_type=ItemType.ON_US,
            presented_date=datetime.now(timezone.utc),
            assigned_reviewer_id=test_user_id,
        )
        db_session.add(item)
        await db_session.commit()

        response = client.get(
            "/api/v1/checks/my-queue",
            headers=reviewer_headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total"] >= 1


class TestAdjacentItems:
    """Tests for getting adjacent items in queue."""

    @pytest.mark.asyncio
    async def test_get_adjacent_items(self, client, db_session, test_tenant_id, reviewer_headers):
        """Test getting previous and next items."""
        # Create ordered items
        for i in range(3):
            item = CheckItem(
                id=f"check-adj-{i}",
                tenant_id=test_tenant_id,
                external_item_id=f"EXT-ADJ-{i}",
                account_id=f"acct-adj-{i}",
                amount=Decimal("1000"),
                status=CheckStatus.NEW,
                risk_level=RiskLevel.MEDIUM,
                item_type=ItemType.ON_US,
                presented_date=datetime.now(timezone.utc),
            )
            db_session.add(item)
        await db_session.commit()

        response = client.get(
            "/api/v1/checks/check-adj-1/adjacent",
            headers=reviewer_headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "previous_id" in data or "next_id" in data


class TestMultiTenantIsolation:
    """Tests for multi-tenant check item isolation."""

    @pytest.mark.asyncio
    async def test_items_filtered_by_tenant(self, client, db_session):
        """Test that items are properly filtered by tenant."""
        tenant_a = "tenant-check-a"
        tenant_b = "tenant-check-b"

        # Create items for tenant A
        for i in range(3):
            item = CheckItem(
                id=f"check-tenant-a-{i}",
                tenant_id=tenant_a,
                external_item_id=f"EXT-A-{i}",
                account_id=f"acct-a-{i}",
                amount=Decimal("1000"),
                status=CheckStatus.NEW,
                risk_level=RiskLevel.LOW,
                item_type=ItemType.ON_US,
                presented_date=datetime.now(timezone.utc),
            )
            db_session.add(item)

        # Create items for tenant B
        for i in range(2):
            item = CheckItem(
                id=f"check-tenant-b-{i}",
                tenant_id=tenant_b,
                external_item_id=f"EXT-B-{i}",
                account_id=f"acct-b-{i}",
                amount=Decimal("1000"),
                status=CheckStatus.NEW,
                risk_level=RiskLevel.LOW,
                item_type=ItemType.ON_US,
                presented_date=datetime.now(timezone.utc),
            )
            db_session.add(item)

        await db_session.commit()

        # Query as tenant A
        token_a = create_access_token(
            subject="user-a",
            additional_claims={
                "username": "usera",
                "roles": ["reviewer"],
                "permissions": ["check_item:view"],
                "tenant_id": tenant_a,
            },
        )

        response = client.get(
            "/api/v1/checks",
            headers={"Authorization": f"Bearer {token_a}"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total"] == 3

        # Query as tenant B
        token_b = create_access_token(
            subject="user-b",
            additional_claims={
                "username": "userb",
                "roles": ["reviewer"],
                "permissions": ["check_item:view"],
                "tenant_id": tenant_b,
            },
        )

        response = client.get(
            "/api/v1/checks",
            headers={"Authorization": f"Bearer {token_b}"},
        )

        data = response.json()
        assert data["total"] == 2
