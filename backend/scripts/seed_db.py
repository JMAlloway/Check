"""Seed the database with test data."""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select, text
from app.db.session import AsyncSessionLocal, engine, Base

# Import ALL models to register them with Base.metadata
from app.models.user import User, Role, Permission
from app.models.check import CheckItem, CheckImage, CheckHistory
from app.models.decision import Decision, ReasonCode
from app.models.policy import Policy, PolicyVersion, PolicyRule
from app.models.queue import Queue, QueueAssignment
from app.models.audit import AuditLog, ItemView
from app.models.fraud import (
    FraudEvent, FraudSharedArtifact, NetworkMatchAlert, TenantFraudConfig,
    FraudType, FraudChannel, AmountBucket, SharingLevel, FraudEventStatus
)

from app.core.security import get_password_hash
from app.core.config import settings
import hashlib
import hmac
from datetime import datetime, timezone, timedelta
from uuid import uuid4


async def seed_database():
    """Create test users and roles."""

    # First, completely reset the database schema
    print("Resetting database schema...")
    async with engine.begin() as conn:
        # Drop everything in public schema and recreate it
        await conn.execute(text("DROP SCHEMA public CASCADE"))
        await conn.execute(text("CREATE SCHEMA public"))
        await conn.execute(text("GRANT ALL ON SCHEMA public TO PUBLIC"))

    print("Creating tables...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("Tables created successfully!")

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
            # Queue permissions
            Permission(name="queue:view", resource="queue", action="view", description="View queues"),
            Permission(name="queue:create", resource="queue", action="create", description="Create queues"),
            Permission(name="queue:update", resource="queue", action="update", description="Update queues"),
            Permission(name="queue:assign", resource="queue", action="assign", description="Assign users to queues"),
            Permission(name="queue:manage", resource="queue", action="manage", description="Manage queues"),
            # User permissions
            Permission(name="user:view", resource="user", action="view", description="View users"),
            Permission(name="user:create", resource="user", action="create", description="Create users"),
            Permission(name="user:update", resource="user", action="update", description="Update users"),
            Permission(name="user:manage", resource="user", action="manage", description="Manage users"),
            # Role permissions
            Permission(name="role:view", resource="role", action="view", description="View roles"),
            Permission(name="role:create", resource="role", action="create", description="Create roles"),
            # Permission permissions
            Permission(name="permission:view", resource="permission", action="view", description="View permissions"),
            # Audit permissions
            Permission(name="audit:view", resource="audit", action="view", description="View audit logs"),
            Permission(name="audit:export", resource="audit", action="export", description="Export audit data"),
            # Policy permissions
            Permission(name="policy:view", resource="policy", action="view", description="View policies"),
            Permission(name="policy:create", resource="policy", action="create", description="Create policies"),
            Permission(name="policy:update", resource="policy", action="update", description="Update policies"),
            Permission(name="policy:activate", resource="policy", action="activate", description="Activate policies"),
            Permission(name="policy:manage", resource="policy", action="manage", description="Manage policies"),
            # Report permissions
            Permission(name="report:view", resource="report", action="view", description="View reports"),
            # Fraud Intelligence permissions
            Permission(name="fraud:view", resource="fraud", action="view", description="View fraud events and alerts"),
            Permission(name="fraud:create", resource="fraud", action="create", description="Create fraud events"),
            Permission(name="fraud:submit", resource="fraud", action="submit", description="Submit fraud events to network"),
            Permission(name="fraud:withdraw", resource="fraud", action="withdraw", description="Withdraw fraud events"),
            Permission(name="fraud:config", resource="fraud", action="config", description="Configure fraud settings"),
        ]

        for perm in permissions:
            db.add(perm)
        await db.flush()

        # Create roles
        admin_role = Role(
            name="admin",
            description="Full system access",
            is_system=True,
        )
        admin_role.permissions = permissions
        db.add(admin_role)

        reviewer_role = Role(
            name="reviewer",
            description="Can review check items",
            is_system=True,
        )
        reviewer_role.permissions = [p for p in permissions if p.action in ["view", "review"]]
        db.add(reviewer_role)

        approver_role = Role(
            name="approver",
            description="Can approve check items",
            is_system=True,
        )
        approver_role.permissions = [p for p in permissions if p.action in ["view", "review", "approve"]]
        db.add(approver_role)

        await db.flush()

        # Create test users
        admin_user = User(
            username="admin",
            email="admin@example.com",
            hashed_password=get_password_hash("admin123"),
            full_name="Admin User",
            is_active=True,
            is_superuser=True,
        )
        admin_user.roles = [admin_role]
        db.add(admin_user)

        reviewer_user = User(
            username="reviewer",
            email="reviewer@example.com",
            hashed_password=get_password_hash("reviewer123"),
            full_name="Test Reviewer",
            is_active=True,
        )
        reviewer_user.roles = [reviewer_role]
        db.add(reviewer_user)

        approver_user = User(
            username="approver",
            email="approver@example.com",
            hashed_password=get_password_hash("approver123"),
            full_name="Test Approver",
            is_active=True,
        )
        approver_user.roles = [approver_role]
        db.add(approver_user)

        await db.flush()

        # Create tenant fraud configuration
        default_tenant_id = "default-tenant"
        fraud_config = TenantFraudConfig(
            tenant_id=default_tenant_id,
            default_sharing_level=SharingLevel.NETWORK_MATCH,
            allow_narrative_sharing=True,
            allow_account_indicator_sharing=True,
            shared_artifact_retention_months=24,
            receive_network_alerts=True,
            minimum_alert_severity="low",
        )
        db.add(fraud_config)
        await db.flush()

        # Helper function to hash indicators (simulating the hashing service)
        def hash_indicator(value: str) -> str:
            pepper = settings.NETWORK_PEPPER.encode()
            return hmac.new(pepper, value.encode(), hashlib.sha256).hexdigest()

        # Create sample shared artifacts from "other institutions" for network matching demo
        # These simulate fraud indicators shared by other banks in the network
        now = datetime.now(timezone.utc)
        sample_artifacts = [
            # Routing number associated with fraud
            {
                "tenant_id": "bank-a",
                "indicators_json": {"routing_number": hash_indicator("021000021")},
                "fraud_type": FraudType.COUNTERFEIT_CHECK,
                "channel": FraudChannel.MOBILE,
                "amount_bucket": AmountBucket.FROM_1000_TO_5000,
                "occurred_at": now - timedelta(days=45),
            },
            {
                "tenant_id": "bank-b",
                "indicators_json": {"routing_number": hash_indicator("021000021")},
                "fraud_type": FraudType.FORGED_SIGNATURE,
                "channel": FraudChannel.RDC,
                "amount_bucket": AmountBucket.FROM_5000_TO_10000,
                "occurred_at": now - timedelta(days=60),
            },
            # Payee name associated with fraud
            {
                "tenant_id": "bank-c",
                "indicators_json": {"payee_name": hash_indicator("ACME CORP")},
                "fraud_type": FraudType.FICTITIOUS_PAYEE,
                "channel": FraudChannel.BRANCH,
                "amount_bucket": AmountBucket.FROM_10000_TO_50000,
                "occurred_at": now - timedelta(days=75),
            },
            {
                "tenant_id": "bank-a",
                "indicators_json": {"payee_name": hash_indicator("ACME CORP")},
                "fraud_type": FraudType.FICTITIOUS_PAYEE,
                "channel": FraudChannel.MOBILE,
                "amount_bucket": AmountBucket.FROM_5000_TO_10000,
                "occurred_at": now - timedelta(days=90),
            },
            # Check fingerprint
            {
                "tenant_id": "bank-d",
                "indicators_json": {"check_fingerprint": hash_indicator("021000021:1234567890:1001")},
                "fraud_type": FraudType.DUPLICATE_DEPOSIT,
                "channel": FraudChannel.ATM,
                "amount_bucket": AmountBucket.FROM_500_TO_1000,
                "occurred_at": now - timedelta(days=30),
            },
        ]

        for artifact_data in sample_artifacts:
            occurred_at = artifact_data["occurred_at"]
            artifact = FraudSharedArtifact(
                tenant_id=artifact_data["tenant_id"],
                fraud_event_id=None,  # Simulated external events (nullable for demo)
                sharing_level=SharingLevel.NETWORK_MATCH,
                occurred_at=occurred_at,
                occurred_month=occurred_at.strftime("%Y-%m"),
                fraud_type=artifact_data["fraud_type"],
                channel=artifact_data["channel"],
                amount_bucket=artifact_data["amount_bucket"],
                indicators_json=artifact_data["indicators_json"],
                is_active=True,
            )
            db.add(artifact)

        await db.commit()

        print("Database seeded successfully!")
        print("\nTest accounts:")
        print("  admin    / admin123    (full access)")
        print("  reviewer / reviewer123 (review only)")
        print("  approver / approver123 (review + approve)")
        print("\nFraud Intelligence:")
        print(f"  Tenant config created for: {default_tenant_id}")
        print(f"  Sample network artifacts: {len(sample_artifacts)} indicators")


if __name__ == "__main__":
    asyncio.run(seed_database())
