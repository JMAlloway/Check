"""
Pytest configuration and fixtures for Check Review Console tests.

Provides common fixtures for:
- Test database setup
- Test client with authentication
- Mock users and tenants
- Common test data
"""

import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import selectinload
from sqlalchemy.pool import NullPool

# NOTE: endpoints depend on app.api.deps.get_db (which opens the app's pooled
# AsyncSessionLocal). That is the dependency that must be overridden so requests
# use the test engine; overriding app.db.session.get_db would have no effect.
from app.api.deps import get_current_user, get_db, security
from app.core.config import settings
from app.core.rate_limit import limiter, tenant_limiter, user_limiter
from app.core.security import create_access_token, decode_token, get_password_hash
from app.db.enums import create_enum_types
from app.db.session import Base
from app.main import app
from app.models.user import Permission, Role, User

# Rate limiting is irrelevant to test correctness and causes flaky 429s when many
# requests run in sequence. Disable all limiters for the test session.
limiter.enabled = False
user_limiter.enabled = False
tenant_limiter.enabled = False

# A valid bcrypt hash for the synthesized auth user, so password verification
# (e.g. change-password) returns False rather than raising UnknownHashError.
_PLACEHOLDER_PASSWORD_HASH = get_password_hash("conftest-placeholder-password")

# =============================================================================
# Database Fixtures
# =============================================================================


# Tests run against PostgreSQL to match production (the app relies on
# Postgres-specific column types: JSONB, UUID, ARRAY, INET). The connection
# string comes from DATABASE_URL (set by CI to the postgres service); the
# default targets a locally running postgres for developer convenience.
TEST_DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/test_db",
)


async def _reset_schema(conn) -> None:
    """Reset to an empty public schema, then build enums + tables.

    A raw DROP SCHEMA ... CASCADE is used instead of Base.metadata.drop_all
    because check_items and decisions have a circular foreign-key dependency
    that drop_all cannot topologically sort.
    """
    await conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
    await conn.execute(text("CREATE SCHEMA public"))
    await create_enum_types(conn)
    await conn.run_sync(Base.metadata.create_all)


@pytest_asyncio.fixture(scope="function")
async def async_engine():
    """Engine used only in the pytest event loop (schema setup + db_session).

    A separate engine (app_engine) serves request handlers in the TestClient's
    portal loop. Keeping them distinct avoids reusing one engine across two
    event loops, which asyncpg forbids.
    """
    engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)

    async with engine.begin() as conn:
        await _reset_schema(conn)

    yield engine

    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def app_engine(async_engine):
    """Engine used only by request handlers (the TestClient portal loop).

    Depends on async_engine so the schema is (re)created before any request runs
    -- otherwise a test that uses ``client`` but not ``db_session`` would hit a
    database with no tables (order-dependent "relation does not exist" errors).
    """
    engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)
    yield engine
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
        # Test setup data frequently references fabricated foreign keys (e.g.
        # AuditLog.user_id="user-1"). SQLite silently allowed this; Postgres
        # enforces it. Disable FK/trigger enforcement on this SETUP session only
        # -- request handlers use a separate session that still enforces FKs, so
        # the code under test is validated normally.
        await session.execute(text("SET session_replication_role = replica"))
        yield session
        await session.rollback()


@pytest.fixture(scope="function")
def override_get_db(app_engine):
    """Override get_db with a fresh session per request.

    The TestClient runs the ASGI app in its own event loop/thread, and asyncpg
    connections cannot cross event loops. So each request gets its own session
    from app_engine (used only in the request loop). Tests commit their setup
    data via db_session, so the request session sees it.
    """
    session_factory = async_sessionmaker(app_engine, class_=AsyncSession, expire_on_commit=False)

    async def _override():
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    return _override


# =============================================================================
# Test Client Fixtures
# =============================================================================


