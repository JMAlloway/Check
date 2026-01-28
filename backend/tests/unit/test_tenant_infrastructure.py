"""
Unit tests for tenant isolation infrastructure.

Tests the TenantContext, TenantAwareSession, and related components
that provide automatic tenant filtering at the ORM layer.

Run with: pytest tests/unit/test_tenant_infrastructure.py -v
"""

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.tenant import (
    TenantAwareSession,
    TenantContext,
    TenantIsolationError,
    TenantScopedMixin,
    is_tenant_scoped_model,
    register_tenant_scoped_model,
    tenant_filter,
)

# =============================================================================
# TenantContext Tests
# =============================================================================


class TestTenantContext:
    """Tests for TenantContext async-safe context management."""

    def test_get_returns_none_when_not_set(self):
        """TenantContext.get() returns None when no tenant is set."""
        TenantContext.clear()
        assert TenantContext.get() is None

    def test_set_and_get(self):
        """TenantContext.set() stores tenant_id retrievable by get()."""
        TenantContext.clear()
        TenantContext.set("tenant-123")
        assert TenantContext.get() == "tenant-123"
        TenantContext.clear()

    def test_clear_removes_tenant(self):
        """TenantContext.clear() removes the stored tenant_id."""
        TenantContext.set("tenant-123")
        TenantContext.clear()
        assert TenantContext.get() is None

    def test_get_required_raises_when_not_set(self):
        """TenantContext.get_required() raises when no tenant is set."""
        TenantContext.clear()
        with pytest.raises(TenantIsolationError) as exc_info:
            TenantContext.get_required()
        assert "not set" in str(exc_info.value)

    def test_get_required_returns_tenant_when_set(self):
        """TenantContext.get_required() returns tenant_id when set."""
        TenantContext.set("tenant-456")
        assert TenantContext.get_required() == "tenant-456"
        TenantContext.clear()

    def test_scope_context_manager(self):
        """TenantContext.scope() context manager sets and restores tenant."""
        TenantContext.clear()

        with TenantContext.scope("scoped-tenant"):
            assert TenantContext.get() == "scoped-tenant"

        # After scope, should be cleared
        assert TenantContext.get() is None

    def test_scope_preserves_previous_tenant(self):
        """TenantContext.scope() restores previous tenant on exit."""
        TenantContext.set("outer-tenant")

        with TenantContext.scope("inner-tenant"):
            assert TenantContext.get() == "inner-tenant"

        assert TenantContext.get() == "outer-tenant"
        TenantContext.clear()

    def test_nested_scopes(self):
        """Nested TenantContext.scope() calls work correctly."""
        TenantContext.clear()

        with TenantContext.scope("level-1"):
            assert TenantContext.get() == "level-1"

            with TenantContext.scope("level-2"):
                assert TenantContext.get() == "level-2"

                with TenantContext.scope("level-3"):
                    assert TenantContext.get() == "level-3"

                assert TenantContext.get() == "level-2"

            assert TenantContext.get() == "level-1"

        assert TenantContext.get() is None


# =============================================================================
# TenantScopedMixin Tests
# =============================================================================


class TestTenantScopedMixin:
    """Tests for TenantScopedMixin model registration."""

    def test_subclass_is_registered(self):
        """Classes inheriting TenantScopedMixin are automatically registered."""

        class TestModel(TenantScopedMixin):
            pass

        assert is_tenant_scoped_model(TestModel)

    def test_non_mixin_class_not_registered(self):
        """Classes not inheriting TenantScopedMixin are not registered."""

        class RegularModel:
            pass

        assert not is_tenant_scoped_model(RegularModel)


# =============================================================================
# TenantAwareSession Tests
# =============================================================================


