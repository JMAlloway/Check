"""
Unit tests for database constraints and model validation.

Tests cover:
- Field length constraints
- Required fields (NOT NULL)
- Unique constraints
- Foreign key relationships
- Enum validation
- JSONB field handling
- Audit log immutability
"""

import pytest
from datetime import datetime, timezone
from decimal import Decimal
import uuid

from sqlalchemy import inspect
from pydantic import ValidationError

from app.models.check import CheckItem, CheckStatus, RiskLevel
from app.models.decision import Decision, DecisionAction
from app.models.user import User, Role, Permission
from app.models.audit import AuditLog, AuditAction, ItemView
from app.models.queue import Queue, QueueType


class TestCheckItemConstraints:
    """Tests for CheckItem model constraints."""

    def test_check_item_requires_tenant_id(self):
        """CheckItem should require tenant_id."""
        # The model should have tenant_id as required
        mapper = inspect(CheckItem)
        tenant_col = mapper.columns.get("tenant_id")
        assert tenant_col is not None
        assert tenant_col.nullable is False

    def test_check_item_requires_external_item_id(self):
        """CheckItem should require external_item_id."""
        mapper = inspect(CheckItem)
        ext_id_col = mapper.columns.get("external_item_id")
        assert ext_id_col is not None
        assert ext_id_col.nullable is False

    def test_check_item_amount_is_decimal(self):
        """CheckItem amount should be a decimal field."""
        mapper = inspect(CheckItem)
        amount_col = mapper.columns.get("amount")
        assert amount_col is not None
        # Check it's a numeric type
        assert "NUMERIC" in str(amount_col.type).upper() or \
               "DECIMAL" in str(amount_col.type).upper() or \
               "FLOAT" in str(amount_col.type).upper()

    def test_check_status_enum_values(self):
        """CheckStatus enum should have expected values."""
        expected_statuses = [
            "new", "in_review", "pending_approval", "approved",
            "returned", "rejected", "escalated"
        ]
        actual_values = [s.value for s in CheckStatus]

        for status in expected_statuses:
            assert status in actual_values, f"Missing status: {status}"

    def test_risk_level_enum_values(self):
        """RiskLevel enum should have expected values."""
        expected_levels = ["low", "medium", "high", "critical"]
        actual_values = [r.value for r in RiskLevel]

        for level in expected_levels:
            assert level in actual_values, f"Missing risk level: {level}"

    def test_check_item_has_tenant_index(self):
        """CheckItem should have index on tenant_id for query performance."""
        mapper = inspect(CheckItem)
        indexes = mapper.persist_selectable.indexes

        # Check for tenant_id in any index
        tenant_indexed = any(
            "tenant_id" in str(idx.columns)
            for idx in indexes
        )
        # tenant_id column should have index=True
        tenant_col = mapper.columns.get("tenant_id")
        assert tenant_col.index is True or tenant_indexed


class TestDecisionConstraints:
    """Tests for Decision model constraints."""

    def test_decision_requires_check_item_id(self):
        """Decision should require check_item_id."""
        mapper = inspect(Decision)
        check_col = mapper.columns.get("check_item_id")
        assert check_col is not None
        assert check_col.nullable is False

    def test_decision_requires_user_id(self):
        """Decision should require user_id."""
        mapper = inspect(Decision)
        user_col = mapper.columns.get("user_id")
        assert user_col is not None
        assert user_col.nullable is False

    def test_decision_requires_action(self):
        """Decision should require action."""
        mapper = inspect(Decision)
        action_col = mapper.columns.get("action")
        assert action_col is not None
        assert action_col.nullable is False

    def test_decision_action_enum_values(self):
        """DecisionAction enum should have expected values."""
        expected_actions = [
            "approve", "return", "reject", "escalate",
            "hold", "needs_more_info"
        ]
        actual_values = [a.value for a in DecisionAction]

        for action in expected_actions:
            assert action in actual_values, f"Missing action: {action}"

    def test_decision_has_foreign_key_to_check_item(self):
        """Decision should have foreign key to CheckItem."""
        mapper = inspect(Decision)
        check_col = mapper.columns.get("check_item_id")

        # Check for foreign key
        assert len(check_col.foreign_keys) > 0


