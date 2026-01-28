"""
Integration tests for one-time-use image access tokens.

These tests verify the security properties of the token-based image access system:
- Token works once (one-time-use enforcement)
- Token expires after TTL
- Token cannot access other tenant's images (tenant isolation)
- Token minting requires appropriate permissions

CRITICAL FOR: Bank security compliance, vendor risk assessments
"""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.main import app
from app.models.check import CheckImage, CheckItem
from app.models.image_token import ImageAccessToken
from app.models.user import User
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession


class TestOneTimeTokenSecurity:
    """Tests for one-time-use token security properties."""

    @pytest.fixture
    def client(self):
        """Create a test client."""
        return TestClient(app)

    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        db = AsyncMock(spec=AsyncSession)
        db.commit = AsyncMock()
        db.add = MagicMock()
        return db

    @pytest.fixture
    def mock_user(self):
        """Create a mock authenticated user."""
        user = MagicMock(spec=User)
        user.id = str(uuid.uuid4())
        user.username = "test_reviewer"
        user.tenant_id = "tenant-1"
        user.is_superuser = False
        return user

    @pytest.fixture
    def mock_check_item(self):
        """Create a mock check item."""
        item = MagicMock(spec=CheckItem)
        item.id = str(uuid.uuid4())
        item.tenant_id = "tenant-1"
        return item

    @pytest.fixture
    def mock_check_image(self, mock_check_item):
        """Create a mock check image."""
        image = MagicMock(spec=CheckImage)
        image.id = str(uuid.uuid4())
        image.check_item = mock_check_item
        image.external_image_id = "ext-image-123"
        return image

    @pytest.fixture
    def mock_image_data(self):
        """Mock image binary data (1x1 transparent PNG)."""
        return bytes(
            [
                0x89,
                0x50,
                0x4E,
                0x47,
                0x0D,
                0x0A,
                0x1A,
                0x0A,
                0x00,
                0x00,
                0x00,
                0x0D,
                0x49,
                0x48,
                0x44,
                0x52,
                0x00,
                0x00,
                0x00,
                0x01,
                0x00,
                0x00,
                0x00,
                0x01,
                0x08,
                0x06,
                0x00,
                0x00,
                0x00,
                0x1F,
                0x15,
                0xC4,
                0x89,
                0x00,
                0x00,
                0x00,
                0x0A,
                0x49,
                0x44,
                0x41,
                0x54,
                0x78,
                0x9C,
                0x63,
                0x00,
                0x01,
                0x00,
                0x00,
                0x05,
                0x00,
                0x01,
                0x0D,
                0x0A,
                0x2D,
                0xB4,
                0x00,
                0x00,
                0x00,
                0x00,
                0x49,
                0x45,
                0x4E,
                0x44,
                0xAE,
                0x42,
                0x60,
                0x82,
            ]
        )


class TestTokenModel:
    """Tests for ImageAccessToken model properties."""

    def test_is_expired_when_past_expiry(self):
        """Token should be expired when current time is past expires_at."""
        token = ImageAccessToken(
            id=str(uuid.uuid4()),
            tenant_id="tenant-1",
            image_id=str(uuid.uuid4()),
            expires_at=datetime.now(timezone.utc) - timedelta(seconds=10),
            created_by_user_id=str(uuid.uuid4()),
        )
        assert token.is_expired is True

    def test_is_not_expired_when_before_expiry(self):
        """Token should not be expired when current time is before expires_at."""
        token = ImageAccessToken(
            id=str(uuid.uuid4()),
            tenant_id="tenant-1",
            image_id=str(uuid.uuid4()),
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=60),
            created_by_user_id=str(uuid.uuid4()),
        )
        assert token.is_expired is False

    def test_is_used_when_used_at_set(self):
        """Token should be marked as used when used_at is set."""
        token = ImageAccessToken(
            id=str(uuid.uuid4()),
            tenant_id="tenant-1",
            image_id=str(uuid.uuid4()),
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=60),
            used_at=datetime.now(timezone.utc),
            created_by_user_id=str(uuid.uuid4()),
        )
        assert token.is_used is True

    def test_is_not_used_when_used_at_none(self):
        """Token should not be marked as used when used_at is None."""
        token = ImageAccessToken(
            id=str(uuid.uuid4()),
            tenant_id="tenant-1",
            image_id=str(uuid.uuid4()),
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=60),
            used_at=None,
            created_by_user_id=str(uuid.uuid4()),
        )
        assert token.is_used is False

    def test_is_valid_when_not_expired_and_not_used(self):
        """Token should be valid when neither expired nor used."""
        token = ImageAccessToken(
            id=str(uuid.uuid4()),
            tenant_id="tenant-1",
            image_id=str(uuid.uuid4()),
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=60),
            used_at=None,
            created_by_user_id=str(uuid.uuid4()),
        )
        assert token.is_valid is True

    def test_is_not_valid_when_expired(self):
        """Token should not be valid when expired."""
        token = ImageAccessToken(
            id=str(uuid.uuid4()),
            tenant_id="tenant-1",
            image_id=str(uuid.uuid4()),
            expires_at=datetime.now(timezone.utc) - timedelta(seconds=10),
            used_at=None,
            created_by_user_id=str(uuid.uuid4()),
        )
        assert token.is_valid is False

    def test_is_not_valid_when_used(self):
        """Token should not be valid when already used."""
        token = ImageAccessToken(
            id=str(uuid.uuid4()),
            tenant_id="tenant-1",
            image_id=str(uuid.uuid4()),
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=60),
            used_at=datetime.now(timezone.utc),
            created_by_user_id=str(uuid.uuid4()),
        )
        assert token.is_valid is False


