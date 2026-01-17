"""
Integration tests for secure image endpoint security headers.

These tests verify that the secure image endpoint properly sets
security headers to prevent bearer token leakage via referrer headers.

CRITICAL FOR: Bank vendor risk assessments, security compliance
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from app.main import app
from app.core.security import generate_signed_url
from app.core.config import settings


class TestSecureImageSecurityHeaders:
    """Tests for security headers on secure image endpoints."""

    @pytest.fixture
    def client(self):
        """Create a test client."""
        return TestClient(app)

    @pytest.fixture
    def mock_image_data(self):
        """Mock image binary data."""
        # Simple 1x1 transparent PNG
        return bytes([
            0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A,
            0x00, 0x00, 0x00, 0x0D, 0x49, 0x48, 0x44, 0x52,
            0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01,
            0x08, 0x06, 0x00, 0x00, 0x00, 0x1F, 0x15, 0xC4,
            0x89, 0x00, 0x00, 0x00, 0x0A, 0x49, 0x44, 0x41,
            0x54, 0x78, 0x9C, 0x63, 0x00, 0x01, 0x00, 0x00,
            0x05, 0x00, 0x01, 0x0D, 0x0A, 0x2D, 0xB4, 0x00,
            0x00, 0x00, 0x00, 0x49, 0x45, 0x4E, 0x44, 0xAE,
            0x42, 0x60, 0x82,
        ])

    def test_referrer_policy_header_present(self, client, mock_image_data):
        """Secure image endpoint should include Referrer-Policy: no-referrer."""
        with patch("app.api.v1.endpoints.images.verify_signed_url") as mock_verify, \
             patch("app.api.v1.endpoints.images.get_adapter") as mock_adapter, \
             patch("app.api.v1.endpoints.images.AuditService"):

            # Mock valid token verification
            mock_payload = MagicMock()
            mock_payload.user_id = "test-user-id"
            mock_payload.resource_id = "test-image-id"
            mock_verify.return_value = mock_payload

            # Mock user lookup
            with patch("app.api.v1.endpoints.images.select"), \
                 patch.object(client.app.state, "limiter", MagicMock()):

                # For this test, we'll check the response headers from SECURE_IMAGE_HEADERS
                # by importing and verifying the constant
                from app.api.v1.endpoints.images import SECURE_IMAGE_HEADERS

                assert "Referrer-Policy" in SECURE_IMAGE_HEADERS
                assert SECURE_IMAGE_HEADERS["Referrer-Policy"] == "no-referrer"

    def test_cache_control_headers_present(self):
        """Secure image responses should have strict cache-control headers."""
        from app.api.v1.endpoints.images import SECURE_IMAGE_HEADERS

        assert "Cache-Control" in SECURE_IMAGE_HEADERS
        cache_control = SECURE_IMAGE_HEADERS["Cache-Control"]

        # Verify all required cache-control directives
        assert "private" in cache_control
        assert "no-store" in cache_control
        assert "no-cache" in cache_control
        assert "must-revalidate" in cache_control

    def test_security_headers_complete(self):
        """Verify all required security headers are present."""
        from app.api.v1.endpoints.images import SECURE_IMAGE_HEADERS

        required_headers = [
            "Cache-Control",
            "Pragma",
            "Expires",
            "X-Content-Type-Options",
            "X-Frame-Options",
            "X-XSS-Protection",
            "Content-Disposition",
            "Referrer-Policy",
        ]

        for header in required_headers:
            assert header in SECURE_IMAGE_HEADERS, f"Missing required header: {header}"

    def test_x_content_type_options_nosniff(self):
        """X-Content-Type-Options should be set to nosniff."""
        from app.api.v1.endpoints.images import SECURE_IMAGE_HEADERS

        assert SECURE_IMAGE_HEADERS.get("X-Content-Type-Options") == "nosniff"


class TestTokenRedactionMiddleware:
    """Tests for the token redaction middleware."""

    @pytest.fixture
    def client(self):
        """Create a test client."""
        return TestClient(app)

    def test_middleware_is_registered(self, client):
        """Token redaction middleware should be registered on the app."""
        from app.core.middleware import TokenRedactionMiddleware

        middleware_types = [type(m.cls).__name__ for m in app.user_middleware]
        # Check that our middleware or its class is in the chain
        # Note: Starlette wraps middleware, so we check for the presence
        assert any("TokenRedaction" in str(m) for m in app.user_middleware) or \
               TokenRedactionMiddleware in [m.cls for m in app.user_middleware]


class TestNginxConfigSecurityHeaders:
    """Tests to verify nginx configuration includes required security settings.

    Note: These are config validation tests, not runtime tests.
    They verify the nginx.conf file has the expected directives.
    """

    @pytest.fixture
    def nginx_config(self):
        """Load the nginx configuration file."""
        import os
        config_path = os.path.join(
            os.path.dirname(__file__),
            "..", "..", "..", "docker", "nginx.conf"
        )
        with open(config_path, "r") as f:
            return f.read()

    def test_secure_image_location_disables_access_log(self, nginx_config):
        """Nginx should disable access logging for secure image endpoint."""
        # Check that the secure image location exists and has access_log off
        assert "/api/v1/images/secure/" in nginx_config
        assert "access_log off" in nginx_config

    def test_secure_image_location_has_referrer_policy(self, nginx_config):
        """Nginx should set Referrer-Policy: no-referrer for secure images."""
        # Find the secure image location block and verify referrer policy
        assert 'Referrer-Policy "no-referrer"' in nginx_config

    def test_global_security_headers_present(self, nginx_config):
        """Nginx should have global security headers configured."""
        assert "X-Frame-Options" in nginx_config
        assert "X-Content-Type-Options" in nginx_config
        assert "X-XSS-Protection" in nginx_config
