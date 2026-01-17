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

        # Default tenant for seeded users
        default_tenant_id = "default-tenant"

        # Create permissions
        # Check item permissions
        perm_check_view = Permission(name="check_item:view", resource="check_item", action="view", description="View check items")
        perm_check_review = Permission(name="check_item:review", resource="check_item", action="review", description="Review check items")
        perm_check_approve = Permission(name="check_item:approve", resource="check_item", action="approve", description="Approve check items")
        perm_check_dual_control = Permission(name="check_item:dual_control", resource="check_item", action="dual_control", description="Perform dual control approval")
        perm_check_reassign = Permission(name="check_item:reassign", resource="check_item", action="reassign", description="Reassign check items to other reviewers")

        # Queue permissions
        perm_queue_view = Permission(name="queue:view", resource="queue", action="view", description="View queues")
        perm_queue_create = Permission(name="queue:create", resource="queue", action="create", description="Create queues")
        perm_queue_update = Permission(name="queue:update", resource="queue", action="update", description="Update queues")
        perm_queue_assign = Permission(name="queue:assign", resource="queue", action="assign", description="Assign users to queues")
        perm_queue_manage = Permission(name="queue:manage", resource="queue", action="manage", description="Manage queues")

        # User permissions
        perm_user_view = Permission(name="user:view", resource="user", action="view", description="View users")
        perm_user_create = Permission(name="user:create", resource="user", action="create", description="Create users")
        perm_user_update = Permission(name="user:update", resource="user", action="update", description="Update users")
        perm_user_manage = Permission(name="user:manage", resource="user", action="manage", description="Manage users")

        # Role permissions
        perm_role_view = Permission(name="role:view", resource="role", action="view", description="View roles")
        perm_role_create = Permission(name="role:create", resource="role", action="create", description="Create roles")

        # Permission permissions
        perm_permission_view = Permission(name="permission:view", resource="permission", action="view", description="View permissions")

        # Audit permissions
        perm_audit_view = Permission(name="audit:view", resource="audit", action="view", description="View audit logs")
        perm_audit_export = Permission(name="audit:export", resource="audit", action="export", description="Export audit data")

        # Policy permissions
        perm_policy_view = Permission(name="policy:view", resource="policy", action="view", description="View policies")
        perm_policy_create = Permission(name="policy:create", resource="policy", action="create", description="Create policies")
        perm_policy_update = Permission(name="policy:update", resource="policy", action="update", description="Update policies")
        perm_policy_activate = Permission(name="policy:activate", resource="policy", action="activate", description="Activate policies")
        perm_policy_manage = Permission(name="policy:manage", resource="policy", action="manage", description="Manage policies")

        # Report permissions
        perm_report_view = Permission(name="report:view", resource="report", action="view", description="View reports")

        # Fraud Intelligence permissions
        perm_fraud_view = Permission(name="fraud:view", resource="fraud", action="view", description="View fraud events and alerts")
        perm_fraud_create = Permission(name="fraud:create", resource="fraud", action="create", description="Create fraud events")
        perm_fraud_submit = Permission(name="fraud:submit", resource="fraud", action="submit", description="Submit fraud events to network")
        perm_fraud_withdraw = Permission(name="fraud:withdraw", resource="fraud", action="withdraw", description="Withdraw fraud events")
        perm_fraud_config = Permission(name="fraud:config", resource="fraud", action="config", description="Configure fraud settings")

        # Collect all permissions
        all_permissions = [
            perm_check_view, perm_check_review, perm_check_approve, perm_check_dual_control, perm_check_reassign,
            perm_queue_view, perm_queue_create, perm_queue_update, perm_queue_assign, perm_queue_manage,
            perm_user_view, perm_user_create, perm_user_update, perm_user_manage,
            perm_role_view, perm_role_create,
            perm_permission_view,
            perm_audit_view, perm_audit_export,
            perm_policy_view, perm_policy_create, perm_policy_update, perm_policy_activate, perm_policy_manage,
            perm_report_view,
            perm_fraud_view, perm_fraud_create, perm_fraud_submit, perm_fraud_withdraw, perm_fraud_config,
        ]

        for perm in all_permissions:
            db.add(perm)
        await db.flush()

        # =============================================================================
        # Create roles per Technical Guide Section 2.2 and 5.4
        # =============================================================================

        # 1. Reviewer: View queue, review checks, make decisions
        reviewer_role = Role(
            name="reviewer",
            description="View queue, review checks, make decisions",
            is_system=True,
        )
        reviewer_role.permissions = [
            perm_check_view, perm_check_review,
            perm_queue_view,
            perm_user_view, perm_role_view, perm_permission_view,
            perm_policy_view, perm_report_view, perm_fraud_view,
        ]
        db.add(reviewer_role)

        # 2. Senior Reviewer: All reviewer permissions + dual control approval
        senior_reviewer_role = Role(
            name="senior_reviewer",
            description="All reviewer permissions + dual control approval",
            is_system=True,
        )
        senior_reviewer_role.permissions = [
            # Reviewer permissions
            perm_check_view, perm_check_review,
            perm_queue_view,
            perm_user_view, perm_role_view, perm_permission_view,
            perm_policy_view, perm_report_view, perm_fraud_view,
            # Senior reviewer additions
            perm_check_approve, perm_check_dual_control,
        ]
        db.add(senior_reviewer_role)

        # 3. Supervisor: All senior permissions + queue management, reassignment
        supervisor_role = Role(
            name="supervisor",
            description="All senior permissions + queue management, reassignment",
            is_system=True,
        )
        supervisor_role.permissions = [
            # Senior reviewer permissions
            perm_check_view, perm_check_review, perm_check_approve, perm_check_dual_control,
            perm_queue_view,
            perm_user_view, perm_role_view, perm_permission_view,
            perm_policy_view, perm_report_view, perm_fraud_view,
            # Supervisor additions
            perm_check_reassign,
            perm_queue_create, perm_queue_update, perm_queue_assign, perm_queue_manage,
            perm_audit_view,
        ]
        db.add(supervisor_role)

        # 4. Administrator: All supervisor permissions + user management, policies
        administrator_role = Role(
            name="administrator",
            description="All supervisor permissions + user management, policies",
            is_system=True,
        )
        administrator_role.permissions = [
            # Supervisor permissions
            perm_check_view, perm_check_review, perm_check_approve, perm_check_dual_control, perm_check_reassign,
            perm_queue_view, perm_queue_create, perm_queue_update, perm_queue_assign, perm_queue_manage,
            perm_user_view, perm_role_view, perm_permission_view,
            perm_policy_view, perm_report_view, perm_fraud_view,
            perm_audit_view,
            # Administrator additions
            perm_user_create, perm_user_update, perm_user_manage,
            perm_role_create,
            perm_policy_create, perm_policy_update, perm_policy_activate, perm_policy_manage,
            perm_audit_export,
            perm_fraud_create, perm_fraud_submit, perm_fraud_withdraw, perm_fraud_config,
        ]
        db.add(administrator_role)

        # 5. Auditor: Read-only access to all data and audit logs
        auditor_role = Role(
            name="auditor",
            description="Read-only access to all data and audit logs",
            is_system=True,
        )
        auditor_role.permissions = [
            # Read-only permissions (NO review, approve, or dual_control)
            perm_check_view,
            perm_queue_view,
            perm_user_view, perm_role_view, perm_permission_view,
            perm_policy_view, perm_report_view, perm_fraud_view,
            # Audit access
            perm_audit_view, perm_audit_export,
        ]
        db.add(auditor_role)

        # 6. System Admin: Full system access including configuration
        system_admin_role = Role(
            name="system_admin",
            description="Full system access including configuration",
            is_system=True,
        )
        system_admin_role.permissions = all_permissions
        db.add(system_admin_role)

        await db.flush()

        # =============================================================================
        # Create test users (one per role) with tenant_id
        # =============================================================================

        # System Admin user
        system_admin_user = User(
            tenant_id=default_tenant_id,
            username="system_admin",
            email="system_admin@example.com",
            hashed_password=get_password_hash("sysadmin123"),
            full_name="System Administrator",
            is_active=True,
            is_superuser=True,
        )
        system_admin_user.roles = [system_admin_role]
        db.add(system_admin_user)

        # Administrator user
        administrator_user = User(
            tenant_id=default_tenant_id,
            username="administrator",
            email="administrator@example.com",
            hashed_password=get_password_hash("admin123"),
            full_name="Bank Administrator",
            is_active=True,
        )
        administrator_user.roles = [administrator_role]
        db.add(administrator_user)

        # Supervisor user
        supervisor_user = User(
            tenant_id=default_tenant_id,
            username="supervisor",
            email="supervisor@example.com",
            hashed_password=get_password_hash("supervisor123"),
            full_name="Review Supervisor",
            is_active=True,
        )
        supervisor_user.roles = [supervisor_role]
        db.add(supervisor_user)

        # Senior Reviewer user
        senior_reviewer_user = User(
            tenant_id=default_tenant_id,
            username="senior_reviewer",
            email="senior_reviewer@example.com",
            hashed_password=get_password_hash("senior123"),
            full_name="Senior Check Reviewer",
            is_active=True,
        )
        senior_reviewer_user.roles = [senior_reviewer_role]
        db.add(senior_reviewer_user)

        # Reviewer user
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

        # Auditor user
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
        print(f"\nTenant: {default_tenant_id}")
        print("\nTest accounts (per Technical Guide Section 2.2):")
        print("  system_admin    / sysadmin123   (System Admin - full system access)")
        print("  administrator   / admin123      (Administrator - user mgmt, policies)")
        print("  supervisor      / supervisor123 (Supervisor - queue mgmt, reassign)")
        print("  senior_reviewer / senior123     (Senior Reviewer - dual control)")
        print("  reviewer        / reviewer123   (Reviewer - view, review checks)")
        print("  auditor         / auditor123    (Auditor - read-only audit access)")
        print("\nRoles created: reviewer, senior_reviewer, supervisor, administrator, auditor, system_admin")
        print(f"Permissions created: {len(all_permissions)} (including dual_control, reassign)")
        print("\nFraud Intelligence:")
        print(f"  Tenant config created for: {default_tenant_id}")
        print(f"  Sample network artifacts: {len(sample_artifacts)} indicators")


if __name__ == "__main__":
    asyncio.run(seed_database())