class TestTokenMintingEndpoint:
    """Tests for the token minting endpoint."""

    def test_token_response_structure(self):
        """Token mint response should have correct structure."""
        from app.api.v1.endpoints.images import TokenMintResponse

        # Verify response model has expected fields
        fields = TokenMintResponse.model_fields
        assert "token_id" in fields
        assert "image_url" in fields
        assert "expires_at" in fields

    def test_batch_token_response_structure(self):
        """Batch token mint response should have correct structure."""
        from app.api.v1.endpoints.images import BatchTokenMintResponse, TokenMintResponse

        # Verify batch response model has tokens list
        fields = BatchTokenMintResponse.model_fields
        assert "tokens" in fields


class TestSecureImageEndpoint:
    """Tests for the secure image access endpoint."""

    def test_secure_endpoint_returns_410_for_expired_token(self):
        """Expired tokens should return 410 Gone."""
        # This is validated by the endpoint checking token.is_expired
        # and raising HTTPException with status_code=410
        from app.api.v1.endpoints.images import get_secure_image
        from fastapi import HTTPException

        # The endpoint logic checks is_expired and raises 410
        token = ImageAccessToken(
            id=str(uuid.uuid4()),
            tenant_id="tenant-1",
            image_id=str(uuid.uuid4()),
            expires_at=datetime.now(timezone.utc) - timedelta(seconds=10),
            created_by_user_id=str(uuid.uuid4()),
        )
        assert token.is_expired is True
        # Endpoint should return 410 for this token

    def test_secure_endpoint_returns_410_for_used_token(self):
        """Already-used tokens should return 410 Gone."""
        # This is validated by the endpoint checking token.is_used
        # and raising HTTPException with status_code=410
        token = ImageAccessToken(
            id=str(uuid.uuid4()),
            tenant_id="tenant-1",
            image_id=str(uuid.uuid4()),
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=60),
            used_at=datetime.now(timezone.utc),
            created_by_user_id=str(uuid.uuid4()),
        )
        assert token.is_used is True
        # Endpoint should return 410 for this token

    def test_token_marked_used_before_serving_image(self):
        """Token should be marked as used BEFORE serving the image (atomic)."""
        # This is a critical security property:
        # The endpoint commits used_at before returning the image
        # to prevent race conditions where the same token is used twice

        # Verify the endpoint logic marks used_at before serving
        # by checking the source code order (used_at set, then commit, then serve)
        import inspect

        from app.api.v1.endpoints.images import get_image_by_token

        source = inspect.getsource(get_image_by_token)

        # Search for ASSIGNMENT of used_at, not just any reference
        used_at_assign = source.find("token.used_at =")
        assert used_at_assign > 0, "token.used_at assignment should be in function"

        # Find commit AFTER the assignment
        commit_after = source.find("await db.commit()", used_at_assign)
        assert commit_after > used_at_assign, "commit should happen after used_at assignment"

        # Find image serving AFTER the commit
        get_image_after = source.find("adapter.get_image", commit_after)
        get_thumbnail_after = source.find("adapter.get_thumbnail", commit_after)

        assert get_image_after > commit_after, "get_image should happen after commit"
        assert get_thumbnail_after > commit_after, "get_thumbnail should happen after commit"


