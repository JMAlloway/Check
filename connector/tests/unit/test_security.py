"""
Unit tests for JWT validation and path security.
"""
import time
import uuid

import jwt
import pytest

from app.core.security import (
    JWTValidator,
    JWTClaims,
    PathValidator,
    ReplayCache,
)


class TestReplayCache:
    """Tests for the replay cache."""

    def test_add_and_contains(self):
        """Test adding and checking JTIs."""
        cache = ReplayCache(default_ttl=60)
        jti = str(uuid.uuid4())

        assert not cache.contains(jti)
        cache.add(jti)
        assert cache.contains(jti)

    def test_expiration(self):
        """Test that expired entries are removed."""
        cache = ReplayCache(default_ttl=1)
        jti = str(uuid.uuid4())

        cache.add(jti, time.time() - 1)  # Already expired
        assert not cache.contains(jti)

    def test_lru_eviction(self):
        """Test LRU eviction when at capacity."""
        cache = ReplayCache(max_size=3, default_ttl=60)

        cache.add("jti1")
        cache.add("jti2")
        cache.add("jti3")
        cache.add("jti4")  # Should evict jti1

        assert not cache.contains("jti1")
        assert cache.contains("jti2")
        assert cache.contains("jti3")
        assert cache.contains("jti4")


class TestJWTValidator:
    """Tests for JWT validation."""

    def test_validate_valid_token(self, public_key, valid_token):
        """Test validation of a valid token."""
        validator = JWTValidator(
            public_key=public_key,
            issuer="check-review-saas",
            required_roles=["image_viewer"]
        )

        is_valid, claims, error = validator.validate(valid_token)

        assert is_valid
        assert claims is not None
        assert claims.sub == "test-user"
        assert claims.org_id == "test-org"
        assert "image_viewer" in claims.roles
        assert error is None

    def test_validate_expired_token(self, public_key, expired_token):
        """Test validation of an expired token."""
        validator = JWTValidator(
            public_key=public_key,
            issuer="check-review-saas"
        )

        is_valid, claims, error = validator.validate(expired_token)

        assert not is_valid
        assert claims is None
        assert "expired" in error.lower()

    def test_validate_invalid_signature(self, valid_token):
        """Test validation with wrong public key."""
        # Use a different key
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.backends import default_backend

        wrong_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend()
        ).public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        ).decode()

        validator = JWTValidator(
            public_key=wrong_key,
            issuer="check-review-saas"
        )

        is_valid, claims, error = validator.validate(valid_token)

        assert not is_valid
        assert claims is None
        assert "signature" in error.lower()

    def test_replay_protection(self, public_key, private_key):
        """Test that replayed tokens are rejected."""
        validator = JWTValidator(
            public_key=public_key,
            issuer="check-review-saas",
            replay_cache_ttl=60
        )

        # Create a token with fixed JTI
        now = int(time.time())
        payload = {
            "sub": "test-user",
            "org_id": "test-org",
            "roles": ["image_viewer"],
            "iat": now,
            "exp": now + 120,
            "jti": "fixed-jti-123",
            "iss": "check-review-saas",
        }
        token = jwt.encode(payload, private_key, algorithm="RS256")

        # First use should succeed
        is_valid1, _, _ = validator.validate(token)
        assert is_valid1

        # Replay should fail
        is_valid2, _, error = validator.validate(token)
        assert not is_valid2
        assert "replay" in error.lower()

    def test_check_roles_success(self, public_key, valid_token):
        """Test role checking with valid roles."""
        validator = JWTValidator(
            public_key=public_key,
            issuer="check-review-saas",
            required_roles=["image_viewer", "admin"]
        )

        is_valid, claims, _ = validator.validate(valid_token)
        assert is_valid

        has_access, error = validator.check_roles(claims)
        assert has_access
        assert error is None

    def test_check_roles_failure(self, public_key, token_missing_roles):
        """Test role checking with missing roles."""
        validator = JWTValidator(
            public_key=public_key,
            issuer="check-review-saas",
            required_roles=["image_viewer"]
        )

        is_valid, claims, _ = validator.validate(token_missing_roles)
        assert is_valid

        has_access, error = validator.check_roles(claims)
        assert not has_access
        assert "missing required role" in error.lower()


class TestPathValidator:
    """Tests for path validation."""

    def test_validate_allowed_path(self):
        """Test validation of allowed paths."""
        validator = PathValidator(allowed_roots=[
            "\\\\tn-director-pro\\Checks\\Transit\\",
            "\\\\tn-director-pro\\Checks\\OnUs\\"
        ])

        is_valid, error = validator.validate(
            "\\\\tn-director-pro\\Checks\\Transit\\V406\\580\\12374628.IMG"
        )

        assert is_valid
        assert error is None

    def test_validate_blocked_path(self):
        """Test validation of paths outside allowed roots."""
        validator = PathValidator(allowed_roots=[
            "\\\\tn-director-pro\\Checks\\Transit\\"
        ])

        is_valid, error = validator.validate(
            "\\\\other-server\\Checks\\12374628.IMG"
        )

        assert not is_valid
        assert "not in allowed" in error.lower()

    def test_block_path_traversal(self):
        """Test that path traversal is blocked."""
        validator = PathValidator(allowed_roots=[
            "\\\\tn-director-pro\\Checks\\Transit\\"
        ])

        is_valid, error = validator.validate(
            "\\\\tn-director-pro\\Checks\\Transit\\..\\..\\secrets.txt"
        )

        assert not is_valid
        assert "traversal" in error.lower()

    def test_empty_path(self):
        """Test validation of empty path."""
        validator = PathValidator(allowed_roots=[
            "\\\\tn-director-pro\\Checks\\Transit\\"
        ])

        is_valid, error = validator.validate("")

        assert not is_valid
        assert "empty" in error.lower()

    def test_hash_path(self):
        """Test path hashing for audit logs."""
        validator = PathValidator()

        hash1 = validator.hash_path("\\\\server\\share\\file.img")
        hash2 = validator.hash_path("\\\\server\\share\\file.img")
        hash3 = validator.hash_path("\\\\server\\share\\other.img")

        assert hash1 == hash2  # Same path = same hash
        assert hash1 != hash3  # Different path = different hash
        assert len(hash1) == 64  # SHA256 hex digest

    def test_case_insensitive(self):
        """Test that path comparison is case-insensitive."""
        validator = PathValidator(allowed_roots=[
            "\\\\TN-DIRECTOR-PRO\\Checks\\Transit\\"
        ])

        is_valid, _ = validator.validate(
            "\\\\tn-director-pro\\checks\\transit\\file.img"
        )

        assert is_valid


class TestJWTClaims:
    """Tests for JWT claims dataclass."""

    def test_has_role(self):
        """Test has_role method."""
        claims = JWTClaims(
            sub="user",
            org_id="org",
            roles=["admin", "viewer"],
            exp=0,
            iat=0,
            jti="123",
            iss="test"
        )

        assert claims.has_role("admin")
        assert claims.has_role("viewer")
        assert not claims.has_role("other")

    def test_has_any_role(self):
        """Test has_any_role method."""
        claims = JWTClaims(
            sub="user",
            org_id="org",
            roles=["admin"],
            exp=0,
            iat=0,
            jti="123",
            iss="test"
        )

        assert claims.has_any_role(["admin", "viewer"])
        assert claims.has_any_role(["admin"])
        assert not claims.has_any_role(["viewer", "other"])