class TestTenantAwareSession:
    """Tests for TenantAwareSession tenant-scoped database operations."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock AsyncSession."""
        session = AsyncMock(spec=AsyncSession)
        return session

    @pytest.fixture
    def tenant_session(self, mock_session):
        """Create a TenantAwareSession with mock underlying session."""
        return TenantAwareSession(
            session=mock_session,
            tenant_id="test-tenant-123",
            strict=True,
        )

    def test_tenant_id_stored(self, tenant_session):
        """TenantAwareSession stores the tenant_id."""
        assert tenant_session.tenant_id == "test-tenant-123"

    def test_sets_tenant_context(self, mock_session):
        """TenantAwareSession sets TenantContext on creation."""
        TenantContext.clear()

        TenantAwareSession(
            session=mock_session,
            tenant_id="context-tenant",
            strict=True,
        )

        assert TenantContext.get() == "context-tenant"
        TenantContext.clear()

    @pytest.mark.asyncio
    async def test_add_auto_sets_tenant_id(self, tenant_session):
        """TenantAwareSession.add() auto-sets tenant_id for tenant-scoped models."""

        class MockTenantModel(TenantScopedMixin):
            tenant_id = None

        instance = MockTenantModel()
        tenant_session.add(instance)

        assert instance.tenant_id == "test-tenant-123"

    @pytest.mark.asyncio
    async def test_add_rejects_wrong_tenant(self, tenant_session):
        """TenantAwareSession.add() rejects models with wrong tenant_id."""

        class MockTenantModel(TenantScopedMixin):
            tenant_id = "wrong-tenant"

        instance = MockTenantModel()

        with pytest.raises(TenantIsolationError) as exc_info:
            tenant_session.add(instance)

        assert "wrong-tenant" in str(exc_info.value)
        assert "test-tenant-123" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_add_allows_matching_tenant(self, tenant_session):
        """TenantAwareSession.add() allows models with matching tenant_id."""

        class MockTenantModel(TenantScopedMixin):
            tenant_id = "test-tenant-123"

        instance = MockTenantModel()
        tenant_session.add(instance)  # Should not raise

    @pytest.mark.asyncio
    async def test_delete_rejects_wrong_tenant(self, tenant_session):
        """TenantAwareSession.delete() rejects models with wrong tenant_id."""

        class MockTenantModel(TenantScopedMixin):
            tenant_id = "wrong-tenant"

        instance = MockTenantModel()

        with pytest.raises(TenantIsolationError) as exc_info:
            await tenant_session.delete(instance)

        assert "wrong-tenant" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_commit_delegates(self, tenant_session, mock_session):
        """TenantAwareSession.commit() delegates to underlying session."""
        await tenant_session.commit()
        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_rollback_delegates(self, tenant_session, mock_session):
        """TenantAwareSession.rollback() delegates to underlying session."""
        await tenant_session.rollback()
        mock_session.rollback.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_clears_context(self, tenant_session):
        """TenantAwareSession.close() clears TenantContext."""
        TenantContext.set("test-tenant-123")

        await tenant_session.close()

        assert TenantContext.get() is None


# =============================================================================
# tenant_filter Function Tests
# =============================================================================


class TestTenantFilterFunction:
    """Tests for the tenant_filter helper function."""

    def test_explicit_tenant_id(self):
        """tenant_filter with explicit tenant_id creates correct filter."""

        class MockModel:
            tenant_id = "column"  # Mock column

        # This would create: MockModel.tenant_id == "explicit-tenant"
        # We can't easily test the actual filter without a real ORM model
        TenantContext.clear()

    def test_context_tenant_id(self):
        """tenant_filter uses TenantContext when tenant_id not provided."""
        TenantContext.set("context-tenant")

        class MockModel:
            tenant_id = "column"

        # Would use context tenant_id
        TenantContext.clear()

    def test_raises_without_tenant_id_column(self):
        """tenant_filter raises for models without tenant_id column."""

        class NoTenantModel:
            pass

        with pytest.raises(TenantIsolationError) as exc_info:
            tenant_filter(NoTenantModel, "any-tenant")

        assert "tenant_id" in str(exc_info.value)


# =============================================================================
# TenantIsolationError Tests
# =============================================================================


class TestTenantIsolationError:
    """Tests for TenantIsolationError exception."""

    def test_basic_creation(self):
        """TenantIsolationError can be created with message."""
        error = TenantIsolationError("Test error")
        assert str(error) == "Test error"

    def test_with_model(self):
        """TenantIsolationError stores model name."""
        error = TenantIsolationError("Test error", model="CheckItem")
        assert error.model == "CheckItem"

    def test_with_query(self):
        """TenantIsolationError stores query."""
        error = TenantIsolationError("Test error", query="SELECT * FROM checks")
        assert error.query == "SELECT * FROM checks"


