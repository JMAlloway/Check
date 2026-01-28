"""Seed the database with test data.

WARNING: This script creates test users with known passwords.
It is blocked from running in production/pilot/staging/uat environments.
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.config import settings

# Environment guard - block in secure environments
BLOCKED_ENVIRONMENTS = {"production", "pilot", "staging", "uat"}

if settings.ENVIRONMENT.lower() in BLOCKED_ENVIRONMENTS:
    print("=" * 60, file=sys.stderr)
    print("ERROR: seed_db.py cannot run in secure environments!", file=sys.stderr)
    print("=" * 60, file=sys.stderr)
    print(file=sys.stderr)
    print(f"Current environment: {settings.ENVIRONMENT}", file=sys.stderr)
    print(f"Blocked environments: {', '.join(sorted(BLOCKED_ENVIRONMENTS))}", file=sys.stderr)
    print(file=sys.stderr)
    print("This script creates test users with known passwords (e.g., admin123)", file=sys.stderr)
    print("and should NEVER run in production or pilot environments.", file=sys.stderr)
    print(file=sys.stderr)
    print("For production user creation, use:", file=sys.stderr)
    print("  python -m scripts.create_admin", file=sys.stderr)
    print("=" * 60, file=sys.stderr)
    sys.exit(1)

import hashlib
import hmac
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import select, text

from app.core.security import get_password_hash
from app.db.session import AsyncSessionLocal, Base, engine
from app.models.audit import AuditLog, ItemView
from app.models.check import CheckHistory, CheckImage, CheckItem
from app.models.decision import Decision, ReasonCode
from app.models.fraud import (
    AmountBucket,
    FraudChannel,
    FraudEvent,
    FraudEventStatus,
    FraudSharedArtifact,
    FraudType,
    NetworkMatchAlert,
    SharingLevel,
    TenantFraudConfig,
)
from app.models.policy import Policy, PolicyRule, PolicyVersion
from app.models.queue import Queue, QueueAssignment

# Import ALL models to register them with Base.metadata
from app.models.user import Permission, Role, User


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
        # Check if system_admin user exists
        result = await db.execute(select(User).where(User.username == "system_admin"))
        if result.scalar_one_or_none():
            print("Database already seeded!")
            return

        # Create system-wide permissions (tenant_id=None, is_system=True)
        # These permissions are shared across all tenants
        permissions = [
            Permission(
                tenant_id=None,
                is_system=True,
                name="check_item:view",
                resource="check_item",
                action="view",
                description="View check items",
            ),
            Permission(
                tenant_id=None,
                is_system=True,
                name="check_item:review",
                resource="check_item",
                action="review",
                description="Review check items",
            ),
            Permission(
                tenant_id=None,
                is_system=True,
                name="check_item:approve",
                resource="check_item",
                action="approve",
                description="Approve check items",
            ),
            # Queue permissions
            Permission(
                tenant_id=None,
                is_system=True,
                name="queue:view",
                resource="queue",
                action="view",
                description="View queues",
            ),
            Permission(
                tenant_id=None,
                is_system=True,
                name="queue:create",
                resource="queue",
                action="create",
                description="Create queues",
            ),
            Permission(
                tenant_id=None,
                is_system=True,
                name="queue:update",
                resource="queue",
                action="update",
                description="Update queues",
            ),
            Permission(
                tenant_id=None,
                is_system=True,
                name="queue:assign",
                resource="queue",
                action="assign",
                description="Assign users to queues",
            ),
            Permission(
                tenant_id=None,
                is_system=True,
                name="queue:manage",
                resource="queue",
                action="manage",
                description="Manage queues",
            ),
            # User permissions
            Permission(
                tenant_id=None,
                is_system=True,
                name="user:view",
                resource="user",
                action="view",
                description="View users",
            ),
            Permission(
                tenant_id=None,
                is_system=True,
                name="user:create",
                resource="user",
                action="create",
                description="Create users",
            ),
            Permission(
                tenant_id=None,
                is_system=True,
                name="user:update",
                resource="user",
                action="update",
                description="Update users",
            ),
            Permission(
                tenant_id=None,
                is_system=True,
                name="user:manage",
                resource="user",
                action="manage",
                description="Manage users",
            ),
            # Role permissions
            Permission(
                tenant_id=None,
                is_system=True,
                name="role:view",
                resource="role",
                action="view",
                description="View roles",
            ),
            Permission(
                tenant_id=None,
                is_system=True,
                name="role:create",
                resource="role",
                action="create",
                description="Create roles",
            ),
            # Permission permissions
            Permission(
                tenant_id=None,
                is_system=True,
                name="permission:view",
                resource="permission",
                action="view",
                description="View permissions",
            ),
            # Audit permissions
            Permission(
                tenant_id=None,
                is_system=True,
                name="audit:view",
                resource="audit",
                action="view",
                description="View audit logs",
            ),
            Permission(
                tenant_id=None,
                is_system=True,
                name="audit:export",
                resource="audit",
                action="export",
                description="Export audit data",
            ),
            # Policy permissions
            Permission(
                tenant_id=None,
                is_system=True,
                name="policy:view",
                resource="policy",
                action="view",
                description="View policies",
            ),
            Permission(
                tenant_id=None,
                is_system=True,
                name="policy:create",
                resource="policy",
                action="create",
                description="Create policies",
            ),
            Permission(
                tenant_id=None,
                is_system=True,
                name="policy:update",
                resource="policy",
                action="update",
                description="Update policies",
            ),
            Permission(
                tenant_id=None,
                is_system=True,
                name="policy:activate",
                resource="policy",
                action="activate",
                description="Activate policies",
            ),
            Permission(
                tenant_id=None,
                is_system=True,
                name="policy:manage",
                resource="policy",
                action="manage",
                description="Manage policies",
            ),
            # Report permissions
            Permission(
                tenant_id=None,
                is_system=True,
                name="report:view",
                resource="report",
                action="view",
                description="View reports",
            ),
            # Fraud Intelligence permissions
            Permission(
                tenant_id=None,
                is_system=True,
                name="fraud:view",
                resource="fraud",
                action="view",
                description="View fraud events and alerts",
            ),
            Permission(
                tenant_id=None,
                is_system=True,
                name="fraud:create",
                resource="fraud",
                action="create",
                description="Create fraud events",
            ),
            Permission(
                tenant_id=None,
                is_system=True,
                name="fraud:submit",
                resource="fraud",
                action="submit",
                description="Submit fraud events to network",
            ),
            Permission(
                tenant_id=None,
                is_system=True,
                name="fraud:withdraw",
                resource="fraud",
                action="withdraw",
                description="Withdraw fraud events",
            ),
            Permission(
                tenant_id=None,
                is_system=True,
                name="fraud:config",
                resource="fraud",
                action="config",
                description="Configure fraud settings",
            ),
            # Archive permissions
            Permission(
                tenant_id=None,
                is_system=True,
                name="archive:view",
                resource="archive",
                action="view",
                description="View archived items",
            ),
            Permission(
                tenant_id=None,
                is_system=True,
                name="archive:export",
                resource="archive",
                action="export",
                description="Export archived items",
            ),
        ]

        for perm in permissions:
            db.add(perm)
        await db.flush()

        # Add additional permissions for 6-role system (system-wide)
        perm_dual_control = Permission(
            tenant_id=None,
            is_system=True,
            name="check_item:dual_control",
            resource="check_item",
            action="dual_control",
            description="Perform dual control approval",
        )
        perm_reassign = Permission(
            tenant_id=None,
            is_system=True,
            name="check_item:reassign",
            resource="check_item",
            action="reassign",
            description="Reassign check items",
        )
        db.add(perm_dual_control)
        db.add(perm_reassign)
        await db.flush()

        all_permissions = permissions + [perm_dual_control, perm_reassign]

        # Create permission lookup by name
        perm_lookup = {p.name: p for p in all_permissions}

        # Create 6 system-wide roles per Technical Guide Section 2.2
        # System roles (tenant_id=None, is_system=True) are shared across all tenants
        # 1. Reviewer: View queue, review checks, make decisions
        reviewer_role = Role(
            tenant_id=None,
            name="reviewer",
            description="View queue, review checks, make decisions",
            is_system=True,
        )
        reviewer_role.permissions = [
            perm_lookup[n]
            for n in [
                "check_item:view",
                "check_item:review",
                "queue:view",
                "user:view",
                "role:view",
                "permission:view",
                "policy:view",
                "report:view",
                "fraud:view",
                "archive:view",
            ]
        ]
        db.add(reviewer_role)

        # 2. Senior Reviewer: All reviewer permissions + dual control approval
        senior_reviewer_role = Role(
            tenant_id=None,
            name="senior_reviewer",
            description="All reviewer permissions + dual control approval",
            is_system=True,
        )
        senior_reviewer_role.permissions = [
            perm_lookup[n]
            for n in [
                "check_item:view",
                "check_item:review",
                "check_item:approve",
                "check_item:dual_control",
                "queue:view",
                "user:view",
                "role:view",
                "permission:view",
                "policy:view",
                "report:view",
                "fraud:view",
                "archive:view",
            ]
        ]
        db.add(senior_reviewer_role)

        # 3. Supervisor: All senior permissions + queue management, reassignment
        supervisor_role = Role(
            tenant_id=None,
            name="supervisor",
            description="All senior permissions + queue management, reassignment",
            is_system=True,
        )
        supervisor_role.permissions = [
            perm_lookup[n]
            for n in [
                "check_item:view",
                "check_item:review",
                "check_item:approve",
                "check_item:dual_control",
                "check_item:reassign",
                "queue:view",
                "queue:create",
                "queue:update",
                "queue:assign",
                "queue:manage",
                "user:view",
                "role:view",
                "permission:view",
                "policy:view",
                "report:view",
                "fraud:view",
                "audit:view",
                "archive:view",
                "archive:export",
            ]
        ]
        db.add(supervisor_role)

        # 4. Administrator: All supervisor permissions + user management, policies
        administrator_role = Role(
            tenant_id=None,
            name="administrator",
            description="All supervisor permissions + user management, policies",
            is_system=True,
        )
        administrator_role.permissions = [
            perm_lookup[n]
            for n in [
                "check_item:view",
                "check_item:review",
                "check_item:approve",
                "check_item:dual_control",
                "check_item:reassign",
                "queue:view",
                "queue:create",
                "queue:update",
                "queue:assign",
                "queue:manage",
                "user:view",
                "user:create",
                "user:update",
                "user:manage",
                "role:view",
                "role:create",
                "permission:view",
                "policy:view",
                "policy:create",
                "policy:update",
                "policy:activate",
                "policy:manage",
                "report:view",
                "fraud:view",
                "fraud:create",
                "fraud:submit",
                "fraud:withdraw",
                "fraud:config",
                "audit:view",
                "audit:export",
                "archive:view",
                "archive:export",
            ]
        ]
        db.add(administrator_role)

        # 5. Auditor: Read-only access to all data and audit logs
        auditor_role = Role(
            tenant_id=None,
            name="auditor",
            description="Read-only access to all data and audit logs",
            is_system=True,
        )
        auditor_role.permissions = [
            perm_lookup[n]
            for n in [
                "check_item:view",
                "queue:view",
                "user:view",
                "role:view",
                "permission:view",
                "policy:view",
                "report:view",
                "fraud:view",
                "audit:view",
                "audit:export",
                "archive:view",
                "archive:export",
            ]
        ]
        db.add(auditor_role)

        # 6. System Admin: Full system access including configuration
        system_admin_role = Role(
            tenant_id=None,
            name="system_admin",
            description="Full system access including configuration",
            is_system=True,
        )
        system_admin_role.permissions = all_permissions
        db.add(system_admin_role)

        await db.flush()

        # Default tenant for all users
        default_tenant_id = "default-tenant"

        # Create test users per Technical Guide Section 2.2
        system_admin_user = User(
            tenant_id=default_tenant_id,
            username="system_admin",
            email="sysadmin@example.com",
            hashed_password=get_password_hash("sysadmin123"),
            full_name="System Administrator",
            is_active=True,
            is_superuser=True,
        )
        system_admin_user.roles = [system_admin_role]
        db.add(system_admin_user)

        administrator_user = User(
            tenant_id=default_tenant_id,
            username="administrator",
            email="admin@example.com",
            hashed_password=get_password_hash("admin123"),
            full_name="Administrator User",
            is_active=True,
        )
        administrator_user.roles = [administrator_role]
        db.add(administrator_user)

        supervisor_user = User(
            tenant_id=default_tenant_id,
            username="supervisor",
            email="supervisor@example.com",
            hashed_password=get_password_hash("supervisor123"),
            full_name="Supervisor User",
            is_active=True,
        )
        supervisor_user.roles = [supervisor_role]
        db.add(supervisor_user)

        senior_reviewer_user = User(
            tenant_id=default_tenant_id,
            username="senior_reviewer",
            email="senior@example.com",
            hashed_password=get_password_hash("senior123"),
            full_name="Senior Reviewer",
            is_active=True,
        )
        senior_reviewer_user.roles = [senior_reviewer_role]
        db.add(senior_reviewer_user)

        reviewer_user = User(
            tenant_id=default_tenant_id,
            username="reviewer",
            email="reviewer@example.com",
            hashed_password=get_password_hash("reviewer123"),
            full_name="Check Reviewer",
            is_active=True,
        )
        reviewer_user.roles = [reviewer_role]
        db.add(reviewer_user)

        auditor_user = User(
            tenant_id=default_tenant_id,
            username="auditor",
            email="auditor@example.com",
            hashed_password=get_password_hash("auditor123"),
            full_name="Compliance Auditor",
            is_active=True,
        )
        auditor_user.roles = [auditor_role]
        db.add(auditor_user)

        await db.flush()

        # Create tenant fraud configuration (using same default_tenant_id from above)
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
                "indicators_json": {
                    "check_fingerprint": hash_indicator("021000021:1234567890:1001")
                },
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
        print(f"\nTenant: {default_tenant_id}")
        print("\nTest accounts (per Technical Guide Section 2.2):")
        print("  system_admin    / sysadmin123   (System Admin - full system access)")
        print("  administrator   / admin123      (Administrator - user mgmt, policies)")
        print("  supervisor      / supervisor123 (Supervisor - queue mgmt, reassign)")
        print("  senior_reviewer / senior123     (Senior Reviewer - dual control)")
        print("  reviewer        / reviewer123   (Reviewer - view, review checks)")
        print("  auditor         / auditor123    (Auditor - read-only audit access)")
        print(
            "\nRoles created: reviewer, senior_reviewer, supervisor, administrator, auditor, system_admin"
        )
        print(f"Permissions created: {len(all_permissions)}")
        print("\nFraud Intelligence:")
        print(f"  Tenant config created for: {default_tenant_id}")
        print(f"  Sample network artifacts: {len(sample_artifacts)} indicators")


if __name__ == "__main__":
    asyncio.run(seed_database())
