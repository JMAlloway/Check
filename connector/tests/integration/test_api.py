"""
Integration tests for the Bank-Side Connector API.
"""
import io
import os
import sys

import pytest
from PIL import Image

# Add the app to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


class TestHealthEndpoint:
    """Tests for the /healthz endpoint."""

    @pytest.mark.asyncio
    async def test_health_check_returns_200(self, mock_settings):
        """Test that health check returns 200."""
        from app.main import app
        from httpx import ASGITransport, AsyncClient

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test"
        ) as client:
            response = await client.get("/healthz")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] in ["healthy", "degraded"]
        assert data["mode"] == "DEMO"
        assert "connector_id" in data
        assert "components" in data
        assert "cache" in data

    @pytest.mark.asyncio
    async def test_health_check_includes_version(self, mock_settings):
        """Test that health check includes version."""
        from app.main import app
        from httpx import ASGITransport, AsyncClient

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test"
        ) as client:
            response = await client.get("/healthz")

        data = response.json()
        assert "version" in data


class TestImageByHandleEndpoint:
    """Tests for the /v1/images/by-handle endpoint."""

    @pytest.mark.asyncio
    async def test_requires_authentication(self, mock_settings):
        """Test that endpoint requires authentication."""
        from app.main import app
        from httpx import ASGITransport, AsyncClient

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test"
        ) as client:
            response = await client.get(
                "/v1/images/by-handle",
                params={"path": "\\\\tn-director-pro\\Checks\\Transit\\V406\\580\\12374628.IMG"}
            )

        assert response.status_code == 401
        data = response.json()
        assert data["detail"]["error_code"] == "AUTH_FAILED"

    @pytest.mark.asyncio
    async def test_rejects_invalid_token(self, mock_settings):
        """Test that invalid tokens are rejected."""
        from app.main import app
        from httpx import ASGITransport, AsyncClient

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test"
        ) as client:
            response = await client.get(
                "/v1/images/by-handle",
                params={"path": "\\\\tn-director-pro\\Checks\\Transit\\V406\\580\\12374628.IMG"},
                headers={"Authorization": "Bearer invalid-token"}
            )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_returns_image_with_valid_token(self, mock_settings, valid_token):
        """Test that valid token returns image."""
        from app.main import app
        from httpx import ASGITransport, AsyncClient

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test"
        ) as client:
            response = await client.get(
                "/v1/images/by-handle",
                params={
                    "path": "\\\\tn-director-pro\\Checks\\Transit\\V406\\580\\12374628.IMG",
                    "side": "front"
                },
                headers={"Authorization": f"Bearer {valid_token}"}
            )

        assert response.status_code == 200
        assert response.headers["content-type"] == "image/png"

        # Verify it's a valid PNG
        img = Image.open(io.BytesIO(response.content))
        assert img.format == "PNG"

    @pytest.mark.asyncio
    async def test_returns_back_image(self, mock_settings, valid_token):
        """Test that back side can be retrieved."""
        from app.main import app
        from httpx import ASGITransport, AsyncClient

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test"
        ) as client:
            response = await client.get(
                "/v1/images/by-handle",
                params={
                    "path": "\\\\tn-director-pro\\Checks\\Transit\\V406\\580\\12374628.IMG",
                    "side": "back"
                },
                headers={"Authorization": f"Bearer {valid_token}"}
            )

        assert response.status_code == 200
        assert response.headers["content-type"] == "image/png"

    @pytest.mark.asyncio
    async def test_no_back_image_returns_404(self, mock_settings, valid_token):
        """Test that requesting back of single-page image returns 404."""
        from app.main import app
        from httpx import ASGITransport, AsyncClient

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test"
        ) as client:
            response = await client.get(
                "/v1/images/by-handle",
                params={
                    "path": "\\\\tn-director-pro\\Checks\\Transit\\V406\\580\\12374630.IMG",
                    "side": "back"
                },
                headers={"Authorization": f"Bearer {valid_token}"}
            )

        assert response.status_code == 404
        data = response.json()
        assert data["detail"]["error_code"] == "NO_BACK_IMAGE"

    @pytest.mark.asyncio
    async def test_blocked_path_returns_403(self, mock_settings, valid_token):
        """Test that paths outside allowed roots are blocked."""
        from app.main import app
        from httpx import ASGITransport, AsyncClient

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test"
        ) as client:
            response = await client.get(
                "/v1/images/by-handle",
                params={
                    "path": "\\\\other-server\\Shares\\file.IMG",
                    "side": "front"
                },
                headers={"Authorization": f"Bearer {valid_token}"}
            )

        assert response.status_code == 403
        data = response.json()
        assert data["detail"]["error_code"] == "PATH_NOT_ALLOWED"

    @pytest.mark.asyncio
    async def test_not_found_returns_404(self, mock_settings, valid_token):
        """Test that non-existent images return 404."""
        from app.main import app
        from httpx import ASGITransport, AsyncClient

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test"
        ) as client:
            response = await client.get(
                "/v1/images/by-handle",
                params={
                    "path": "\\\\tn-director-pro\\Checks\\Transit\\V406\\580\\nonexistent.IMG",
                    "side": "front"
                },
                headers={"Authorization": f"Bearer {valid_token}"}
            )

        assert response.status_code == 404
        data = response.json()
        assert data["detail"]["error_code"] == "NOT_FOUND"

    @pytest.mark.asyncio
    async def test_includes_correlation_id(self, mock_settings, valid_token):
        """Test that response includes correlation ID."""
        from app.main import app
        from httpx import ASGITransport, AsyncClient

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test"
        ) as client:
            response = await client.get(
                "/v1/images/by-handle",
                params={
                    "path": "\\\\tn-director-pro\\Checks\\Transit\\V406\\580\\12374628.IMG",
                    "side": "front"
                },
                headers={
                    "Authorization": f"Bearer {valid_token}",
                    "X-Correlation-ID": "test-correlation-123"
                }
            )

        assert response.status_code == 200
        assert response.headers.get("x-correlation-id") == "test-correlation-123"