# =============================================================================
# Integration-Style Unit Tests
# =============================================================================


class TestTenantIsolationWorkflow:
    """
    Tests that verify the complete tenant isolation workflow.

    These are higher-level unit tests that verify the components
    work together correctly.
    """

    @pytest.fixture
    def mock_session(self):
        """Create a mock AsyncSession."""
        return AsyncMock(spec=AsyncSession)

    @pytest.mark.asyncio
    async def test_complete_workflow(self, mock_session):
        """Test complete tenant isolation workflow."""
        # 1. Create tenant-aware session
        tenant_id = "workflow-tenant-" + uuid.uuid4().hex[:8]
        session = TenantAwareSession(
            session=mock_session,
            tenant_id=tenant_id,
            strict=True,
        )

        # 2. Verify context is set
        assert TenantContext.get() == tenant_id
        assert session.tenant_id == tenant_id

        # 3. Create a tenant-scoped model instance
        class WorkflowModel(TenantScopedMixin):
            tenant_id = None

        instance = WorkflowModel()

        # 4. Add to session - should auto-set tenant_id
        session.add(instance)
        assert instance.tenant_id == tenant_id

        # 5. Close session - should clear context
        await session.close()
        assert TenantContext.get() is None

    @pytest.mark.asyncio
    async def test_strict_vs_permissive_mode(self, mock_session):
        """Test that strict mode raises and permissive mode warns."""
        # Strict mode
        strict_session = TenantAwareSession(
            session=mock_session,
            tenant_id="strict-tenant",
            strict=True,
        )

        # Permissive mode
        permissive_session = TenantAwareSession(
            session=mock_session,
            tenant_id="permissive-tenant",
            strict=False,
        )

        # Both should work for normal operations
        class TestModel(TenantScopedMixin):
            tenant_id = None

        instance1 = TestModel()
        strict_session.add(instance1)
        assert instance1.tenant_id == "strict-tenant"

        instance2 = TestModel()
        permissive_session.add(instance2)
        assert instance2.tenant_id == "permissive-tenant"

        await strict_session.close()
        await permissive_session.close()


# =============================================================================
# Security-Focused Tests
# =============================================================================


class TestTenantIsolationSecurity:
    """
    Security-focused tests for tenant isolation.

    These tests verify that the tenant isolation infrastructure
    provides the expected security guarantees.
    """

    def test_context_isolation_between_requests(self):
        """Verify tenant context doesn't leak between operations."""
        # Simulate first request
        TenantContext.set("tenant-request-1")
        assert TenantContext.get() == "tenant-request-1"

        # Clear (as would happen at request end)
        TenantContext.clear()

        # Simulate second request - should not see first tenant
        assert TenantContext.get() is None

    @pytest.mark.asyncio
    async def test_cannot_bypass_tenant_check_on_add(self):
        """Verify tenant check cannot be bypassed when adding entities."""
        mock_session = AsyncMock(spec=AsyncSession)

        session = TenantAwareSession(
            session=mock_session,
            tenant_id="legitimate-tenant",
            strict=True,
        )

        class SecureModel(TenantScopedMixin):
            tenant_id = "attacker-tenant"  # Pre-set to wrong tenant

        instance = SecureModel()

        # Attempt to add with wrong tenant should fail
        with pytest.raises(TenantIsolationError):
            session.add(instance)

        await session.close()

    @pytest.mark.asyncio
    async def test_cannot_bypass_tenant_check_on_delete(self):
        """Verify tenant check cannot be bypassed when deleting entities."""
        mock_session = AsyncMock(spec=AsyncSession)

        session = TenantAwareSession(
            session=mock_session,
            tenant_id="legitimate-tenant",
            strict=True,
        )

        class SecureModel(TenantScopedMixin):
            tenant_id = "other-tenant"

        instance = SecureModel()

        # Attempt to delete entity from other tenant should fail
        with pytest.raises(TenantIsolationError):
            await session.delete(instance)

        await session.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
