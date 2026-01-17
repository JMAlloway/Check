"""Field-level encryption for sensitive data at rest.

Provides AES-256-GCM encryption for sensitive fields like MFA secrets.
Each encrypted value includes a unique nonce and authentication tag.

Security considerations:
- Uses AES-256-GCM for authenticated encryption
- Unique nonce per encryption prevents replay attacks
- Key derived from SECRET_KEY using HKDF for proper key separation
- Encrypted values are base64-encoded for safe storage in text columns

Usage:
    from app.core.encryption import encrypt_field, decrypt_field

    # Encrypt before storing
    encrypted = encrypt_field("my-secret-value")

    # Decrypt when reading
    plaintext = decrypt_field(encrypted)
"""

import base64
import os
from functools import lru_cache

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes


# Encryption version prefix for future algorithm migration
ENCRYPTION_VERSION = b"v1:"
NONCE_SIZE = 12  # 96 bits for GCM


@lru_cache(maxsize=1)
def _get_encryption_key() -> bytes:
    """Derive a 256-bit encryption key from SECRET_KEY using HKDF.

    HKDF provides proper key derivation with domain separation,
    allowing SECRET_KEY to be used for multiple purposes safely.
    """
    from app.core.config import settings

    # Use HKDF to derive a separate key for field encryption
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,  # 256 bits for AES-256
        salt=b"check-review-field-encryption",  # Fixed salt for deterministic derivation
        info=b"mfa-secret-encryption",  # Context for this specific use
    )

    return hkdf.derive(settings.SECRET_KEY.encode("utf-8"))


def encrypt_field(plaintext: str) -> str:
    """Encrypt a string value for storage.

    Args:
        plaintext: The value to encrypt

    Returns:
        Base64-encoded encrypted value with version prefix

    Raises:
        ValueError: If plaintext is empty or None
    """
    if not plaintext:
        raise ValueError("Cannot encrypt empty value")

    key = _get_encryption_key()
    aesgcm = AESGCM(key)

    # Generate a unique nonce for this encryption
    nonce = os.urandom(NONCE_SIZE)

    # Encrypt with authentication
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)

    # Combine nonce + ciphertext and encode
    encrypted_data = ENCRYPTION_VERSION + nonce + ciphertext
    return base64.urlsafe_b64encode(encrypted_data).decode("ascii")


def decrypt_field(encrypted: str) -> str:
    """Decrypt a stored encrypted value.

    Args:
        encrypted: Base64-encoded encrypted value from encrypt_field()

    Returns:
        Decrypted plaintext string

    Raises:
        ValueError: If decryption fails (wrong key, tampered data, etc.)
    """
    if not encrypted:
        raise ValueError("Cannot decrypt empty value")

    try:
        # Decode from base64
        encrypted_data = base64.urlsafe_b64decode(encrypted.encode("ascii"))

        # Check version prefix
        if not encrypted_data.startswith(ENCRYPTION_VERSION):
            raise ValueError("Unknown encryption version")

        # Remove version prefix
        encrypted_data = encrypted_data[len(ENCRYPTION_VERSION):]

        # Extract nonce and ciphertext
        nonce = encrypted_data[:NONCE_SIZE]
        ciphertext = encrypted_data[NONCE_SIZE:]

        # Decrypt
        key = _get_encryption_key()
        aesgcm = AESGCM(key)
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)

        return plaintext.decode("utf-8")

    except Exception as e:
        # Don't leak specific crypto errors
        raise ValueError(f"Decryption failed: {type(e).__name__}")


def is_encrypted(value: str) -> bool:
    """Check if a value appears to be encrypted.

    Useful for migration: detect whether existing MFA secrets
    need encryption or are already encrypted.
    """
    if not value:
        return False

    try:
        decoded = base64.urlsafe_b64decode(value.encode("ascii"))
        return decoded.startswith(ENCRYPTION_VERSION)
    except Exception:
        return False


def migrate_mfa_secret(value: str | None) -> str | None:
    """Migrate an MFA secret to encrypted format if needed.

    Returns:
        Encrypted value, or None if input was None
    """
    if value is None:
        return None

    if is_encrypted(value):
        return value  # Already encrypted

    return encrypt_field(value)


# Aliases for cleaner API in other modules
encrypt_value = encrypt_field
decrypt_value = decrypt_field
