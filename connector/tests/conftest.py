"""
Pytest fixtures for Bank-Side Connector tests.
"""
import io
import json
import os
import tempfile
import time
import uuid
from datetime import datetime
from pathlib import Path

import jwt
import pytest
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from PIL import Image

# =============================================================================
# RSA Key Pair Fixtures
# =============================================================================

@pytest.fixture(scope="session")
def rsa_key_pair():
    """Generate an RSA key pair for testing."""
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend()
    )

    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    ).decode()

    public_key = private_key.public_key()
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode()

    return private_pem, public_pem


@pytest.fixture
def private_key(rsa_key_pair):
    """Get the private key."""
    return rsa_key_pair[0]


@pytest.fixture
def public_key(rsa_key_pair):
    """Get the public key."""
    return rsa_key_pair[1]


# =============================================================================
# JWT Token Fixtures
# =============================================================================

@pytest.fixture
def valid_token(private_key):
    """Generate a valid JWT token."""
    now = int(time.time())
    payload = {
        "sub": "test-user",
        "org_id": "test-org",
        "roles": ["image_viewer", "check_reviewer"],
        "iat": now,
        "exp": now + 120,
        "jti": str(uuid.uuid4()),
        "iss": "check-review-saas",
    }
    return jwt.encode(payload, private_key, algorithm="RS256")


@pytest.fixture
def expired_token(private_key):
    """Generate an expired JWT token."""
    now = int(time.time())
    payload = {
        "sub": "test-user",
        "org_id": "test-org",
        "roles": ["image_viewer"],
        "iat": now - 300,
        "exp": now - 60,  # Expired 60 seconds ago
        "jti": str(uuid.uuid4()),
        "iss": "check-review-saas",
    }
    return jwt.encode(payload, private_key, algorithm="RS256")


@pytest.fixture
def token_missing_roles(private_key):
    """Generate a token without required roles."""
    now = int(time.time())
    payload = {
        "sub": "test-user",
        "org_id": "test-org",
        "roles": ["other_role"],  # Not in IMAGE_ACCESS_ROLES
        "iat": now,
        "exp": now + 120,
        "jti": str(uuid.uuid4()),
        "iss": "check-review-saas",
    }
    return jwt.encode(payload, private_key, algorithm="RS256")


def make_token(private_key, **kwargs):
    """Helper to create tokens with custom claims."""
    now = int(time.time())
    defaults = {
        "sub": "test-user",
        "org_id": "test-org",
        "roles": ["image_viewer"],
        "iat": now,
        "exp": now + 120,
        "jti": str(uuid.uuid4()),
        "iss": "check-review-saas",
    }
    defaults.update(kwargs)
    return jwt.encode(defaults, private_key, algorithm="RS256")


# =============================================================================
# Demo Repository Fixtures
# =============================================================================

@pytest.fixture
def temp_demo_repo(tmp_path):
    """Create a temporary demo repository with test fixtures."""
    # Create directory structure
    transit_dir = tmp_path / "Checks" / "Transit" / "V406" / "580"
    onus_dir = tmp_path / "Checks" / "OnUs" / "V406" / "123"
    transit_dir.mkdir(parents=True)
    onus_dir.mkdir(parents=True)

    # Create test TIFF images
    def create_tiff(path: Path, pages: int = 2):
        """Create a multi-page TIFF file."""
        images = []
        for i in range(pages):
            img = Image.new("L", (800, 400), color=200)
            images.append(img)

        if len(images) > 1:
            images[0].save(
                path,
                format="TIFF",
                save_all=True,
                append_images=images[1:],
                compression="tiff_lzw"
            )
        else:
            images[0].save(path, format="TIFF", compression="tiff_lzw")

    # Create test images
    create_tiff(transit_dir / "12374628.IMG", pages=2)  # Multi-page
    create_tiff(transit_dir / "12374630.IMG", pages=1)  # Single-page
    create_tiff(onus_dir / "12374629.IMG", pages=2)

    # Create item index
    item_index = {
        "items": [
            {
                "trace_number": "12374628",
                "date": "2024-01-15",
                "image_path": "\\\\tn-director-pro\\Checks\\Transit\\V406\\580\\12374628.IMG",
                "amount_cents": 125000,
                "check_number": "1234",
                "account_last4": "5678",
                "is_onus": False,
                "is_multi_page": True,
                "has_back_image": True
            },
            {
                "trace_number": "12374629",
                "date": "2024-01-15",
                "image_path": "\\\\tn-director-pro\\Checks\\OnUs\\V406\\123\\12374629.IMG",
                "amount_cents": 50000,
                "check_number": "5678",
                "account_last4": "1234",
                "is_onus": True,
                "is_multi_page": True,
                "has_back_image": True
            },
            {
                "trace_number": "12374630",
                "date": "2024-01-16",
                "image_path": "\\\\tn-director-pro\\Checks\\Transit\\V406\\580\\12374630.IMG",
                "amount_cents": 250000,
                "check_number": "9012",
                "account_last4": "4321",
                "is_onus": False,
                "is_multi_page": False,
                "has_back_image": False
            },
        ]
    }

    index_path = tmp_path / "item_index.json"
    with open(index_path, "w") as f:
        json.dump(item_index, f)

    return tmp_path


# =============================================================================
# Settings Override Fixture
# =============================================================================

@pytest.fixture
def mock_settings(temp_demo_repo, public_key, monkeypatch):
    """Override settings for testing."""
    monkeypatch.setenv("CONNECTOR_MODE", "DEMO")
    monkeypatch.setenv("CONNECTOR_DEMO_REPO_ROOT", str(temp_demo_repo))
    monkeypatch.setenv("CONNECTOR_ITEM_INDEX_PATH", str(temp_demo_repo / "item_index.json"))
    monkeypatch.setenv("CONNECTOR_JWT_PUBLIC_KEY", public_key)
    monkeypatch.setenv("CONNECTOR_LOG_DIR", str(temp_demo_repo / "logs"))

    # Reset singletons
    from app.adapters import factory
    from app.core import security
    from app.core.config import Settings
    from app.services import cache

    # Create fresh settings
    settings = Settings()

    # Reset singletons
    security.reset_validators()
    factory.AdapterFactory._instance = None
    factory.AdapterFactory._adapters = None
    cache.reset_image_cache()

    return settings


# =============================================================================
# Test Image Fixtures
# =============================================================================

@pytest.fixture
def single_page_tiff():
    """Create a single-page TIFF in memory."""
    img = Image.new("L", (800, 400), color=200)
    output = io.BytesIO()
    img.save(output, format="TIFF", compression="tiff_lzw")
    output.seek(0)
    return output.read()


@pytest.fixture
def multi_page_tiff():
    """Create a multi-page TIFF in memory."""
    front = Image.new("L", (800, 400), color=200)
    back = Image.new("L", (800, 400), color=180)
    output = io.BytesIO()
    front.save(
        output,
        format="TIFF",
        save_all=True,
        append_images=[back],
        compression="tiff_lzw"
    )
    output.seek(0)
    return output.read()


@pytest.fixture
def png_image():
    """Create a PNG image in memory."""
    img = Image.new("RGB", (100, 100), color="blue")
    output = io.BytesIO()
    img.save(output, format="PNG")
    output.seek(0)
    return output.read()
