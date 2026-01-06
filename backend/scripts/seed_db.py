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
            Permission(name="queue:view", resource="queue", action="view", description="View queues"),
            Permission(name="queue:manage", resource="queue", action="manage", description="Manage queues"),
            Permission(name="user:view", resource="user", action="view", description="View users"),
            Permission(name="user:manage", resource="user", action="manage", description="Manage users"),
            Permission(name="audit:view", resource="audit", action="view", description="View audit logs"),
            Permission(name="audit:export", resource="audit", action="export", description="Export audit data"),
            Permission(name="policy:view", resource="policy", action="view", description="View policies"),
            Permission(name="policy:manage", resource="policy", action="manage", description="Manage policies"),
            Permission(name="report:view", resource="report", action="view", description="View reports"),
            # Fraud Intelligence permissions
            Permission(name="fraud:view", resource="fraud", action="view", description="View fraud events and alerts"),
            Permission(name="fraud:create", resource="fraud", action="create", description="Create fraud events"),
            Permission(name="fraud:submit", resource="fraud", action="submit", description="Submit fraud events to network"),
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
        sample_artifacts = [
            # Routing number associated with fraud
            {
                "contributing_tenant_id": "bank-a",
                "indicator_type": "routing_number",
                "indicator_hash": hash_indicator("021000021"),  # Sample routing number
                "fraud_type": FraudType.COUNTERFEIT_CHECK,
                "channel": FraudChannel.MOBILE,
                "amount_bucket": AmountBucket.BUCKET_1000_5000,
            },
            {
                "contributing_tenant_id": "bank-b",
                "indicator_type": "routing_number",
                "indicator_hash": hash_indicator("021000021"),
                "fraud_type": FraudType.FORGED_SIGNATURE,
                "channel": FraudChannel.RDC,
                "amount_bucket": AmountBucket.BUCKET_5000_10000,
            },
            # Payee name associated with fraud
            {
                "contributing_tenant_id": "bank-c",
                "indicator_type": "payee_name",
                "indicator_hash": hash_indicator("ACME CORP"),  # Normalized payee name
                "fraud_type": FraudType.FICTITIOUS_PAYEE,
                "channel": FraudChannel.BRANCH,
                "amount_bucket": AmountBucket.BUCKET_10000_50000,
            },
            {
                "contributing_tenant_id": "bank-a",
                "indicator_type": "payee_name",
                "indicator_hash": hash_indicator("ACME CORP"),
                "fraud_type": FraudType.FICTITIOUS_PAYEE,
                "channel": FraudChannel.MOBILE,
                "amount_bucket": AmountBucket.BUCKET_5000_10000,
            },
            # Check fingerprint
            {
                "contributing_tenant_id": "bank-d",
                "indicator_type": "check_fingerprint",
                "indicator_hash": hash_indicator("021000021:1234567890:1001"),  # routing:account:check#
                "fraud_type": FraudType.DUPLICATE_DEPOSIT,
                "channel": FraudChannel.ATM,
                "amount_bucket": AmountBucket.BUCKET_500_1000,
            },
        ]

        now = datetime.now(timezone.utc)
        for i, artifact_data in enumerate(sample_artifacts):
            artifact = FraudSharedArtifact(
                fraud_event_id=None,  # Simulated external events
                contributing_tenant_id=artifact_data["contributing_tenant_id"],
                indicator_type=artifact_data["indicator_type"],
                indicator_hash=artifact_data["indicator_hash"],
                fraud_type=artifact_data["fraud_type"],
                channel=artifact_data["channel"],
                amount_bucket=artifact_data["amount_bucket"],
                event_date=(now - timedelta(days=30 + i * 15)).date(),
                expires_at=now + timedelta(days=365),
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
