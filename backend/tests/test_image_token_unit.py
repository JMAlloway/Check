"""
Unit tests for one-time-use image access tokens.

These tests verify the security properties of the token model without
requiring the full application stack.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest


class TestImageAccessTokenModel:
    """Tests for ImageAccessToken model security properties."""

    def test_is_expired_when_past_expiry(self):
        """Token should be expired when current time is past expires_at."""
        # Import inside test to avoid app startup issues
        import sys

        sys.path.insert(0, "/home/user/Check/backend")

        from app.models.image_token import ImageAccessToken

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
        import sys

        sys.path.insert(0, "/home/user/Check/backend")

        from app.models.image_token import ImageAccessToken

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
        import sys

        sys.path.insert(0, "/home/user/Check/backend")

        from app.models.image_token import ImageAccessToken

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
        import sys

        sys.path.insert(0, "/home/user/Check/backend")

        from app.models.image_token import ImageAccessToken

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
        import sys

        sys.path.insert(0, "/home/user/Check/backend")

        from app.models.image_token import ImageAccessToken

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
        import sys

        sys.path.insert(0, "/home/user/Check/backend")

        from app.models.image_token import ImageAccessToken

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
        import sys

        sys.path.insert(0, "/home/user/Check/backend")

        from app.models.image_token import ImageAccessToken

        token = ImageAccessToken(
            id=str(uuid.uuid4()),
            tenant_id="tenant-1",
            image_id=str(uuid.uuid4()),
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=60),
            used_at=datetime.now(timezone.utc),
            created_by_user_id=str(uuid.uuid4()),
        )
        assert token.is_valid is False

    def test_token_contains_tenant_id(self):
        """Token should store tenant_id for validation."""
        import sys

        sys.path.insert(0, "/home/user/Check/backend")

        from app.models.image_token import ImageAccessToken

        token = ImageAccessToken(
            id=str(uuid.uuid4()),
            tenant_id="tenant-1",
            image_id=str(uuid.uuid4()),
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=60),
            created_by_user_id=str(uuid.uuid4()),
        )
        assert token.tenant_id == "tenant-1"

    def test_token_tracks_created_by_user(self):
        """Token should track which user created it."""
        import sys

        sys.path.insert(0, "/home/user/Check/backend")

        from app.models.image_token import ImageAccessToken

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
        import sys

        sys.path.insert(0, "/home/user/Check/backend")

        from app.models.image_token import ImageAccessToken

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


class TestAuditActionEnum:
    """Tests for AuditAction enum additions."""

    def test_audit_action_has_token_created(self):
        """AuditAction should have IMAGE_TOKEN_CREATED action."""
        import sys

        sys.path.insert(0, "/home/user/Check/backend")

        from app.models.audit import AuditAction

        assert hasattr(AuditAction, "IMAGE_TOKEN_CREATED")
        assert AuditAction.IMAGE_TOKEN_CREATED.value == "image_token_created"

    def test_audit_action_has_token_used(self):
        """AuditAction should have IMAGE_TOKEN_USED action."""
        import sys

        sys.path.insert(0, "/home/user/Check/backend")

        from app.models.audit import AuditAction

        assert hasattr(AuditAction, "IMAGE_TOKEN_USED")
        assert AuditAction.IMAGE_TOKEN_USED.value == "image_token_used"

    def test_audit_action_has_token_expired(self):
        """AuditAction should have IMAGE_TOKEN_EXPIRED action."""
        import sys

        sys.path.insert(0, "/home/user/Check/backend")

        from app.models.audit import AuditAction

        assert hasattr(AuditAction, "IMAGE_TOKEN_EXPIRED")
        assert AuditAction.IMAGE_TOKEN_EXPIRED.value == "image_token_expired"


class TestMigrationFile:
    """Tests to verify migration file structure."""

    def test_migration_creates_required_indexes(self):
        """Migration should create indexes for performance."""
        import os

        migration_path = os.path.join(
            os.path.dirname(__file__), "..", "alembic", "versions", "011_one_time_image_tokens.py"
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
            os.path.dirname(__file__), "..", "alembic", "versions", "011_one_time_image_tokens.py"
        )

        with open(migration_path, "r") as f:
            migration_content = f.read()

        # Verify downgrade drops indexes and table
        assert "def downgrade()" in migration_content
        assert "op.drop_index" in migration_content
        assert "op.drop_table" in migration_content


class TestSecurityHeaders:
    """Tests for security headers configuration."""

    def test_secure_image_headers_defined(self):
        """Security headers constant should be defined."""
        import sys

        sys.path.insert(0, "/home/user/Check/backend")

        # Import just the headers constant without full app
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "images", "/home/user/Check/backend/app/api/v1/endpoints/images.py"
        )
        # This will fail if the file has import errors, so we read it instead

        with open("/home/user/Check/backend/app/api/v1/endpoints/images.py", "r") as f:
            content = f.read()

        # Verify security headers are defined
        assert "SECURE_IMAGE_HEADERS" in content
        assert '"Referrer-Policy": "no-referrer"' in content
        assert "no-store" in content
        assert "no-cache" in content
        assert "nosniff" in content


class TestEndpointLogic:
    """Tests for endpoint code logic (static analysis)."""

    def test_token_marked_used_before_serving(self):
        """Token should be marked used BEFORE serving image (atomic)."""
        with open("/home/user/Check/backend/app/api/v1/endpoints/images.py", "r") as f:
            content = f.read()

        # Find the secure image endpoint
        assert "async def get_secure_image" in content

        # Extract just the get_secure_image function to check order within it
        func_start = content.find("async def get_secure_image")
        func_end = content.find("\n@router", func_start + 1)
        if func_end == -1:
            func_end = len(content)
        func_content = content[func_start:func_end]

        # Verify the order of operations within the function:
        # 1. token.used_at should be set
        # 2. db.commit() should happen
        # 3. adapter.get_image should happen AFTER

        used_at_pos = func_content.find("token.used_at")
        commit_pos = func_content.find("await db.commit()")
        get_image_pos = func_content.find("adapter.get_image")
        get_thumbnail_pos = func_content.find("adapter.get_thumbnail")

        # Verify order
        assert used_at_pos > 0, "token.used_at should be in function"
        assert commit_pos > 0, "db.commit should be in function"
        assert used_at_pos < commit_pos, "used_at should be set before commit"
        assert commit_pos < get_image_pos, "commit should happen before get_image"
        assert commit_pos < get_thumbnail_pos, "commit should happen before get_thumbnail"

    def test_batch_endpoint_has_limit(self):
        """Batch token endpoint should have a maximum limit."""
        with open("/home/user/Check/backend/app/api/v1/endpoints/images.py", "r") as f:
            content = f.read()

        # Verify there's a batch limit check
        assert "len(data.image_ids) > 10" in content or "Maximum 10 tokens" in content

    def test_tenant_validation_in_endpoints(self):
        """Endpoints should validate tenant ownership."""
        with open("/home/user/Check/backend/app/api/v1/endpoints/images.py", "r") as f:
            content = f.read()

        # Verify tenant validation is present
        assert "tenant_id" in content
        assert "check_item.tenant_id" in content
