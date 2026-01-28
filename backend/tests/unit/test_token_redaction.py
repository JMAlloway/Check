"""Unit tests for token redaction middleware and logging filters.

These tests verify that bearer tokens in signed image URLs are properly
redacted from logs and error messages to prevent token leakage.
"""

import logging

import pytest
from app.core.middleware import (
    SECURE_IMAGE_PATH_PATTERN,
    TOKEN_REDACTED,
    TokenRedactionFilter,
    is_secure_image_path,
    redact_exception_args,
    redact_token_from_path,
)


class TestRedactTokenFromPath:
    """Tests for the redact_token_from_path function."""

    def test_redacts_jwt_token_in_secure_image_path(self):
        """Should redact JWT tokens from secure image URLs."""
        # Typical JWT token format: header.payload.signature
        path = "/api/v1/images/secure/eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
        result = redact_token_from_path(path)
        assert result == f"/api/v1/images/secure/{TOKEN_REDACTED}"
        assert "eyJ" not in result

    def test_redacts_token_with_underscores(self):
        """Should handle tokens with underscores (base64url encoding)."""
        path = "/api/v1/images/secure/eyJhbG_test-token_value.payload.sig"
        result = redact_token_from_path(path)
        assert result == f"/api/v1/images/secure/{TOKEN_REDACTED}"

    def test_preserves_non_secure_image_paths(self):
        """Should not modify paths that don't match the pattern."""
        paths = [
            "/api/v1/users/123",
            "/api/v1/checks",
            "/api/v1/images/abc123",  # Regular image path (not secure)
            "/health",
            "/",
        ]
        for path in paths:
            assert redact_token_from_path(path) == path

    def test_redacts_token_in_longer_url(self):
        """Should redact tokens even with query params (though not expected)."""
        path = "/api/v1/images/secure/token123.abc.xyz"
        result = redact_token_from_path(path)
        assert "token123" not in result
        assert TOKEN_REDACTED in result

    def test_handles_empty_string(self):
        """Should handle empty string gracefully."""
        assert redact_token_from_path("") == ""

    def test_handles_partial_match(self):
        """Should not redact if path doesn't fully match pattern."""
        # Path prefix but no token
        path = "/api/v1/images/secure/"
        result = redact_token_from_path(path)
        # No token to redact, path unchanged
        assert result == path


class TestIsSecureImagePath:
    """Tests for the is_secure_image_path function."""

    def test_identifies_secure_image_paths(self):
        """Should return True for secure image paths."""
        assert is_secure_image_path("/api/v1/images/secure/sometoken") is True
        assert is_secure_image_path("/api/v1/images/secure/") is True

    def test_rejects_non_secure_paths(self):
        """Should return False for non-secure paths."""
        assert is_secure_image_path("/api/v1/images/123") is False
        assert is_secure_image_path("/api/v1/users") is False
        assert is_secure_image_path("/health") is False


class TestTokenRedactionFilter:
    """Tests for the TokenRedactionFilter logging filter."""

    def test_redacts_token_in_log_message(self, caplog):
        """Should redact tokens from log messages."""
        filter_instance = TokenRedactionFilter()
        logger = logging.getLogger("test.redaction")
        logger.addFilter(filter_instance)

        with caplog.at_level(logging.INFO):
            logger.info("Request to /api/v1/images/secure/eyJtoken.payload.sig returned 200")

        # Check that the token was redacted
        assert "eyJtoken" not in caplog.text
        assert TOKEN_REDACTED in caplog.text

    def test_redacts_token_in_log_args_tuple(self, caplog):
        """Should redact tokens from log message args (tuple format)."""
        filter_instance = TokenRedactionFilter()
        logger = logging.getLogger("test.redaction.args")
        logger.addFilter(filter_instance)

        with caplog.at_level(logging.INFO):
            logger.info("Path: %s", "/api/v1/images/secure/secret.token.value")

        assert "secret.token.value" not in caplog.text
        assert TOKEN_REDACTED in caplog.text

    def test_preserves_non_sensitive_messages(self, caplog):
        """Should not modify messages without tokens."""
        filter_instance = TokenRedactionFilter()
        logger = logging.getLogger("test.redaction.normal")
        logger.addFilter(filter_instance)

        with caplog.at_level(logging.INFO):
            logger.info("Normal request to /api/v1/users/123")

        assert "/api/v1/users/123" in caplog.text

    def test_allows_record_through(self):
        """Filter should always return True to allow record through."""
        filter_instance = TokenRedactionFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="test message",
            args=(),
            exc_info=None,
        )
        assert filter_instance.filter(record) is True


class TestRedactExceptionArgs:
    """Tests for the redact_exception_args function."""

    def test_redacts_token_in_exception_message(self):
        """Should redact tokens from exception args."""
        exc = ValueError("Failed to process /api/v1/images/secure/secret.token.here")
        result = redact_exception_args(exc)

        assert "secret.token.here" not in str(result)
        assert TOKEN_REDACTED in str(result)

    def test_preserves_non_sensitive_exceptions(self):
        """Should not modify exceptions without tokens."""
        exc = ValueError("Database connection failed")
        result = redact_exception_args(exc)
        assert str(result) == "Database connection failed"

    def test_handles_exception_with_multiple_args(self):
        """Should handle exceptions with multiple arguments."""
        exc = Exception(
            "Error 1",
            "/api/v1/images/secure/token.abc.xyz",
            "Error 3",
        )
        result = redact_exception_args(exc)

        assert "token.abc.xyz" not in str(result.args)
        assert TOKEN_REDACTED in str(result.args)
        assert "Error 1" in str(result.args)
        assert "Error 3" in str(result.args)

    def test_handles_exception_with_no_args(self):
        """Should handle exceptions with no arguments gracefully."""
        exc = Exception()
        result = redact_exception_args(exc)
        assert result.args == ()


class TestSecureImagePathPattern:
    """Tests for the regex pattern itself."""

    def test_pattern_matches_jwt_format(self):
        """Pattern should match typical JWT token format."""
        path = "/api/v1/images/secure/header.payload.signature"
        match = SECURE_IMAGE_PATH_PATTERN.search(path)
        assert match is not None
        assert match.group(1) == "/api/v1/images/secure/"
        assert match.group(2) == "header.payload.signature"

    def test_pattern_matches_base64url_characters(self):
        """Pattern should match base64url characters (A-Z, a-z, 0-9, -, _)."""
        path = "/api/v1/images/secure/ABC_xyz-123.DEF_uvw-456.GHI_rst-789"
        match = SECURE_IMAGE_PATH_PATTERN.search(path)
        assert match is not None

    def test_pattern_does_not_match_other_api_paths(self):
        """Pattern should not match non-secure-image paths."""
        paths = [
            "/api/v1/images/12345",
            "/api/v1/users/secure/token",
            "/api/v1/secure/images/token",
        ]
        for path in paths:
            match = SECURE_IMAGE_PATH_PATTERN.search(path)
            assert match is None, f"Should not match: {path}"
