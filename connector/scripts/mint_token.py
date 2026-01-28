#!/usr/bin/env python3
"""
Token minting script for testing the Bank-Side Connector.

Generates RS256 JWT tokens for testing image endpoints.

Usage:
    # Generate a test token
    python scripts/mint_token.py

    # Generate with specific claims
    python scripts/mint_token.py --user test-user --org demo-org --roles image_viewer,check_reviewer

    # Generate key pair (first time setup)
    python scripts/mint_token.py --generate-keys
"""
import argparse
import json
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

try:
    import jwt
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.backends import default_backend
except ImportError:
    print("Required packages not installed. Run:")
    print("  pip install PyJWT cryptography")
    sys.exit(1)


DEFAULT_KEYS_DIR = Path(__file__).parent.parent / "keys"
PRIVATE_KEY_FILE = "connector_private.pem"
PUBLIC_KEY_FILE = "connector_public.pem"


def generate_key_pair(keys_dir: Path) -> tuple:
    """
    Generate a new RSA key pair.

    Args:
        keys_dir: Directory to store keys

    Returns:
        Tuple of (private_key, public_key) as PEM strings
    """
    keys_dir.mkdir(parents=True, exist_ok=True)

    # Generate private key
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend()
    )

    # Serialize private key
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    ).decode()

    # Serialize public key
    public_key = private_key.public_key()
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode()

    # Save keys
    private_path = keys_dir / PRIVATE_KEY_FILE
    public_path = keys_dir / PUBLIC_KEY_FILE

    with open(private_path, "w") as f:
        f.write(private_pem)
    print(f"Private key saved to: {private_path}")

    with open(public_path, "w") as f:
        f.write(public_pem)
    print(f"Public key saved to: {public_path}")

    # Also output for env config
    print("\n" + "=" * 60)
    print("Add this to your .env file for the connector:")
    print("=" * 60)
    print(f'CONNECTOR_JWT_PUBLIC_KEY="{public_pem.strip()}"')
    print("=" * 60)

    return private_pem, public_pem


def load_private_key(keys_dir: Path) -> str:
    """
    Load the private key from file.

    Args:
        keys_dir: Directory containing keys

    Returns:
        Private key as PEM string
    """
    private_path = keys_dir / PRIVATE_KEY_FILE

    if not private_path.exists():
        print(f"Private key not found at: {private_path}")
        print("Run with --generate-keys first to create a key pair")
        sys.exit(1)

    return private_path.read_text()


def mint_token(
    private_key: str,
    subject: str = "demo-user",
    org_id: str = "demo-org",
    roles: list = None,
    expiry_seconds: int = 120,
    issuer: str = "check-review-saas"
) -> str:
    """
    Mint a JWT token.

    Args:
        private_key: RSA private key in PEM format
        subject: Token subject (user ID)
        org_id: Organization ID
        roles: List of roles
        expiry_seconds: Token expiry in seconds
        issuer: Token issuer

    Returns:
        JWT token string
    """
    if roles is None:
        roles = ["image_viewer", "check_reviewer"]

    now = int(time.time())

    payload = {
        "sub": subject,
        "org_id": org_id,
        "roles": roles,
        "iat": now,
        "exp": now + expiry_seconds,
        "jti": str(uuid.uuid4()),
        "iss": issuer
    }

    token = jwt.encode(payload, private_key, algorithm="RS256")
    return token


def decode_token(token: str, public_key: str = None, verify: bool = True) -> dict:
    """
    Decode a token with signature verification.

    Args:
        token: JWT token string
        public_key: Public key for verification (required for verification)
        verify: Whether to verify signature (should be True in production)

    Returns:
        Decoded payload

    Note:
        This is a development/debugging tool only.
        In production code, ALWAYS verify JWT signatures.
    """
    if public_key:
        return jwt.decode(token, public_key, algorithms=["RS256"])
    elif not verify:
        # WARNING: Only use verify=False for debugging self-minted tokens
        # Never disable verification for tokens from external sources
        return jwt.decode(token, options={"verify_signature": False})  # nosec B105
    else:
        raise ValueError("Public key required for token verification")


def main():
    parser = argparse.ArgumentParser(
        description="Mint JWT tokens for testing the Bank-Side Connector"
    )
    parser.add_argument(
        "--generate-keys",
        action="store_true",
        help="Generate a new RSA key pair"
    )
    parser.add_argument(
        "--keys-dir",
        type=Path,
        default=DEFAULT_KEYS_DIR,
        help=f"Directory for keys (default: {DEFAULT_KEYS_DIR})"
    )
    parser.add_argument(
        "--user",
        default="demo-user",
        help="User ID (subject) for the token"
    )
    parser.add_argument(
        "--org",
        default="demo-org",
        help="Organization ID"
    )
    parser.add_argument(
        "--roles",
        default="image_viewer,check_reviewer",
        help="Comma-separated list of roles"
    )
    parser.add_argument(
        "--expiry",
        type=int,
        default=120,
        help="Token expiry in seconds (default: 120)"
    )
    parser.add_argument(
        "--issuer",
        default="check-review-saas",
        help="Token issuer"
    )
    parser.add_argument(
        "--decode",
        metavar="TOKEN",
        help="Decode an existing token"
    )
    parser.add_argument(
        "--curl",
        action="store_true",
        help="Output curl command examples"
    )

    args = parser.parse_args()

    if args.generate_keys:
        generate_key_pair(args.keys_dir)
        return

    if args.decode:
        # For debugging self-minted tokens, decode without verification
        # This is safe since this script is for local testing only
        payload = decode_token(args.decode, verify=False)
        print(json.dumps(payload, indent=2, default=str))
        return

    # Load private key and mint token
    private_key = load_private_key(args.keys_dir)
    roles = [r.strip() for r in args.roles.split(",")]

    token = mint_token(
        private_key=private_key,
        subject=args.user,
        org_id=args.org,
        roles=roles,
        expiry_seconds=args.expiry,
        issuer=args.issuer
    )

    print("=" * 60)
    print("JWT Token")
    print("=" * 60)
    print(token)
    print()

    # Decode and show claims (safe to skip verify since we just minted it)
    payload = decode_token(token, verify=False)
    print("Token Claims:")
    print(json.dumps(payload, indent=2, default=str))
    print()

    # Calculate expiry time
    exp_time = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
    print(f"Expires at: {exp_time.isoformat()}")
    print(f"Valid for: {args.expiry} seconds")
    print()

    if args.curl:
        print("=" * 60)
        print("Example curl commands:")
        print("=" * 60)
        print()
        print("# Health check (no auth required)")
        print("curl -s http://localhost:8443/healthz | jq")
        print()
        print("# Get image by handle")
        print(f'curl -s -H "Authorization: Bearer {token}" \\')
        print('  "http://localhost:8443/v1/images/by-handle?path=\\\\\\\\tn-director-pro\\\\Checks\\\\Transit\\\\V406\\\\580\\\\12374628.IMG&side=front" \\')
        print('  -o front.png')
        print()
        print("# Get image by item")
        print(f'curl -s -H "Authorization: Bearer {token}" \\')
        print('  "http://localhost:8443/v1/images/by-item?trace=12374628&date=2024-01-15&side=front" \\')
        print('  -o front.png')
        print()
        print("# Lookup item")
        print(f'curl -s -H "Authorization: Bearer {token}" \\')
        print('  "http://localhost:8443/v1/items/lookup?trace=12374628&date=2024-01-15" | jq')


if __name__ == "__main__":
    main()
