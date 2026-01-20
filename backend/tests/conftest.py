"""
Pytest configuration and fixtures for Check Review Console tests.

Provides common fixtures for:
- Test database setup
- Test client with authentication
- Mock users and tenants
- Common test data
"""

import asyncio
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.core.security import create_access_token, get_password_hash
from app.db.session import Base, get_db
from app.main import app

# =============================================================================
# Event Loop Configuration
# =============================================================================


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# =============================================================================
# Database Fixtures
# =============================================================================


# Use SQLite for tests (faster, no external dependencies)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture(scope="function")
async def async_engine():
    """Create async test database engine."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session(async_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create async database session for tests."""
    async_session = async_sessionmaker(
        async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with async_session() as session:
        yield session
        await session.rollback()


@pytest.fixture(scope="function")
def override_get_db(db_session):
    """Override the get_db dependency for tests."""

    async def _override():
        yield db_session

    return _override


# =============================================================================
# Test Client Fixtures
# =============================================================================


@pytest.fixture(scope="function")
def client(override_get_db) -> Generator[TestClient, None, None]:
    """Create test client with database override."""
    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()


# =============================================================================
# User and Authentication Fixtures
# =============================================================================


@pytest.fixture
def test_tenant_id() -> str:
    """Generate a test tenant ID."""
    return str(uuid.uuid4())


@pytest.fixture
def test_user_id() -> str:
    """Generate a test user ID."""
    return str(uuid.uuid4())


@pytest.fixture
def test_user_data(test_tenant_id, test_user_id) -> dict:
    """Generate test user data."""
    return {
        "id": test_user_id,
        "tenant_id": test_tenant_id,
        "username": "testuser",
        "email": "testuser@example.com",
        "full_name": "Test User",
        "is_active": True,
        "is_superuser": False,
        "hashed_password": get_password_hash("testpassword123"),
    }


@pytest.fixture
def test_superuser_data(test_tenant_id) -> dict:
    """Generate test superuser data."""
    return {
        "id": str(uuid.uuid4()),
        "tenant_id": test_tenant_id,
        "username": "superuser",
        "email": "superuser@example.com",
        "full_name": "Super User",
        "is_active": True,
        "is_superuser": True,
        "hashed_password": get_password_hash("superpassword123"),
    }


@pytest.fixture
def user_token(test_user_data) -> str:
    """Generate access token for test user."""
    return create_access_token(
        subject=test_user_data["id"],
        additional_claims={
            "username": test_user_data["username"],
            "roles": ["reviewer"],
            "permissions": ["check:view", "check:decide", "report:view"],
            "tenant_id": test_user_data["tenant_id"],
        },
    )


@pytest.fixture
def superuser_token(test_superuser_data) -> str:
    """Generate access token for superuser."""
    return create_access_token(
        subject=test_superuser_data["id"],
        additional_claims={
            "username": test_superuser_data["username"],
            "roles": ["admin"],
            "permissions": ["*:*"],
            "tenant_id": test_superuser_data["tenant_id"],
        },
    )


@pytest.fixture
def auth_headers(user_token) -> dict:
    """Generate auth headers for test user."""
    return {"Authorization": f"Bearer {user_token}"}


@pytest.fixture
def superuser_headers(superuser_token) -> dict:
    """Generate auth headers for superuser."""
    return {"Authorization": f"Bearer {superuser_token}"}


# =============================================================================
# Mock User Fixtures
# =============================================================================


@pytest.fixture
def mock_current_user(test_user_data, test_tenant_id):
    """Create a mock current user object."""
    user = MagicMock()
    user.id = test_user_data["id"]
    user.tenant_id = test_tenant_id
    user.username = test_user_data["username"]
    user.email = test_user_data["email"]
    user.full_name = test_user_data["full_name"]
    user.is_active = True
    user.is_superuser = False
    user.roles = []
    return user


@pytest.fixture
def mock_superuser(test_superuser_data, test_tenant_id):
    """Create a mock superuser object."""
    user = MagicMock()
    user.id = test_superuser_data["id"]
    user.tenant_id = test_tenant_id
    user.username = test_superuser_data["username"]
    user.email = test_superuser_data["email"]
    user.full_name = test_superuser_data["full_name"]
    user.is_active = True
    user.is_superuser = True
    user.roles = []
    return user


# =============================================================================
# Check Item Fixtures
# =============================================================================


@pytest.fixture
def test_check_item_data(test_tenant_id) -> dict:
    """Generate test check item data."""
    return {
        "id": str(uuid.uuid4()),
        "tenant_id": test_tenant_id,
        "external_id": f"CHK-{uuid.uuid4().hex[:8].upper()}",
        "account_number_masked": "****1234",
        "routing_number_masked": "****5678",
        "amount": 1500.00,
        "payee_name": "Test Payee",
        "payer_name": "Test Payer",
        "check_number": "1001",
        "presented_date": datetime.now(timezone.utc),
        "status": "new",
        "risk_level": "medium",
        "queue_id": str(uuid.uuid4()),
    }


@pytest.fixture
def test_decision_data(test_tenant_id, test_user_id, test_check_item_data) -> dict:
    """Generate test decision data."""
    return {
        "id": str(uuid.uuid4()),
        "tenant_id": test_tenant_id,
        "check_item_id": test_check_item_data["id"],
        "user_id": test_user_id,
        "action": "approve",
        "reason_codes": ["verified_signature", "known_payee"],
        "notes": "All verification checks passed",
        "created_at": datetime.now(timezone.utc),
    }


# =============================================================================
# Helper Fixtures
# =============================================================================


@pytest.fixture
def mock_audit_service():
    """Create a mock audit service."""
    with patch("app.audit.service.AuditService") as mock:
        mock_instance = AsyncMock()
        mock.return_value = mock_instance
        mock_instance.log.return_value = MagicMock(id=str(uuid.uuid4()))
        yield mock_instance


@pytest.fixture
def freeze_time():
    """Fixture to freeze time for testing."""
    frozen_time = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)

    with patch("app.core.security.datetime") as mock_dt:
        mock_dt.now.return_value = frozen_time
        mock_dt.utcnow.return_value = frozen_time.replace(tzinfo=None)
        yield frozen_time