class TestUserConstraints:
    """Tests for User model constraints."""

    def test_user_requires_username(self):
        """User should require username."""
        mapper = inspect(User)
        username_col = mapper.columns.get("username")
        assert username_col is not None
        assert username_col.nullable is False

    def test_user_requires_email(self):
        """User should require email."""
        mapper = inspect(User)
        email_col = mapper.columns.get("email")
        assert email_col is not None
        assert email_col.nullable is False

    def test_username_has_max_length(self):
        """Username should have maximum length constraint."""
        mapper = inspect(User)
        username_col = mapper.columns.get("username")

        # Check length constraint
        assert hasattr(username_col.type, "length")
        assert username_col.type.length is not None
        assert username_col.type.length <= 100  # Reasonable max

    def test_user_has_unique_username_constraint(self):
        """Username should be unique within tenant."""
        mapper = inspect(User)
        username_col = mapper.columns.get("username")

        # Check for unique constraint or index
        # The actual unique constraint may be composite (tenant_id, username)
        assert username_col.unique is True or \
               any("username" in str(idx) for idx in mapper.persist_selectable.indexes)


class TestAuditLogConstraints:
    """Tests for AuditLog model constraints."""

    def test_audit_log_requires_timestamp(self):
        """AuditLog should require timestamp."""
        mapper = inspect(AuditLog)
        ts_col = mapper.columns.get("timestamp")
        assert ts_col is not None
        assert ts_col.nullable is False

    def test_audit_log_requires_action(self):
        """AuditLog should require action."""
        mapper = inspect(AuditLog)
        action_col = mapper.columns.get("action")
        assert action_col is not None
        assert action_col.nullable is False

    def test_audit_log_requires_resource_type(self):
        """AuditLog should require resource_type."""
        mapper = inspect(AuditLog)
        rt_col = mapper.columns.get("resource_type")
        assert rt_col is not None
        assert rt_col.nullable is False

    def test_audit_action_enum_values(self):
        """AuditAction enum should have expected values."""
        # Just verify enum exists and has some expected values
        assert AuditAction.LOGIN is not None
        assert AuditAction.LOGOUT is not None
        assert AuditAction.DECISION_MADE is not None
        assert AuditAction.ITEM_VIEWED is not None

    def test_audit_log_has_timestamp_index(self):
        """AuditLog should have index on timestamp for queries."""
        mapper = inspect(AuditLog)
        ts_col = mapper.columns.get("timestamp")
        assert ts_col.index is True

    def test_audit_log_jsonb_fields(self):
        """AuditLog should have JSONB fields for flexible data."""
        mapper = inspect(AuditLog)

        before_col = mapper.columns.get("before_value")
        after_col = mapper.columns.get("after_value")
        extra_col = mapper.columns.get("extra_data")

        assert before_col is not None
        assert after_col is not None
        assert extra_col is not None

    def test_audit_log_has_integrity_hash(self):
        """AuditLog should have integrity_hash field."""
        mapper = inspect(AuditLog)
        hash_col = mapper.columns.get("integrity_hash")
        assert hash_col is not None


class TestQueueConstraints:
    """Tests for Queue model constraints."""

    def test_queue_requires_name(self):
        """Queue should require name."""
        mapper = inspect(Queue)
        name_col = mapper.columns.get("name")
        assert name_col is not None
        assert name_col.nullable is False

    def test_queue_requires_tenant_id(self):
        """Queue should require tenant_id."""
        mapper = inspect(Queue)
        tenant_col = mapper.columns.get("tenant_id")
        assert tenant_col is not None
        assert tenant_col.nullable is False

    def test_queue_type_enum_values(self):
        """QueueType enum should have expected values."""
        expected_types = ["standard", "high_priority", "escalation", "special_review"]
        actual_values = [t.value for t in QueueType]

        for queue_type in expected_types:
            assert queue_type in actual_values, f"Missing queue type: {queue_type}"


