"""
Integration tests for audit endpoints.

Tests cover:
- Searching audit logs
- Getting item audit trails
- Getting user activity
- Generating audit packets
- Multi-tenant isolation
"""

import pytest
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from fastapi import status

from app.core.security import create_access_token
from app.models.audit import AuditLog, AuditAction, ItemView
from app.models.check import CheckItem, CheckStatus, RiskLevel, ItemType
from app.models.user import User


@pytest.fixture
def auditor_token(test_tenant_id):
    """Create a token with auditor permissions."""
    return create_access_token(
        subject="auditor-id",
        additional_claims={
            "username": "auditor",
            "roles": ["auditor"],
            "permissions": ["audit:view", "audit:export"],
            "tenant_id": test_tenant_id,
        },
    )


@pytest.fixture
def auditor_headers(auditor_token):
    """Auth headers for auditor."""
    return {"Authorization": f"Bearer {auditor_token}"}


class TestSearchAuditLogs:
    """Tests for searching audit logs."""

    @pytest.mark.asyncio
    async def test_search_logs_empty(self, client, auditor_headers):
        """Test searching logs when none exist."""
        response = client.get(
            "/api/v1/audit/logs",
            headers=auditor_headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0

    @pytest.mark.asyncio
    async def test_search_logs_with_data(self, client, db_session, test_tenant_id, auditor_headers):
        """Test searching logs with data."""
        # Create test audit logs
        for i in range(5):
            log = AuditLog(
                id=f"audit-log-{i}",
                tenant_id=test_tenant_id,
                timestamp=datetime.now(timezone.utc),
                action=AuditAction.ITEM_VIEWED,
                resource_type="check_item",
                resource_id=f"item-{i}",
                user_id="user-1",
                username="testuser",
            )
            db_session.add(log)
        await db_session.commit()

        response = client.get(
            "/api/v1/audit/logs",
            headers=auditor_headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total"] == 5

    @pytest.mark.asyncio
    async def test_search_logs_filter_by_action(self, client, db_session, test_tenant_id, auditor_headers):
        """Test filtering logs by action."""
        # Create logs with different actions
        actions = [AuditAction.ITEM_VIEWED, AuditAction.DECISION_MADE, AuditAction.LOGIN]
        for i, action in enumerate(actions):
            log = AuditLog(
                id=f"audit-action-{i}",
                tenant_id=test_tenant_id,
                timestamp=datetime.now(timezone.utc),
                action=action,
                resource_type="check_item" if action != AuditAction.LOGIN else "user",
                user_id="user-1",
                username="testuser",
            )
            db_session.add(log)
        await db_session.commit()

        response = client.get(
            "/api/v1/audit/logs?action=decision_made",
            headers=auditor_headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total"] == 1

    @pytest.mark.asyncio
    async def test_search_logs_filter_by_resource(self, client, db_session, test_tenant_id, auditor_headers):
        """Test filtering logs by resource type."""
        log1 = AuditLog(
            id="audit-res-1",
            tenant_id=test_tenant_id,
            timestamp=datetime.now(timezone.utc),
            action=AuditAction.ITEM_VIEWED,
            resource_type="check_item",
            resource_id="item-1",
            user_id="user-1",
            username="testuser",
        )
        log2 = AuditLog(
            id="audit-res-2",
            tenant_id=test_tenant_id,
            timestamp=datetime.now(timezone.utc),
            action=AuditAction.POLICY_CREATED,
            resource_type="policy",
            resource_id="policy-1",
            user_id="user-1",
            username="testuser",
        )
        db_session.add(log1)
        db_session.add(log2)
        await db_session.commit()

        response = client.get(
            "/api/v1/audit/logs?resource_type=check_item",
            headers=auditor_headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total"] == 1

    @pytest.mark.asyncio
    async def test_search_logs_date_range(self, client, db_session, test_tenant_id, auditor_headers):
        """Test filtering logs by date range."""
        now = datetime.now(timezone.utc)
        yesterday = now - timedelta(days=1)
        last_week = now - timedelta(days=7)

        # Create log from yesterday
        log_yesterday = AuditLog(
            id="audit-yesterday",
            tenant_id=test_tenant_id,
            timestamp=yesterday,
            action=AuditAction.ITEM_VIEWED,
            resource_type="check_item",
            user_id="user-1",
            username="testuser",
        )
        # Create log from last week
        log_old = AuditLog(
            id="audit-old",
            tenant_id=test_tenant_id,
            timestamp=last_week,
            action=AuditAction.ITEM_VIEWED,
            resource_type="check_item",
            user_id="user-1",
            username="testuser",
        )
        db_session.add(log_yesterday)
        db_session.add(log_old)
        await db_session.commit()

        # Query for last 3 days
        date_from = (now - timedelta(days=3)).isoformat()
        response = client.get(
            f"/api/v1/audit/logs?date_from={date_from}",
            headers=auditor_headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total"] == 1

    @pytest.mark.asyncio
    async def test_search_logs_pagination(self, client, db_session, test_tenant_id, auditor_headers):
        """Test pagination of audit logs."""
        for i in range(75):
            log = AuditLog(
                id=f"audit-page-{i}",
                tenant_id=test_tenant_id,
                timestamp=datetime.now(timezone.utc),
                action=AuditAction.ITEM_VIEWED,
                resource_type="check_item",
                user_id="user-1",
                username="testuser",
            )
            db_session.add(log)
        await db_session.commit()

        response = client.get(
            "/api/v1/audit/logs?page=1&page_size=50",
            headers=auditor_headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["items"]) == 50
        assert data["total"] == 75
        assert data["has_next"] is True


class TestItemAuditTrail:
    """Tests for item audit trails."""

    @pytest.mark.asyncio
    async def test_get_item_audit_trail(self, client, db_session, test_tenant_id, auditor_headers):
        """Test getting audit trail for a check item."""
        # Create check item
        item = CheckItem(
            id="item-audit-trail",
            tenant_id=test_tenant_id,
            external_item_id="EXT-AUDIT",
            account_id="acct-audit",
            amount=Decimal("1000.00"),
            status=CheckStatus.APPROVED,
            risk_level=RiskLevel.LOW,
            item_type=ItemType.ON_US,
            presented_date=datetime.now(timezone.utc),
        )
        db_session.add(item)

        # Create audit logs for this item
        actions = [AuditAction.ITEM_VIEWED, AuditAction.DECISION_MADE, AuditAction.ITEM_STATUS_CHANGED]
        for i, action in enumerate(actions):
            log = AuditLog(
                id=f"audit-trail-{i}",
                tenant_id=test_tenant_id,
                timestamp=datetime.now(timezone.utc),
                action=action,
                resource_type="check_item",
                resource_id="item-audit-trail",
                user_id="user-1",
                username="reviewer",
                description=f"Action {i}",
            )
            db_session.add(log)
        await db_session.commit()

        response = client.get(
            "/api/v1/audit/items/item-audit-trail",
            headers=auditor_headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 3


class TestItemViews:
    """Tests for item view records."""

    @pytest.mark.asyncio
    async def test_get_item_views(self, client, db_session, test_tenant_id, auditor_headers):
        """Test getting view records for an item."""
        # Create item
        item = CheckItem(
            id="item-views",
            tenant_id=test_tenant_id,
            external_item_id="EXT-VIEWS",
            account_id="acct-views",
            amount=Decimal("1000.00"),
            status=CheckStatus.NEW,
            risk_level=RiskLevel.LOW,
            item_type=ItemType.ON_US,
            presented_date=datetime.now(timezone.utc),
        )
        db_session.add(item)

        # Create user
        user = User(
            id="viewer-user",
            tenant_id=test_tenant_id,
            email="viewer@example.com",
            username="viewer",
            full_name="Viewer User",
            hashed_password="hashed",
            is_active=True,
        )
        db_session.add(user)

        # Create view records
        for i in range(3):
            view = ItemView(
                id=f"view-{i}",
                tenant_id=test_tenant_id,
                check_item_id="item-views",
                user_id="viewer-user",
                view_started_at=datetime.now(timezone.utc),
                view_ended_at=datetime.now(timezone.utc),
                duration_seconds=60 + i * 30,
                front_image_viewed=True,
                back_image_viewed=i > 0,
            )
            db_session.add(view)
        await db_session.commit()

        response = client.get(
            "/api/v1/audit/items/item-views/views",
            headers=auditor_headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 3


class TestUserActivity:
    """Tests for user activity retrieval."""

    @pytest.mark.asyncio
    async def test_get_user_activity(self, client, db_session, test_tenant_id, auditor_headers):
        """Test getting activity for a specific user."""
        # Create logs for specific user
        for i in range(5):
            log = AuditLog(
                id=f"audit-user-{i}",
                tenant_id=test_tenant_id,
                timestamp=datetime.now(timezone.utc),
                action=AuditAction.ITEM_VIEWED,
                resource_type="check_item",
                resource_id=f"item-{i}",
                user_id="target-user",
                username="targetuser",
            )
            db_session.add(log)

        # Create logs for different user
        log_other = AuditLog(
            id="audit-other",
            tenant_id=test_tenant_id,
            timestamp=datetime.now(timezone.utc),
            action=AuditAction.ITEM_VIEWED,
            resource_type="check_item",
            user_id="other-user",
            username="otheruser",
        )
        db_session.add(log_other)
        await db_session.commit()

        response = client.get(
            "/api/v1/audit/users/target-user",
            headers=auditor_headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 5
        assert all(log["user_id"] == "target-user" for log in data)


class TestAuditPacketGeneration:
    """Tests for audit packet generation."""

    @pytest.mark.asyncio
    async def test_generate_audit_packet(self, client, db_session, test_tenant_id, auditor_headers):
        """Test generating an audit packet."""
        # Create check item
        item = CheckItem(
            id="item-packet",
            tenant_id=test_tenant_id,
            external_item_id="EXT-PACKET",
            account_id="acct-packet",
            amount=Decimal("5000.00"),
            status=CheckStatus.APPROVED,
            risk_level=RiskLevel.MEDIUM,
            item_type=ItemType.ON_US,
            presented_date=datetime.now(timezone.utc),
        )
        db_session.add(item)
        await db_session.commit()

        response = client.post(
            "/api/v1/audit/packet",
            headers=auditor_headers,
            json={
                "check_item_id": "item-packet",
                "format": "pdf",
                "include_images": True,
                "include_history": True,
            },
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "packet_id" in data
        assert "download_url" in data
        assert data["check_item_id"] == "item-packet"

    @pytest.mark.asyncio
    async def test_generate_packet_item_not_found(self, client, auditor_headers):
        """Test generating packet for non-existent item."""
        response = client.post(
            "/api/v1/audit/packet",
            headers=auditor_headers,
            json={
                "check_item_id": "nonexistent-item",
                "format": "pdf",
            },
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestMultiTenantAudit:
    """Tests for multi-tenant audit isolation."""

    @pytest.mark.asyncio
    async def test_audit_logs_isolated(self, client, db_session):
        """Test that audit logs are isolated between tenants."""
        tenant_a = "audit-tenant-a"
        tenant_b = "audit-tenant-b"

        # Create logs for tenant A
        for i in range(3):
            log = AuditLog(
                id=f"audit-a-{i}",
                tenant_id=tenant_a,
                timestamp=datetime.now(timezone.utc),
                action=AuditAction.ITEM_VIEWED,
                resource_type="check_item",
                user_id="user-a",
                username="usera",
            )
            db_session.add(log)

        # Create logs for tenant B
        for i in range(2):
            log = AuditLog(
                id=f"audit-b-{i}",
                tenant_id=tenant_b,
                timestamp=datetime.now(timezone.utc),
                action=AuditAction.ITEM_VIEWED,
                resource_type="check_item",
                user_id="user-b",
                username="userb",
            )
            db_session.add(log)
        await db_session.commit()

        # Query as tenant A
        token_a = create_access_token(
            subject="auditor-a",
            additional_claims={
                "username": "auditora",
                "roles": ["auditor"],
                "permissions": ["audit:view"],
                "tenant_id": tenant_a,
            },
        )

        response = client.get(
            "/api/v1/audit/logs",
            headers={"Authorization": f"Bearer {token_a}"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total"] == 3

        # Query as tenant B
        token_b = create_access_token(
            subject="auditor-b",
            additional_claims={
                "username": "auditorb",
                "roles": ["auditor"],
                "permissions": ["audit:view"],
                "tenant_id": tenant_b,
            },
        )

        response = client.get(
            "/api/v1/audit/logs",
            headers={"Authorization": f"Bearer {token_b}"},
        )

        data = response.json()
        assert data["total"] == 2