def _synthesize_user_from_claims(payload: dict) -> "User":
    """Build a transient User from JWT claims (not persisted).

    The token's ``permissions`` claim (a list of ``"resource:action"`` strings,
    or ``"*:*"`` for superuser) is materialized into transient Role/Permission
    objects so that User.has_permission / has_role behave as the test intends.
    """
    now = datetime.now(timezone.utc)
    perms = payload.get("permissions", []) or []
    # Transient ORM objects do not receive column defaults (id, created_at, ...)
    # until flush, but response serializers (e.g. /me) read them, so set them.
    role = Role(
        id=str(uuid.uuid4()),
        name=(payload.get("roles") or ["user"])[0],
        description=None,
        is_system=False,
        created_at=now,
        updated_at=now,
    )
    # Permission.name is the action (e.g. "review"); EntitlementService's
    # no-explicit-entitlement fallback checks `permission.name == "review"`.
    role.permissions = [
        Permission(
            id=str(uuid.uuid4()),
            name=action,
            resource=resource,
            action=action,
            created_at=now,
            updated_at=now,
        )
        for p in perms
        if p != "*:*"
        for resource, _, action in [p.partition(":")]
    ]
    username = payload.get("username", "testuser")
    user = User(
        id=payload.get("sub"),
        tenant_id=payload.get("tenant_id"),
        username=username,
        email=f"{username}@example.com",
        full_name=payload.get("full_name", "Test User"),
        hashed_password=_PLACEHOLDER_PASSWORD_HASH,
        is_active=True,
        is_superuser="*:*" in perms,
        mfa_enabled=False,
        created_at=now,
        updated_at=now,
    )
    user.roles = [role]
    return user


async def _ensure_user_row(db: AsyncSession, user: "User") -> None:
    """Persist a minimal row for the authenticated user if absent.

    Endpoints write rows that foreign-key to users.id (audit_logs.user_id,
    queue_assignments.assigned_by_id, ...). The authenticated user is
    synthesized from the token, so its row must exist for those FKs to resolve.
    """
    if not user.id:
        return
    if await db.get(User, user.id) is not None:
        return
    # Persist into a sentinel tenant (not the token's tenant) with id-derived
    # username/email so the row satisfies FK references (audit_logs.user_id etc.)
    # without polluting tenant-scoped user listings or unique constraints.
    db.add(
        User(
            id=user.id,
            tenant_id="00000000-0000-0000-0000-0000000000ff",
            username=f"authuser-{user.id}",
            email=f"{user.id}@auth.test",
            full_name=user.full_name,
            hashed_password=user.hashed_password,
            is_active=True,
            is_superuser=user.is_superuser,
        )
    )
    await db.flush()


@pytest.fixture(scope="function")
def client(override_get_db) -> Generator[TestClient, None, None]:
    """Create test client with database and authentication overrides.

    Authentication is resolved by synthesizing a transient user from the bearer
    token claims (the token's permissions are the effective permissions). This
    lets token-based integration tests authenticate without seeding a full
    user/role graph for every case, and avoids a cross-event-loop DB lookup.
    """
    app.dependency_overrides[get_db] = override_get_db

    async def _resolve_current_user(
        credentials: HTTPAuthorizationCredentials = Depends(security),
        db: AsyncSession = Depends(get_db),
    ) -> User:
        payload = decode_token(credentials.credentials)
        if payload is None or payload.get("type") != "access" or not payload.get("sub"):
            raise HTTPException(
                status_code=401,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        # Prefer a real user the test created in the token's tenant (so tests that
        # rely on persisted attributes like mfa_enabled work). Scoping by tenant
        # avoids matching the sentinel rows _ensure_user_row persists. Otherwise
        # synthesize from claims and persist a sentinel row for FK references.
        result = await db.execute(
            select(User)
            .options(selectinload(User.roles).selectinload(Role.permissions))
            .where(User.id == payload["sub"], User.tenant_id == payload.get("tenant_id"))
        )
        existing = result.scalar_one_or_none()
        if existing is not None and existing.roles:
            # Real user with seeded roles: use as-is.
            return existing
        # Synthesize from the token (tests encode effective permissions there).
        user = _synthesize_user_from_claims(payload)
        if existing is not None:
            # Real user exists but without seeded roles: keep token-derived
            # permissions, overlay the real persisted attributes the endpoints
            # read (mfa_enabled, password hash, active/superuser flags). The
            # returned object is transient (its id already exists for FKs).
            user.mfa_enabled = existing.mfa_enabled
            user.hashed_password = existing.hashed_password
            user.is_active = existing.is_active
            user.is_superuser = existing.is_superuser
        else:
            await _ensure_user_row(db, user)
        return user

    app.dependency_overrides[get_current_user] = _resolve_current_user

    # Note: TestClient is intentionally NOT used as a context manager so the
    # app lifespan does not run. The lifespan auto-creates tables on the app's
    # own pooled engine (whose connections would be reused across each test's
    # TestClient portal loop, causing cross-event-loop errors) and starts the
    # background scheduler. Tests own schema setup via the async_engine fixture.
    client = TestClient(app)
    yield client
    client.close()

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