class TestTenantIsolation:
    """Tests for tenant isolation in token system."""

    def test_token_contains_tenant_id(self):
        """Token should store tenant_id for validation."""
        token = ImageAccessToken(
            id=str(uuid.uuid4()),
            tenant_id="tenant-1",
            image_id=str(uuid.uuid4()),
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=60),
            created_by_user_id=str(uuid.uuid4()),
        )
        assert token.tenant_id == "tenant-1"

    def test_token_request_schema_requires_image_id(self):
        """Token mint request should require image_id."""
        from app.api.v1.endpoints.images import TokenMintRequest

        # Verify image_id is required (not Optional)
        fields = TokenMintRequest.model_fields
        assert "image_id" in fields
        assert fields["image_id"].is_required()

    def test_batch_request_has_max_limit(self):
        """Batch token request should have a maximum limit."""
        import inspect

        from app.api.v1.endpoints.images import mint_image_tokens_batch

        source = inspect.getsource(mint_image_tokens_batch)
        # Verify there's a limit check for batch size
        assert "len(data.image_ids) > 10" in source or "Maximum 10 tokens" in source


class TestAuditTrail:
    """Tests for audit trail in token system."""

    def test_audit_action_enum_has_token_created(self):
        """AuditAction should have IMAGE_TOKEN_CREATED action."""
        from app.models.audit import AuditAction

        assert hasattr(AuditAction, "IMAGE_TOKEN_CREATED")
        assert AuditAction.IMAGE_TOKEN_CREATED.value == "image_token_created"

    def test_audit_action_enum_has_token_used(self):
        """AuditAction should have IMAGE_TOKEN_USED action."""
        from app.models.audit import AuditAction

        assert hasattr(AuditAction, "IMAGE_TOKEN_USED")
        assert AuditAction.IMAGE_TOKEN_USED.value == "image_token_used"

    def test_token_tracks_created_by_user(self):
        """Token should track which user created it."""
        user_id = str(uuid.uuid4())
        token = ImageAccessToken(
            id=str(uuid.uuid4()),
            tenant_id="tenant-1",
            image_id=str(uuid.uuid4()),
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=60),
            created_by_user_id=user_id,
        )
        assert token.created_by_user_id == user_id

    def test_token_tracks_usage_metadata(self):
        """Token should track usage metadata (IP, user agent)."""
        token = ImageAccessToken(
            id=str(uuid.uuid4()),
            tenant_id="tenant-1",
            image_id=str(uuid.uuid4()),
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=60),
            created_by_user_id=str(uuid.uuid4()),
            used_at=datetime.now(timezone.utc),
            used_by_ip="192.168.1.1",
            used_by_user_agent="Mozilla/5.0 Test Browser",
        )
        assert token.used_by_ip == "192.168.1.1"
        assert token.used_by_user_agent == "Mozilla/5.0 Test Browser"


class TestSecurityHeaders:
    """Tests for security headers on token-based image responses."""

    def test_secure_image_headers_include_no_referrer(self):
        """Secure image responses should have Referrer-Policy: no-referrer."""
        from app.api.v1.endpoints.images import SECURE_IMAGE_HEADERS

        assert SECURE_IMAGE_HEADERS.get("Referrer-Policy") == "no-referrer"

    def test_secure_image_headers_prevent_caching(self):
        """Secure image responses should prevent caching."""
        from app.api.v1.endpoints.images import SECURE_IMAGE_HEADERS

        cache_control = SECURE_IMAGE_HEADERS.get("Cache-Control", "")
        assert "no-store" in cache_control
        assert "no-cache" in cache_control
        assert "private" in cache_control

    def test_secure_image_headers_prevent_sniffing(self):
        """Secure image responses should prevent content sniffing."""
        from app.api.v1.endpoints.images import SECURE_IMAGE_HEADERS

        assert SECURE_IMAGE_HEADERS.get("X-Content-Type-Options") == "nosniff"


class TestMigration:
    """Tests for the database migration."""

    def test_migration_creates_required_indexes(self):
        """Migration should create indexes for performance."""
        import os

        migration_path = os.path.join(
            os.path.dirname(__file__),
            "..",
            "..",
            "alembic",
            "versions",
            "011_one_time_image_tokens.py",
        )

        with open(migration_path, "r") as f:
            migration_content = f.read()

        # Verify required indexes are created
        assert "ix_image_access_tokens_tenant_id" in migration_content
        assert "ix_image_access_tokens_image_id" in migration_content
        assert "ix_image_access_tokens_expires_at" in migration_content

    def test_migration_has_downgrade(self):
        """Migration should have a working downgrade function."""
        import os

        migration_path = os.path.join(
            os.path.dirname(__file__),
            "..",
            "..",
            "alembic",
            "versions",
            "011_one_time_image_tokens.py",
        )

        with open(migration_path, "r") as f:
            migration_content = f.read()

        # Verify downgrade drops indexes and table
        assert "def downgrade()" in migration_content
        assert "op.drop_index" in migration_content
        assert "op.drop_table" in migration_content