class TestImageByItemEndpoint:
    """Tests for the /v1/images/by-item endpoint."""

    @pytest.mark.asyncio
    async def test_returns_image_by_trace_and_date(self, mock_settings, valid_token):
        """Test retrieving image by trace number and date."""
        from app.main import app
        from httpx import ASGITransport, AsyncClient

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test"
        ) as client:
            response = await client.get(
                "/v1/images/by-item",
                params={
                    "trace": "12374628",
                    "date": "2024-01-15",
                    "side": "front"
                },
                headers={"Authorization": f"Bearer {valid_token}"}
            )

        assert response.status_code == 200
        assert response.headers["content-type"] == "image/png"

    @pytest.mark.asyncio
    async def test_item_not_found_returns_404(self, mock_settings, valid_token):
        """Test that non-existent items return 404."""
        from app.main import app
        from httpx import ASGITransport, AsyncClient

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test"
        ) as client:
            response = await client.get(
                "/v1/images/by-item",
                params={
                    "trace": "99999999",
                    "date": "2024-01-15",
                    "side": "front"
                },
                headers={"Authorization": f"Bearer {valid_token}"}
            )

        assert response.status_code == 404
        data = response.json()
        assert data["detail"]["error_code"] == "NOT_FOUND"


class TestItemLookupEndpoint:
    """Tests for the /v1/items/lookup endpoint."""

    @pytest.mark.asyncio
    async def test_returns_item_metadata(self, mock_settings, valid_token):
        """Test retrieving item metadata."""
        from app.main import app
        from httpx import ASGITransport, AsyncClient

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test"
        ) as client:
            response = await client.get(
                "/v1/items/lookup",
                params={
                    "trace": "12374628",
                    "date": "2024-01-15"
                },
                headers={"Authorization": f"Bearer {valid_token}"}
            )

        assert response.status_code == 200
        data = response.json()
        assert data["trace_number"] == "12374628"
        assert data["check_date"] == "2024-01-15"
        assert data["amount_cents"] == 125000
        assert data["check_number"] == "1234"
        assert data["account_last4"] == "5678"
        assert data["is_onus"] is False
        assert data["has_back_image"] is True

    @pytest.mark.asyncio
    async def test_item_not_found_returns_404(self, mock_settings, valid_token):
        """Test that non-existent items return 404."""
        from app.main import app
        from httpx import ASGITransport, AsyncClient

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test"
        ) as client:
            response = await client.get(
                "/v1/items/lookup",
                params={
                    "trace": "99999999",
                    "date": "2024-01-15"
                },
                headers={"Authorization": f"Bearer {valid_token}"}
            )

        assert response.status_code == 404


class TestSecurityHeaders:
    """Tests for security headers."""

    @pytest.mark.asyncio
    async def test_image_response_has_security_headers(self, mock_settings, valid_token):
        """Test that image responses include security headers."""
        from app.main import app
        from httpx import ASGITransport, AsyncClient

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test"
        ) as client:
            response = await client.get(
                "/v1/images/by-handle",
                params={
                    "path": "\\\\tn-director-pro\\Checks\\Transit\\V406\\580\\12374628.IMG",
                    "side": "front"
                },
                headers={"Authorization": f"Bearer {valid_token}"}
            )

        assert response.status_code == 200

        # Check security headers
        assert "no-store" in response.headers.get("cache-control", "")
        assert response.headers.get("x-content-type-options") == "nosniff"
        assert response.headers.get("x-frame-options") == "SAMEORIGIN"
