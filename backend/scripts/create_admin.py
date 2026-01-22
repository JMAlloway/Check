#!/usr/bin/env python3
"""
Script to create admin user with interactive prompts.

SECURITY: This script is blocked from running in production/pilot/staging/uat.
For those environments, use proper user provisioning through your deployment process.

Usage:
    python -m scripts.create_admin

    Or with environment variables (for CI/automation in dev):
        ADMIN_USERNAME=admin ADMIN_EMAIL=admin@example.com ADMIN_PASSWORD=secret123 \
            python -m scripts.create_admin
"""

import asyncio
import getpass
import os
import secrets
import sys
import uuid

# Add parent directory to path for imports when run as script
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import settings
from app.core.security import get_password_hash
from app.db.session import AsyncSessionLocal
from app.models.user import User

# Environments where this script must NOT run
BLOCKED_ENVIRONMENTS = {"production", "pilot", "staging", "uat"}


def check_environment() -> None:
    """Fail if running in a secure environment."""
    env = settings.ENVIRONMENT.lower()
    if env in BLOCKED_ENVIRONMENTS:
        print(
            f"ERROR: create_admin.py cannot run in '{env}' environment.\n"
            f"Use proper user provisioning for {env} deployments.",
            file=sys.stderr,
        )
        sys.exit(1)


def get_input(prompt: str, env_var: str, default: str | None = None) -> str:
    """Get input from env var, interactive prompt, or default."""
    # Check environment variable first
    value = os.environ.get(env_var, "").strip()
    if value:
        return value

    # Interactive prompt
    if default:
        user_input = input(f"{prompt} [{default}]: ").strip()
        return user_input if user_input else default
    else:
        while True:
            user_input = input(f"{prompt}: ").strip()
            if user_input:
                return user_input
            print("This field is required.")


def get_password(env_var: str) -> tuple[str, bool]:
    """
    Get password from env var, interactive prompt, or generate one.

    Returns:
        tuple of (password, was_generated)
    """
    # Check environment variable first
    value = os.environ.get(env_var, "").strip()
    if value:
        return value, False

    # Interactive prompt
    print("\nPassword options:")
    print("  1. Enter a password")
    print("  2. Generate a random password")

    choice = input("Choose [1/2] (default: 2): ").strip()

    if choice == "1":
        while True:
            password = getpass.getpass("Enter password: ")
            if not password:
                print("Password cannot be empty.")
                continue
            confirm = getpass.getpass("Confirm password: ")
            if password != confirm:
                print("Passwords do not match. Try again.")
                continue
            return password, False
    else:
        # Generate random password
        password = secrets.token_urlsafe(16)
        return password, True


async def create_admin_user() -> None:
    """Create admin user with interactive prompts."""
    check_environment()

    print("=" * 50)
    print("Create Admin User")
    print(f"Environment: {settings.ENVIRONMENT}")
    print("=" * 50)
    print()

    # Get user details
    username = get_input("Username", "ADMIN_USERNAME", "admin")
    email = get_input("Email", "ADMIN_EMAIL", f"{username}@example.com")
    tenant_id = get_input("Tenant ID", "ADMIN_TENANT_ID", "default")
    full_name = get_input("Full name", "ADMIN_FULL_NAME", "Admin User")

    password, was_generated = get_password("ADMIN_PASSWORD")

    async with AsyncSessionLocal() as db:
        # Check if user already exists
        from sqlalchemy import select

        result = await db.execute(select(User).where(User.username == username))
        existing = result.scalar_one_or_none()
        if existing:
            print(f"\nERROR: User '{username}' already exists!", file=sys.stderr)
            sys.exit(1)

        # Check if email already exists
        result = await db.execute(select(User).where(User.email == email))
        existing = result.scalar_one_or_none()
        if existing:
            print(f"\nERROR: Email '{email}' already in use!", file=sys.stderr)
            sys.exit(1)

        user = User(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            email=email,
            username=username,
            hashed_password=get_password_hash(password),
            full_name=full_name,
            is_active=True,
            is_superuser=True,
        )
        db.add(user)
        await db.commit()

        print()
        print("=" * 50)
        print("Admin user created successfully!")
        print("=" * 50)
        print(f"  Username: {username}")
        print(f"  Email:    {email}")
        print(f"  Tenant:   {tenant_id}")

        if was_generated:
            # Print generated password to stderr (won't appear in logs if stdout is captured)
            print(f"\n  Generated password: {password}", file=sys.stderr)
            print("\n  (Save this password - it will not be shown again)", file=sys.stderr)


if __name__ == "__main__":
    asyncio.run(create_admin_user())
