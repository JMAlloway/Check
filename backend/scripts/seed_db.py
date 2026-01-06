"""Seed the database with test data."""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from app.db.session import AsyncSessionLocal
from app.models.user import User, Role, Permission
from app.core.security import get_password_hash


async def seed_database():
    """Create test users and roles."""

    async with AsyncSessionLocal() as db:
        # Check if admin user exists
        result = await db.execute(select(User).where(User.username == "admin"))
        if result.scalar_one_or_none():
            print("Database already seeded!")
            return

        # Create permissions
        permissions = [
            Permission(name="check_item:view", resource="check_item", action="view", description="View check items"),
            Permission(name="check_item:review", resource="check_item", action="review", description="Review check items"),
            Permission(name="check_item:approve", resource="check_item", action="approve", description="Approve check items"),
            Permission(name="queue:view", resource="queue", action="view", description="View queues"),
            Permission(name="queue:manage", resource="queue", action="manage", description="Manage queues"),
            Permission(name="user:view", resource="user", action="view", description="View users"),
            Permission(name="user:manage", resource="user", action="manage", description="Manage users"),
            Permission(name="audit:view", resource="audit", action="view", description="View audit logs"),
            Permission(name="audit:export", resource="audit", action="export", description="Export audit data"),
            Permission(name="policy:view", resource="policy", action="view", description="View policies"),
            Permission(name="policy:manage", resource="policy", action="manage", description="Manage policies"),
            Permission(name="report:view", resource="report", action="view", description="View reports"),
        ]

        for perm in permissions:
            db.add(perm)
        await db.flush()

        # Create roles
        admin_role = Role(
            name="admin",
            description="Full system access",
            is_system_role=True,
        )
        admin_role.permissions = permissions
        db.add(admin_role)

        reviewer_role = Role(
            name="reviewer",
            description="Can review check items",
            is_system_role=True,
        )
        reviewer_role.permissions = [p for p in permissions if p.action in ["view", "review"]]
        db.add(reviewer_role)

        approver_role = Role(
            name="approver",
            description="Can approve check items",
            is_system_role=True,
        )
        approver_role.permissions = [p for p in permissions if p.action in ["view", "review", "approve"]]
        db.add(approver_role)

        await db.flush()

        # Create test users
        admin_user = User(
            username="admin",
            email="admin@example.com",
            hashed_password=get_password_hash("admin123"),
            first_name="Admin",
            last_name="User",
            is_active=True,
            is_superuser=True,
        )
        admin_user.roles = [admin_role]
        db.add(admin_user)

        reviewer_user = User(
            username="reviewer",
            email="reviewer@example.com",
            hashed_password=get_password_hash("reviewer123"),
            first_name="Test",
            last_name="Reviewer",
            is_active=True,
        )
        reviewer_user.roles = [reviewer_role]
        db.add(reviewer_user)

        approver_user = User(
            username="approver",
            email="approver@example.com",
            hashed_password=get_password_hash("approver123"),
            first_name="Test",
            last_name="Approver",
            is_active=True,
        )
        approver_user.roles = [approver_role]
        db.add(approver_user)

        await db.commit()

        print("Database seeded successfully!")
        print("\nTest accounts:")
        print("  admin    / admin123    (full access)")
        print("  reviewer / reviewer123 (review only)")
        print("  approver / approver123 (review + approve)")


if __name__ == "__main__":
    asyncio.run(seed_database())