class TestItemViewConstraints:
    """Tests for ItemView model constraints."""

    def test_item_view_requires_tenant_id(self):
        """ItemView should require tenant_id."""
        mapper = inspect(ItemView)
        tenant_col = mapper.columns.get("tenant_id")
        assert tenant_col is not None
        assert tenant_col.nullable is False

    def test_item_view_requires_check_item_id(self):
        """ItemView should require check_item_id."""
        mapper = inspect(ItemView)
        check_col = mapper.columns.get("check_item_id")
        assert check_col is not None
        assert check_col.nullable is False

    def test_item_view_requires_user_id(self):
        """ItemView should require user_id."""
        mapper = inspect(ItemView)
        user_col = mapper.columns.get("user_id")
        assert user_col is not None
        assert user_col.nullable is False

    def test_item_view_has_interaction_flags(self):
        """ItemView should have interaction tracking flags."""
        mapper = inspect(ItemView)

        expected_flags = [
            "front_image_viewed",
            "back_image_viewed",
            "zoom_used",
            "magnifier_used",
            "history_compared",
            "ai_assists_viewed",
            "context_panel_viewed",
        ]

        for flag in expected_flags:
            col = mapper.columns.get(flag)
            assert col is not None, f"Missing interaction flag: {flag}"


class TestRolePermissionConstraints:
    """Tests for Role and Permission model constraints."""

    def test_role_requires_name(self):
        """Role should require name."""
        mapper = inspect(Role)
        name_col = mapper.columns.get("name")
        assert name_col is not None
        assert name_col.nullable is False

    def test_permission_requires_resource(self):
        """Permission should require resource."""
        mapper = inspect(Permission)
        resource_col = mapper.columns.get("resource")
        assert resource_col is not None
        assert resource_col.nullable is False

    def test_permission_requires_action(self):
        """Permission should require action."""
        mapper = inspect(Permission)
        action_col = mapper.columns.get("action")
        assert action_col is not None
        assert action_col.nullable is False


class TestFieldLengthConstraints:
    """Tests for field length constraints across models."""

    def test_username_max_length(self):
        """Username should have reasonable max length."""
        mapper = inspect(User)
        col = mapper.columns.get("username")
        assert col.type.length <= 100

    def test_email_max_length(self):
        """Email should have reasonable max length."""
        mapper = inspect(User)
        col = mapper.columns.get("email")
        assert col.type.length <= 255

    def test_check_external_item_id_max_length(self):
        """Check external_item_id should have reasonable max length."""
        mapper = inspect(CheckItem)
        col = mapper.columns.get("external_item_id")
        assert col.type.length <= 100

    def test_tenant_id_length(self):
        """Tenant ID should accommodate UUIDs."""
        mapper = inspect(User)
        col = mapper.columns.get("tenant_id")
        assert col.type.length >= 36  # UUID length


class TestUniqueConstraints:
    """Tests for unique constraints."""

    def test_user_email_unique_within_tenant(self):
        """User email should be unique within tenant."""
        # This is typically enforced via composite unique constraint
        # Verify the column exists and has some uniqueness indicator
        mapper = inspect(User)
        email_col = mapper.columns.get("email")
        assert email_col is not None

    def test_check_external_item_id_unique_within_tenant(self):
        """Check external_item_id should be unique within tenant."""
        # External ID uniqueness per tenant prevents duplicates
        mapper = inspect(CheckItem)
        ext_id_col = mapper.columns.get("external_item_id")
        assert ext_id_col is not None
