"""
Demo Data Seeding Module.

This module creates synthetic data for demonstration purposes.
All data is clearly marked as demo data and uses no real PII.

Usage:
    python -m app.demo.seed --reset --count 60
"""

import argparse
import asyncio
import random
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import get_password_hash
from app.db.session import AsyncSessionLocal
from app.demo import require_non_production
from app.demo.scenarios import (
    DEMO_ACCOUNTS,
    DEMO_CREDENTIALS,
    DEMO_PAYEES,
    DEMO_ROUTING_NUMBERS,
    DEMO_SCENARIOS,
    DemoScenario,
)
from app.models.audit import AuditLog, AuditAction
from app.models.check import CheckHistory, CheckImage, CheckItem, CheckStatus, RiskLevel, AccountType, ItemType
from app.models.decision import Decision, DecisionAction, DecisionType, ReasonCode
from app.models.fraud import (
    FraudEvent,
    FraudSharedArtifact,
    NetworkMatchAlert,
    FraudType,
    FraudChannel,
    FraudEventStatus,
    TenantFraudConfig,
    SharingLevel,
    get_amount_bucket,
)
from app.models.image_connector import ImageConnector, ConnectorStatus
from app.models.policy import Policy, PolicyVersion, PolicyRule, PolicyStatus, RuleType
from app.models.queue import Queue, QueueType
from app.models.user import User


class DemoSeeder:
    """Seeds the database with demo data."""

    def __init__(self, db: AsyncSession, count: int = 60):
        self.db = db
        self.count = count
        self.demo_users: dict[str, User] = {}
        self.demo_queues: dict[str, Queue] = {}
        self.demo_checks: list[CheckItem] = []

    async def seed_all(self, reset: bool = False) -> dict:
        """Seed all demo data."""
        require_non_production()

        stats = {
            "users": 0,
            "queues": 0,
            "policies": 0,
            "image_connectors": 0,
            "reason_codes": 0,
            "check_items": 0,
            "check_images": 0,
            "check_history": 0,
            "decisions": 0,
            "audit_events": 0,
            "fraud_events": 0,
            "network_alerts": 0,
            "network_trends": 0,
        }

        if reset:
            await self._clear_demo_data()
            print("Cleared existing demo data")

        # Seed in order of dependencies
        # CRITICAL: Commit users early so login always works even if later steps fail
        stats["users"] = await self._seed_users()
        stats["queues"] = await self._seed_queues()
        await self._seed_tenant_fraud_config()  # Enable fraud features for demo
        await self.db.commit()  # Commit users and queues first
        print(f"Committed {stats['users']} users and {stats['queues']} queues")

        # Seed admin configuration items
        stats["policies"] = await self._seed_policies()
        stats["image_connectors"] = await self._seed_image_connectors()
        await self.db.commit()
        print(f"Committed {stats['policies']} policies and {stats['image_connectors']} image connectors")

        stats["reason_codes"] = await self._seed_reason_codes()
        stats["check_items"], stats["check_images"] = await self._seed_checks()
        stats["check_history"] = await self._seed_check_history()
        stats["decisions"] = await self._seed_decisions()
        stats["audit_events"] = await self._seed_audit_events()
        await self.db.commit()  # Commit core data

        # Fraud data is optional - don't let it break the whole seeding
        try:
            stats["fraud_events"] = await self._seed_fraud_events()
            stats["network_alerts"] = await self._seed_network_alerts()
            stats["network_trends"] = await self._seed_network_trend_data()
            await self.db.commit()
        except Exception as e:
            print(f"Warning: Failed to seed fraud data: {e}")
            await self.db.rollback()

        return stats

    async def _clear_demo_data(self):
        """Clear all demo data from the database using is_demo flag."""
        # Delete in reverse order of dependencies using is_demo column
        # NOTE: Audit logs are immutable (DB trigger prevents DELETE), so we skip them

        # Clear network alerts (must clear before check items due to FK)
        await self.db.execute(
            delete(NetworkMatchAlert).where(
                NetworkMatchAlert.tenant_id == "DEMO-TENANT-000000000000000000000000"
            )
        )

        # Clear fraud shared artifacts (must clear before fraud events)
        # Include both demo tenant and fake network tenants
        await self.db.execute(
            delete(FraudSharedArtifact).where(
                FraudSharedArtifact.tenant_id.like("DEMO-%")
            )
        )

        # Clear fraud events (must clear before check items due to FK)
        await self.db.execute(
            delete(FraudEvent).where(
                FraudEvent.tenant_id == "DEMO-TENANT-000000000000000000000000"
            )
        )

        # Clear decisions
        await self.db.execute(delete(Decision).where(Decision.is_demo == True))

        # Clear check images
        await self.db.execute(delete(CheckImage).where(CheckImage.is_demo == True))

        # Clear check items
        await self.db.execute(delete(CheckItem).where(CheckItem.is_demo == True))

        # Clear check history
        await self.db.execute(delete(CheckHistory).where(CheckHistory.is_demo == True))

        # Clear queues
        await self.db.execute(delete(Queue).where(Queue.is_demo == True))

        # Clear reason codes (by code prefix - reason codes don't have is_demo)
        await self.db.execute(delete(ReasonCode).where(ReasonCode.code.like("DEMO-%")))

        # Clear image connectors (by connector_id prefix)
        await self.db.execute(
            delete(ImageConnector).where(ImageConnector.connector_id.like("DEMO-%"))
        )

        # Clear policy rules, versions, and policies (by name prefix)
        # Rules are cascade deleted with versions, versions cascade with policies
        await self.db.execute(delete(Policy).where(Policy.name.like("Demo%")))

        # Clear demo users
        await self.db.execute(delete(User).where(User.is_demo == True))

        await self.db.commit()

    async def _seed_users(self) -> int:
        """Create demo users."""
        count = 0

        for role, creds in DEMO_CREDENTIALS.items():
            # Check if user exists
            result = await self.db.execute(
                select(User).where(User.username == creds["username"])
            )
            existing = result.scalar_one_or_none()

            if existing:
                self.demo_users[role] = existing
                continue

            user = User(
                id=f"DEMO-USER-{role.upper()}-{uuid.uuid4().hex[:8]}",
                tenant_id="DEMO-TENANT-000000000000000000000000",
                email=f"{creds['username']}@demo.example.com",
                username=creds["username"],
                hashed_password=get_password_hash(creds["password"]),
                full_name=f"Demo {role.title()} User",
                is_active=True,
                is_superuser=(role == "system_admin"),
                department="Demo Department",
                branch="Demo Branch",
                employee_id=f"DEMO-EMP-{role.upper()}",
                is_demo=True,  # Mark as demo user
            )
            self.db.add(user)
            self.demo_users[role] = user
            count += 1

        await self.db.flush()
        return count

    async def _seed_queues(self) -> int:
        """Create demo queues."""
        queue_configs = [
            {
                "name": "Demo High Priority",
                "queue_type": QueueType.HIGH_PRIORITY,
                "priority": 100,
                "description": "Demo queue for high-value items requiring immediate review",
            },
            {
                "name": "Demo Standard Review",
                "queue_type": QueueType.STANDARD,
                "priority": 50,
                "description": "Demo queue for standard review items",
            },
            {
                "name": "Demo Dual Control",
                "queue_type": QueueType.SPECIAL_REVIEW,
                "priority": 75,
                "description": "Demo queue for items pending dual control approval",
            },
            {
                "name": "Demo Escalation",
                "queue_type": QueueType.ESCALATION,
                "priority": 90,
                "description": "Demo queue for escalated items",
            },
        ]

        count = 0
        for config in queue_configs:
            result = await self.db.execute(
                select(Queue).where(Queue.name == config["name"])
            )
            existing = result.scalar_one_or_none()

            if existing:
                self.demo_queues[config["name"]] = existing
                continue

            queue = Queue(
                id=str(uuid.uuid4()),
                tenant_id="DEMO-TENANT-000000000000000000000000",
                name=config["name"],
                queue_type=config["queue_type"],
                description=config["description"],
                display_order=config["priority"],
                is_active=True,
                sla_hours=settings.DEFAULT_SLA_HOURS,
                is_demo=True,  # Mark as demo queue
            )
            self.db.add(queue)
            self.demo_queues[config["name"]] = queue
            count += 1

        await self.db.flush()
        return count

    async def _seed_tenant_fraud_config(self) -> None:
        """Create or update tenant fraud config to enable fraud features."""
        result = await self.db.execute(
            select(TenantFraudConfig).where(
                TenantFraudConfig.tenant_id == "DEMO-TENANT-000000000000000000000000"
            )
        )
        config = result.scalar_one_or_none()

        if not config:
            config = TenantFraudConfig(
                id=str(uuid.uuid4()),
                tenant_id="DEMO-TENANT-000000000000000000000000",
                default_sharing_level=SharingLevel.AGGREGATE.value,  # Level 1 - enables network trends
                allow_narrative_sharing=True,
                allow_account_indicator_sharing=True,
                receive_network_alerts=True,
                minimum_alert_severity="low",
                shared_artifact_retention_months=24,
            )
            self.db.add(config)
        else:
            # Update existing config to enable features
            config.default_sharing_level = SharingLevel.AGGREGATE.value
            config.receive_network_alerts = True
            config.minimum_alert_severity = "low"

        await self.db.flush()

    async def _seed_policies(self) -> int:
        """Create demo policies for the admin console."""
        import json
        from enum import Enum

        # Custom JSON encoder for Decimal and Enum types
        class PolicyEncoder(json.JSONEncoder):
            def default(self, obj):
                if isinstance(obj, Decimal):
                    return str(obj)
                if isinstance(obj, Enum):
                    return obj.value
                return super().default(obj)

        count = 0
        admin_user = self.demo_users.get("system_admin")
        admin_id = admin_user.id if admin_user else "DEMO-USER-ADMIN-00000001"

        policy_configs = [
            {
                "name": "Demo High Value Check Policy",
                "description": "Policy for checks exceeding $10,000 - requires dual control and enhanced review",
                "is_default": True,
                "rules": [
                    {
                        "name": "High Value Dual Control",
                        "rule_type": RuleType.DUAL_CONTROL,
                        "priority": 100,
                        "conditions": json.dumps([
                            {"field": "amount", "operator": "greater_or_equal", "value": 10000, "value_type": "number"}
                        ]),
                        "actions": json.dumps([
                            {"action": "require_dual_control", "params": {"approver_role": "senior_approver"}}
                        ]),
                        "amount_threshold": Decimal("10000.00"),
                    },
                    {
                        "name": "Very High Value Escalation",
                        "rule_type": RuleType.ESCALATION,
                        "priority": 90,
                        "conditions": json.dumps([
                            {"field": "amount", "operator": "greater_or_equal", "value": 50000, "value_type": "number"}
                        ]),
                        "actions": json.dumps([
                            {"action": "escalate", "params": {"queue": "management_review", "notify": True}}
                        ]),
                        "amount_threshold": Decimal("50000.00"),
                    },
                ],
            },
            {
                "name": "Demo Fraud Prevention Policy",
                "description": "Policy for handling high-risk and potentially fraudulent checks",
                "is_default": False,
                "rules": [
                    {
                        "name": "High Risk Auto-Escalate",
                        "rule_type": RuleType.ESCALATION,
                        "priority": 100,
                        "conditions": json.dumps([
                            {"field": "risk_level", "operator": "in", "value": ["high", "critical"], "value_type": "array"}
                        ]),
                        "actions": json.dumps([
                            {"action": "escalate", "params": {"queue": "fraud_review"}},
                            {"action": "require_dual_control", "params": {}}
                        ]),
                        "risk_level_threshold": "high",
                    },
                    {
                        "name": "AI Flag Review Required",
                        "rule_type": RuleType.REQUIRE_REASON,
                        "priority": 80,
                        "conditions": json.dumps([
                            {"field": "has_ai_flags", "operator": "equals", "value": True, "value_type": "boolean"}
                        ]),
                        "actions": json.dumps([
                            {"action": "require_reason", "params": {"reason_category": "ai_override"}}
                        ]),
                    },
                    {
                        "name": "Network Alert Dual Control",
                        "rule_type": RuleType.DUAL_CONTROL,
                        "priority": 95,
                        "conditions": json.dumps([
                            {"field": "has_network_alerts", "operator": "equals", "value": True, "value_type": "boolean"}
                        ]),
                        "actions": json.dumps([
                            {"action": "require_dual_control", "params": {"approver_role": "fraud_analyst"}}
                        ]),
                    },
                ],
            },
            {
                "name": "Demo New Account Policy",
                "description": "Enhanced scrutiny for accounts less than 90 days old",
                "is_default": False,
                "rules": [
                    {
                        "name": "New Account Enhanced Review",
                        "rule_type": RuleType.ROUTING,
                        "priority": 70,
                        "conditions": json.dumps([
                            {"field": "account_tenure_days", "operator": "less_than", "value": 90, "value_type": "number"}
                        ]),
                        "actions": json.dumps([
                            {"action": "route_to_queue", "params": {"queue": "new_account_review"}}
                        ]),
                    },
                    {
                        "name": "New Account High Value",
                        "rule_type": RuleType.DUAL_CONTROL,
                        "priority": 85,
                        "conditions": json.dumps([
                            {"field": "account_tenure_days", "operator": "less_than", "value": 90, "value_type": "number"},
                            {"field": "amount", "operator": "greater_or_equal", "value": 5000, "value_type": "number"}
                        ]),
                        "actions": json.dumps([
                            {"action": "require_dual_control", "params": {}},
                            {"action": "escalate", "params": {"notify": True}}
                        ]),
                        "amount_threshold": Decimal("5000.00"),
                    },
                ],
            },
            {
                "name": "Demo SLA Management Policy",
                "description": "Automatic routing based on SLA status",
                "is_default": False,
                "rules": [
                    {
                        "name": "SLA Breach High Priority",
                        "rule_type": RuleType.ROUTING,
                        "priority": 100,
                        "conditions": json.dumps([
                            {"field": "sla_breached", "operator": "equals", "value": True, "value_type": "boolean"}
                        ]),
                        "actions": json.dumps([
                            {"action": "route_to_queue", "params": {"queue": "high_priority"}},
                            {"action": "notify", "params": {"channel": "supervisor"}}
                        ]),
                    },
                ],
            },
        ]

        for config in policy_configs:
            # Check if policy already exists
            result = await self.db.execute(
                select(Policy).where(Policy.name == config["name"])
            )
            existing = result.scalar_one_or_none()
            if existing:
                continue

            # Create policy
            policy = Policy(
                id=str(uuid.uuid4()),
                tenant_id="DEMO-TENANT-000000000000000000000000",  # Multi-tenant support
                name=config["name"],
                description=config["description"],
                status=PolicyStatus.ACTIVE,
                is_default=config.get("is_default", False),
                applies_to_account_types=json.dumps(["consumer", "business", "commercial"]),
                applies_to_branches=json.dumps(["all"]),
                applies_to_markets=json.dumps(["all"]),
            )
            self.db.add(policy)
            await self.db.flush()

            # Create policy version
            version = PolicyVersion(
                id=str(uuid.uuid4()),
                policy_id=policy.id,
                version_number=1,
                effective_date=datetime.now(timezone.utc) - timedelta(days=30),
                is_current=True,
                rules_snapshot=json.dumps(config["rules"], cls=PolicyEncoder),
                approved_by_id=admin_id,
                approved_at=datetime.now(timezone.utc) - timedelta(days=30),
                change_notes="Initial demo policy version",
            )
            self.db.add(version)
            await self.db.flush()

            # Create policy rules
            for rule_config in config["rules"]:
                rule = PolicyRule(
                    id=str(uuid.uuid4()),
                    policy_version_id=version.id,
                    name=rule_config["name"],
                    rule_type=rule_config["rule_type"],
                    priority=rule_config["priority"],
                    is_enabled=True,
                    conditions=rule_config["conditions"],
                    actions=rule_config["actions"],
                    amount_threshold=rule_config.get("amount_threshold"),
                    risk_level_threshold=rule_config.get("risk_level_threshold"),
                )
                self.db.add(rule)

            count += 1

        await self.db.flush()
        return count

    async def _seed_image_connectors(self) -> int:
        """Create demo image connector configuration."""
        count = 0
        admin_user = self.demo_users.get("system_admin")
        admin_id = admin_user.id if admin_user else "DEMO-USER-ADMIN-00000001"

        # Demo RSA public key (NOT for production use - just for demo display)
        demo_public_key = """-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAu1SU1LfVLPHCozMxH2Mo
4lgOEePzNm0tRgeLezV6ffAt0gunVTLw7onLRnrq0/IzW7yWR7QkrmBL7jTKEn5u
+qKhbwKfBstIs+bMY2Zkp18gnTxKLxoS2tFczGkPLPgizskuemMghRniWaoLcyeh
kd3qqGElvW/VDL5AaWTg0nLVkjRo9z+40RQzuVaE8AkAFmxZzow3x+VJYKdjykkJ
0iT9wCS0DRTXu269V264Vf/3jvredZiKRkgwlL9xNAwxXFg0x/XFw005UWVRIkdg
cKWTjpBP2dPwVZ4WWC+9aGVd+Gyn1o0CLelf4rEjGoXbAAEgAqeGUxrcIlbjXfbc
mwIDAQAB
-----END PUBLIC KEY-----"""

        connector_configs = [
            {
                "connector_id": "DEMO-CONNECTOR-PRIMARY",
                "name": "Demo Primary Image Connector",
                "description": "Primary connector for demo check images - simulates bank datacenter connection",
                "base_url": "https://demo-connector.example.com:8443",
                "status": ConnectorStatus.ACTIVE,
                "is_enabled": True,
                "priority": 100,
                "connector_version": "1.2.0",
                "connector_mode": "demo",
                "allowed_roots": ["/demo/images", "/demo/archive"],
            },
            {
                "connector_id": "DEMO-CONNECTOR-BACKUP",
                "name": "Demo Backup Image Connector",
                "description": "Secondary connector for failover demonstration",
                "base_url": "https://demo-connector-backup.example.com:8443",
                "status": ConnectorStatus.INACTIVE,
                "is_enabled": False,
                "priority": 200,
                "connector_version": "1.2.0",
                "connector_mode": "demo",
                "allowed_roots": ["/demo/images"],
            },
        ]

        for config in connector_configs:
            # Check if connector already exists
            result = await self.db.execute(
                select(ImageConnector).where(
                    ImageConnector.connector_id == config["connector_id"],
                    ImageConnector.tenant_id == "DEMO-TENANT-000000000000000000000000",
                )
            )
            existing = result.scalar_one_or_none()
            if existing:
                continue

            connector = ImageConnector(
                id=str(uuid.uuid4()),
                tenant_id="DEMO-TENANT-000000000000000000000000",
                connector_id=config["connector_id"],
                name=config["name"],
                description=config["description"],
                base_url=config["base_url"],
                status=config["status"],
                is_enabled=config["is_enabled"],
                public_key_pem=demo_public_key,
                public_key_id=f"{config['connector_id']}-key-v1",
                public_key_expires_at=datetime.now(timezone.utc) + timedelta(days=365),
                token_expiry_seconds=120,
                jwt_issuer="check-review-demo",
                last_health_check_at=datetime.now(timezone.utc) - timedelta(minutes=5) if config["is_enabled"] else None,
                last_health_check_status="healthy" if config["is_enabled"] else None,
                last_health_check_latency_ms=45 if config["is_enabled"] else None,
                health_check_failure_count=0,
                last_successful_request_at=datetime.now(timezone.utc) - timedelta(hours=1) if config["is_enabled"] else None,
                connector_version=config["connector_version"],
                connector_mode=config["connector_mode"],
                allowed_roots=config["allowed_roots"],
                timeout_seconds=30,
                max_retries=2,
                circuit_breaker_threshold=5,
                circuit_breaker_timeout_seconds=60,
                priority=config["priority"],
                created_by_user_id=admin_id,
                last_connection_test_at=datetime.now(timezone.utc) - timedelta(hours=2) if config["is_enabled"] else None,
                last_connection_test_result="Connection successful" if config["is_enabled"] else None,
                last_connection_test_success=True if config["is_enabled"] else None,
            )
            self.db.add(connector)
            count += 1

        await self.db.flush()
        return count

    async def _seed_reason_codes(self) -> int:
        """Create demo reason codes for decisions."""
        reason_code_configs = [
            # Return reason codes
            {
                "code": "RET-SIG",
                "description": "Signature discrepancy - signature does not match account records",
                "category": "signature",
                "decision_type": "return",
                "display_order": 10,
                "requires_notes": False,
            },
            {
                "code": "RET-AMT",
                "description": "Amount mismatch - written and numeric amounts do not match",
                "category": "amount",
                "decision_type": "return",
                "display_order": 20,
                "requires_notes": False,
            },
            {
                "code": "RET-DATE",
                "description": "Date issue - stale dated or post-dated check",
                "category": "date",
                "decision_type": "return",
                "display_order": 30,
                "requires_notes": False,
            },
            {
                "code": "RET-PAYEE",
                "description": "Payee issue - payee name unclear or altered",
                "category": "payee",
                "decision_type": "return",
                "display_order": 40,
                "requires_notes": False,
            },
            {
                "code": "RET-OTHER",
                "description": "Other return reason - see notes for details",
                "category": "other",
                "decision_type": "return",
                "display_order": 100,
                "requires_notes": True,
            },
            # Reject reason codes
            {
                "code": "REJ-FRAUD",
                "description": "Suspected fraud - check appears to be fraudulent",
                "category": "fraud",
                "decision_type": "reject",
                "display_order": 10,
                "requires_notes": True,
            },
            {
                "code": "REJ-FORGE",
                "description": "Forged signature - signature appears to be forged",
                "category": "signature",
                "decision_type": "reject",
                "display_order": 20,
                "requires_notes": True,
            },
            {
                "code": "REJ-CNTFT",
                "description": "Counterfeit check - check stock is not authentic",
                "category": "fraud",
                "decision_type": "reject",
                "display_order": 30,
                "requires_notes": True,
            },
            {
                "code": "REJ-ALTER",
                "description": "Altered check - check has been materially altered",
                "category": "alteration",
                "decision_type": "reject",
                "display_order": 40,
                "requires_notes": True,
            },
            {
                "code": "REJ-DUP",
                "description": "Duplicate presentment - check was previously deposited",
                "category": "duplicate",
                "decision_type": "reject",
                "display_order": 50,
                "requires_notes": False,
            },
            # Escalate reason codes
            {
                "code": "ESC-REVIEW",
                "description": "Requires senior review - complex case needs additional review",
                "category": "escalation",
                "decision_type": "escalate",
                "display_order": 10,
                "requires_notes": True,
            },
            {
                "code": "ESC-POLICY",
                "description": "Policy exception required - case requires policy exception",
                "category": "escalation",
                "decision_type": "escalate",
                "display_order": 20,
                "requires_notes": True,
            },
            {
                "code": "ESC-LEGAL",
                "description": "Legal review needed - requires legal department input",
                "category": "escalation",
                "decision_type": "escalate",
                "display_order": 30,
                "requires_notes": True,
            },
            # Needs more info reason codes
            {
                "code": "INFO-SIG",
                "description": "Need signature verification - requires customer contact",
                "category": "verification",
                "decision_type": "needs_more_info",
                "display_order": 10,
                "requires_notes": False,
            },
            {
                "code": "INFO-DOC",
                "description": "Need supporting documents - requires additional documentation",
                "category": "verification",
                "decision_type": "needs_more_info",
                "display_order": 20,
                "requires_notes": True,
            },
            {
                "code": "INFO-CALL",
                "description": "Callback required - need to contact customer",
                "category": "verification",
                "decision_type": "needs_more_info",
                "display_order": 30,
                "requires_notes": True,
            },
        ]

        count = 0
        for config in reason_code_configs:
            # Check if reason code exists
            result = await self.db.execute(
                select(ReasonCode).where(ReasonCode.code == config["code"])
            )
            existing = result.scalar_one_or_none()

            if existing:
                continue

            reason_code = ReasonCode(
                id=str(uuid.uuid4()),
                code=config["code"],
                description=config["description"],
                category=config["category"],
                decision_type=config["decision_type"],
                display_order=config["display_order"],
                requires_notes=config["requires_notes"],
                is_active=True,
            )
            self.db.add(reason_code)
            count += 1

        await self.db.flush()
        return count

    async def _seed_checks(self) -> tuple[int, int]:
        """Create demo check items with various scenarios."""
        check_count = 0
        image_count = 0

        # Distribute scenarios
        scenarios = list(DemoScenario)
        scenario_weights = {
            # Normal scenarios get higher weight
            DemoScenario.ROUTINE_PAYROLL: 15,
            DemoScenario.REGULAR_VENDOR_PAYMENT: 15,
            DemoScenario.KNOWN_CUSTOMER_CHECK: 15,
            # Review scenarios
            DemoScenario.ALTERED_AMOUNT: 5,
            DemoScenario.SUSPICIOUS_ENDORSEMENT: 5,
            DemoScenario.MISMATCHED_SIGNATURE: 4,
            DemoScenario.STALE_DATED: 4,
            DemoScenario.POST_DATED: 4,
            DemoScenario.DUPLICATE_CHECK: 3,
            DemoScenario.UNUSUAL_AMOUNT: 5,
            DemoScenario.NEW_ACCOUNT_HIGH_VALUE: 5,
            DemoScenario.VELOCITY_SPIKE: 4,
            # Fraud scenarios
            DemoScenario.COUNTERFEIT_CHECK: 3,
            DemoScenario.FORGED_SIGNATURE: 3,
            DemoScenario.ACCOUNT_TAKEOVER: 2,
        }

        # Status distribution for workflow demonstration
        status_distribution = {
            CheckStatus.NEW: 20,
            CheckStatus.IN_REVIEW: 15,
            CheckStatus.PENDING_DUAL_CONTROL: 15,
            CheckStatus.ESCALATED: 5,
            CheckStatus.APPROVED: 25,
            CheckStatus.REJECTED: 10,
            CheckStatus.RETURNED: 10,
        }

        for i in range(self.count):
            # Select scenario based on weights
            scenario = random.choices(
                list(scenario_weights.keys()),
                weights=list(scenario_weights.values()),
            )[0]
            scenario_config = DEMO_SCENARIOS[scenario]

            # Select account
            account = random.choice(DEMO_ACCOUNTS)

            # Select status based on distribution
            status = random.choices(
                list(status_distribution.keys()),
                weights=list(status_distribution.values()),
            )[0]

            # Generate amount within scenario range
            amount = Decimal(str(random.uniform(
                float(scenario_config.amount_range[0]),
                float(scenario_config.amount_range[1])
            ))).quantize(Decimal("0.01"))

            # Generate dates
            presented_date = datetime.now(timezone.utc) - timedelta(
                days=random.randint(0, 30),
                hours=random.randint(0, 23),
            )
            check_date = presented_date - timedelta(days=random.randint(0, 14))

            # For stale-dated scenario
            if scenario == DemoScenario.STALE_DATED:
                check_date = presented_date - timedelta(days=random.randint(190, 365))
            elif scenario == DemoScenario.POST_DATED:
                check_date = presented_date + timedelta(days=random.randint(5, 30))

            # Select queue based on status and scenario
            queue = self._select_queue_for_status(status, scenario_config.requires_dual_control)

            # Determine if dual control is required
            requires_dual_control = (
                scenario_config.requires_dual_control or
                amount >= settings.DUAL_CONTROL_THRESHOLD
            )

            # Map risk level
            risk_level_map = {
                "low": RiskLevel.LOW,
                "medium": RiskLevel.MEDIUM,
                "high": RiskLevel.HIGH,
                "critical": RiskLevel.CRITICAL,
            }

            # Map account type string to enum
            account_type_map = {
                "consumer": AccountType.CONSUMER,
                "business": AccountType.BUSINESS,
                "commercial": AccountType.COMMERCIAL,
                "non_profit": AccountType.NON_PROFIT,
            }

            # Randomly assign item type (40% on_us, 60% transit)
            item_type = ItemType.ON_US if random.random() < 0.4 else ItemType.TRANSIT

            check_item = CheckItem(
                id=str(uuid.uuid4()),
                tenant_id="DEMO-TENANT-000000000000000000000000",
                external_item_id=f"DEMO-CHECK-{i+1:04d}-{uuid.uuid4().hex[:8]}",
                source_system="demo",
                item_type=item_type,
                account_id=account.account_id,
                account_number_masked=account.account_number_masked,
                account_type=account_type_map.get(account.account_type, AccountType.CONSUMER),
                routing_number=random.choice(DEMO_ROUTING_NUMBERS),
                check_number=f"{random.randint(1000, 9999)}",
                amount=amount,
                currency="USD",
                payee_name=random.choice(DEMO_PAYEES),
                memo=f"Demo payment - {scenario.value}",
                micr_line=f"DEMO-MICR-{i+1:06d}",
                micr_account=account.account_number_masked.replace("*", "0"),
                micr_routing=random.choice(DEMO_ROUTING_NUMBERS),
                micr_check_number=f"{random.randint(1000, 9999)}",
                presented_date=presented_date,
                check_date=check_date,
                status=status,
                risk_level=risk_level_map.get(scenario_config.risk_level, RiskLevel.LOW),
                priority=self._calculate_priority(scenario_config, amount),
                queue_id=queue.id if queue else None,
                sla_due_at=presented_date + timedelta(hours=settings.DEFAULT_SLA_HOURS),
                sla_breached=random.random() < 0.1,  # 10% SLA breach rate
                requires_dual_control=requires_dual_control,
                dual_control_reason="amount_threshold" if amount >= settings.DUAL_CONTROL_THRESHOLD else "policy_rule" if requires_dual_control else None,
                has_ai_flags=len(scenario_config.flags) > 0,
                ai_risk_score=Decimal(str(1 - scenario_config.ai_confidence)).quantize(Decimal("0.0001")),
                risk_flags=str(scenario_config.flags) if scenario_config.flags else None,
                ai_model_id="demo-risk-analyzer",
                ai_model_version="demo-1.0.0",
                ai_analyzed_at=datetime.now(timezone.utc),
                ai_recommendation=scenario_config.ai_recommendation,
                ai_confidence=Decimal(str(scenario_config.ai_confidence)).quantize(Decimal("0.0001")),
                ai_explanation=scenario_config.explanation,
                ai_risk_factors=str(scenario_config.flags) if scenario_config.flags else None,
                account_tenure_days=account.tenure_days,
                current_balance=account.avg_balance,
                average_balance_30d=account.avg_balance,
                avg_check_amount_30d=account.avg_check_amount,
                avg_check_amount_90d=account.avg_check_amount * Decimal("0.95"),
                avg_check_amount_365d=account.avg_check_amount * Decimal("0.90"),
                check_frequency_30d=account.check_frequency,
                returned_item_count_90d=account.returned_items,
                is_demo=True,  # Mark as demo data
            )

            # Assign reviewers for non-new items
            if status != CheckStatus.NEW:
                check_item.assigned_reviewer_id = self.demo_users.get("reviewer", self.demo_users.get("system_admin")).id

            if status == CheckStatus.PENDING_DUAL_CONTROL:
                check_item.assigned_approver_id = self.demo_users.get("senior_reviewer", self.demo_users.get("system_admin")).id

            self.db.add(check_item)
            self.demo_checks.append(check_item)
            check_count += 1

            # Create check images (front and back)
            for image_type in ["front", "back"]:
                image = CheckImage(
                    id=str(uuid.uuid4()),
                    check_item_id=check_item.id,
                    image_type=image_type,
                    external_image_id=f"DEMO-IMG-{check_item.id}-{image_type}",
                    storage_path=f"/demo/images/{check_item.id}/{image_type}.png",
                    content_type="image/png",
                    file_size=random.randint(50000, 200000),
                    width=1200,
                    height=600,
                    dpi=200,
                    is_demo=True,  # Mark as demo data
                )
                self.db.add(image)
                image_count += 1

        await self.db.flush()
        return check_count, image_count

    async def _seed_check_history(self) -> int:
        """Create historical check data for side-by-side comparison with images."""
        count = 0

        for account in DEMO_ACCOUNTS:
            # Create 8-20 historical checks per account for better scrollable history
            history_count = random.randint(8, 20)

            for i in range(history_count):
                check_date = datetime.now(timezone.utc) - timedelta(
                    days=random.randint(30, 365)
                )
                amount = account.avg_check_amount * Decimal(str(random.uniform(0.5, 1.5)))
                history_id = str(uuid.uuid4())
                external_id = f"DEMO-HIST-{account.account_id}-{i}"

                # Generate image references for historical checks
                front_image_ref = f"DEMO-IMG-HIST-{history_id}-front"
                back_image_ref = f"DEMO-IMG-HIST-{history_id}-back"

                # Most checks cleared, some returned with different reasons
                status_roll = random.random()
                if status_roll < 0.85:
                    status = "cleared"
                    return_reason = None
                elif status_roll < 0.92:
                    status = "returned"
                    return_reason = random.choice(["NSF", "Stop Payment", "Account Closed"])
                else:
                    status = "returned"
                    return_reason = random.choice(["Signature Mismatch", "Stale Dated", "Duplicate"])

                history = CheckHistory(
                    id=history_id,
                    account_id=account.account_id,
                    check_number=f"{random.randint(1000, 9999)}",
                    amount=amount.quantize(Decimal("0.01")),
                    check_date=check_date,
                    payee_name=random.choice(DEMO_PAYEES),
                    status=status,
                    return_reason=return_reason,
                    external_item_id=external_id,
                    front_image_ref=front_image_ref,
                    back_image_ref=back_image_ref,
                    signature_hash=f"DEMO-SIG-{uuid.uuid4().hex[:16]}",
                    check_stock_hash=f"DEMO-STOCK-{uuid.uuid4().hex[:16]}",
                    is_demo=True,  # Mark as demo data
                )
                self.db.add(history)
                count += 1

        await self.db.flush()
        return count

    async def _seed_decisions(self) -> int:
        """Create decisions for completed check items."""
        count = 0
        terminal_statuses = [CheckStatus.APPROVED, CheckStatus.REJECTED, CheckStatus.RETURNED]

        for check in self.demo_checks:
            if check.status in terminal_statuses:
                # Map check status to decision action
                action_map = {
                    CheckStatus.APPROVED: DecisionAction.APPROVE,
                    CheckStatus.REJECTED: DecisionAction.REJECT,
                    CheckStatus.RETURNED: DecisionAction.RETURN,
                }

                reviewer = self.demo_users.get("reviewer", self.demo_users.get("system_admin"))
                decision = Decision(
                    id=str(uuid.uuid4()),
                    tenant_id="DEMO-TENANT-000000000000000000000000",
                    check_item_id=check.id,
                    user_id=reviewer.id,
                    decision_type=DecisionType.REVIEW_RECOMMENDATION if check.requires_dual_control else DecisionType.APPROVAL_DECISION,
                    action=action_map[check.status],
                    notes=f"Demo decision for {check.status.value} scenario",
                    previous_status=CheckStatus.IN_REVIEW.value,
                    new_status=check.status.value,
                    is_dual_control_required=check.requires_dual_control,
                    is_demo=True,  # Mark as demo data
                )
                self.db.add(decision)
                count += 1

                # Add approver decision for dual control items
                if check.requires_dual_control:
                    approver = self.demo_users.get("senior_reviewer", self.demo_users.get("system_admin"))
                    approval_decision = Decision(
                        id=str(uuid.uuid4()),
                        tenant_id="DEMO-TENANT-000000000000000000000000",
                        check_item_id=check.id,
                        user_id=approver.id,
                        decision_type=DecisionType.APPROVAL_DECISION,
                        action=action_map[check.status],
                        notes=f"Demo approval for {check.status.value}",
                        previous_status=CheckStatus.PENDING_DUAL_CONTROL.value,
                        new_status=check.status.value,
                        dual_control_approver_id=approver.id,
                        dual_control_approved_at=datetime.now(timezone.utc),
                        is_demo=True,  # Mark as demo data
                    )
                    self.db.add(approval_decision)
                    count += 1

        await self.db.flush()
        return count

    async def _seed_audit_events(self) -> int:
        """Create audit trail events."""
        count = 0

        for check in self.demo_checks[:20]:  # Limit to first 20 for performance
            # Login event
            reviewer = self.demo_users.get("reviewer", self.demo_users.get("system_admin"))
            login_time = check.presented_date - timedelta(minutes=random.randint(5, 60))

            audit_log = AuditLog(
                id=str(uuid.uuid4()),
                tenant_id="DEMO-TENANT-000000000000000000000000",
                timestamp=login_time,
                user_id=reviewer.id,
                username=reviewer.username,
                ip_address="127.0.0.1",
                action=AuditAction.LOGIN,
                resource_type="session",
                resource_id=f"DEMO-SESSION-{uuid.uuid4().hex[:8]}",
                description="Demo user login",
                is_demo=True,  # Mark as demo data
            )
            self.db.add(audit_log)
            count += 1

            # View check event
            view_time = login_time + timedelta(minutes=random.randint(1, 30))
            view_log = AuditLog(
                id=str(uuid.uuid4()),
                tenant_id="DEMO-TENANT-000000000000000000000000",
                timestamp=view_time,
                user_id=reviewer.id,
                username=reviewer.username,
                ip_address="127.0.0.1",
                action=AuditAction.ITEM_VIEWED,
                resource_type="check_item",
                resource_id=check.id,
                description=f"Viewed check {check.external_item_id}",
                is_demo=True,  # Mark as demo data
            )
            self.db.add(view_log)
            count += 1

        await self.db.flush()
        return count

    async def _seed_fraud_events(self) -> int:
        """Create fraud events for network intelligence demonstration."""
        count = 0

        # Fraud event configurations - realistic scenarios
        fraud_scenarios = [
            {
                "fraud_type": FraudType.COUNTERFEIT_CHECK,
                "channel": FraudChannel.MOBILE,
                "confidence": 5,
                "narrative": "Counterfeit check stock detected - magnetic ink anomalies",
            },
            {
                "fraud_type": FraudType.FORGED_SIGNATURE,
                "channel": FraudChannel.BRANCH,
                "confidence": 4,
                "narrative": "Signature does not match known patterns for account holder",
            },
            {
                "fraud_type": FraudType.ALTERED_CHECK,
                "channel": FraudChannel.RDC,
                "confidence": 5,
                "narrative": "Amount field shows evidence of chemical alteration",
            },
            {
                "fraud_type": FraudType.DUPLICATE_DEPOSIT,
                "channel": FraudChannel.MOBILE,
                "confidence": 5,
                "narrative": "Same check deposited at multiple institutions",
            },
            {
                "fraud_type": FraudType.ACCOUNT_TAKEOVER,
                "channel": FraudChannel.ONLINE,
                "confidence": 4,
                "narrative": "Unusual check activity pattern inconsistent with account history",
            },
            {
                "fraud_type": FraudType.PAYEE_ALTERATION,
                "channel": FraudChannel.BRANCH,
                "confidence": 4,
                "narrative": "Payee name shows signs of mechanical erasure and rewriting",
            },
            {
                "fraud_type": FraudType.AMOUNT_ALTERATION,
                "channel": FraudChannel.ATM,
                "confidence": 5,
                "narrative": "Numeric and written amounts inconsistent, alterations visible",
            },
            {
                "fraud_type": FraudType.CHECK_KITING,
                "channel": FraudChannel.BRANCH,
                "confidence": 3,
                "narrative": "Pattern of circular deposits between accounts detected",
            },
        ]

        # Create fraud events for some high-risk demo checks
        high_risk_checks = [c for c in self.demo_checks if c.risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]]
        rejected_checks = [c for c in self.demo_checks if c.status == CheckStatus.REJECTED]
        fraud_check_pool = list(set(high_risk_checks + rejected_checks))[:15]  # Limit to 15

        reviewer = self.demo_users.get("reviewer", self.demo_users.get("system_admin"))

        for i, check in enumerate(fraud_check_pool):
            scenario = fraud_scenarios[i % len(fraud_scenarios)]
            event_date = check.presented_date - timedelta(hours=random.randint(1, 48))

            fraud_event = FraudEvent(
                id=str(uuid.uuid4()),
                tenant_id="DEMO-TENANT-000000000000000000000000",
                check_item_id=check.id,
                event_date=event_date,
                amount=check.amount,
                amount_bucket=get_amount_bucket(check.amount),
                fraud_type=scenario["fraud_type"],
                channel=scenario["channel"],
                confidence=scenario["confidence"],
                narrative_private=scenario["narrative"],
                narrative_shareable=f"Fraud indicator detected via {scenario['channel'].value} channel" if random.random() > 0.5 else None,
                sharing_level=random.choice([0, 1, 2]),  # Mix of sharing levels
                status=random.choice([FraudEventStatus.DRAFT, FraudEventStatus.SUBMITTED, FraudEventStatus.SUBMITTED]),
                created_by_user_id=reviewer.id,
                submitted_at=datetime.now(timezone.utc) if random.random() > 0.3 else None,
                submitted_by_user_id=reviewer.id if random.random() > 0.3 else None,
            )
            self.db.add(fraud_event)
            count += 1

            # Create shared artifact for submitted events with network sharing
            if fraud_event.status == FraudEventStatus.SUBMITTED and fraud_event.sharing_level >= 1:
                artifact = FraudSharedArtifact(
                    id=str(uuid.uuid4()),
                    tenant_id="DEMO-TENANT-000000000000000000000000",
                    fraud_event_id=fraud_event.id,
                    sharing_level=fraud_event.sharing_level,
                    occurred_at=event_date,
                    occurred_month=event_date.strftime("%Y-%m"),
                    fraud_type=scenario["fraud_type"],
                    channel=scenario["channel"],
                    amount_bucket=fraud_event.amount_bucket,
                    indicators_json={
                        "routing_hash": f"demo_routing_{uuid.uuid4().hex[:8]}",
                        "payee_hash": f"demo_payee_{uuid.uuid4().hex[:8]}",
                        "check_fingerprint": f"demo_fp_{uuid.uuid4().hex[:12]}",
                    } if fraud_event.sharing_level == 2 else None,
                    pepper_version=1,
                    is_active=True,
                )
                self.db.add(artifact)

        await self.db.flush()
        return count

    async def _seed_network_alerts(self) -> int:
        """Create network match alerts for fraud intelligence demonstration."""
        count = 0

        # Create alerts for ~40% of checks to ensure users see network intelligence in demos
        # Prioritize higher risk checks but include some lower risk ones too
        high_risk_checks = [c for c in self.demo_checks if c.risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]]
        medium_risk_checks = [c for c in self.demo_checks if c.risk_level == RiskLevel.MEDIUM]
        low_risk_checks = [c for c in self.demo_checks if c.risk_level == RiskLevel.LOW]

        # Take most high-risk, some medium, few low for variety
        alertable_checks = (
            high_risk_checks[:15] +  # Most high-risk checks
            medium_risk_checks[:10] +  # Some medium risk
            low_risk_checks[:5]  # A few low risk (false positive scenarios)
        )

        for check in alertable_checks:
            # Vary the severity and match count
            severity = random.choice(["low", "medium", "high"])
            total_matches = random.randint(1, 8)
            distinct_institutions = min(total_matches, random.randint(1, 5))

            # Generate realistic match reasons
            match_reasons = {}
            possible_reasons = [
                ("routing_hash", "Routing number matched prior fraud reports"),
                ("payee_hash", "Payee name pattern matched known fraud"),
                ("check_fingerprint", "Check image characteristics match known counterfeits"),
                ("amount_pattern", "Amount pattern consistent with fraud ring activity"),
            ]

            num_reasons = random.randint(1, 3)
            selected_reasons = random.sample(possible_reasons, num_reasons)

            # Fraud types and channels for realistic match reasons
            fraud_type_options = [
                "counterfeit_check", "forged_signature", "altered_check",
                "duplicate_deposit", "account_takeover", "check_kiting"
            ]
            channel_options = ["branch", "mobile", "atm", "rdc", "online"]

            for reason_key, reason_desc in selected_reasons:
                months_back = random.randint(1, 12)
                first_seen = (datetime.now(timezone.utc) - timedelta(days=30 * months_back)).strftime("%Y-%m")
                last_seen = (datetime.now(timezone.utc) - timedelta(days=random.randint(1, 30))).strftime("%Y-%m")

                match_reasons[reason_key] = {
                    "count": random.randint(1, total_matches),
                    "first_seen": first_seen,
                    "last_seen": last_seen,
                    "description": reason_desc,
                    "fraud_types": random.sample(fraud_type_options, random.randint(1, 3)),
                    "channels": random.sample(channel_options, random.randint(1, 2)),
                }

            alert = NetworkMatchAlert(
                id=str(uuid.uuid4()),
                tenant_id="DEMO-TENANT-000000000000000000000000",
                check_item_id=check.id,
                matched_artifact_ids=[str(uuid.uuid4()) for _ in range(total_matches)],
                match_reasons=match_reasons,
                severity=severity,
                total_matches=total_matches,
                distinct_institutions=distinct_institutions,
                earliest_match_date=datetime.now(timezone.utc) - timedelta(days=random.randint(30, 180)),
                latest_match_date=datetime.now(timezone.utc) - timedelta(days=random.randint(1, 30)),
                dismissed_at=datetime.now(timezone.utc) if random.random() < 0.2 else None,  # 20% dismissed
                dismissed_by_user_id=self.demo_users.get("reviewer", self.demo_users.get("system_admin")).id if random.random() < 0.2 else None,
                dismissed_reason="False positive - verified with customer" if random.random() < 0.2 else None,
                last_checked_at=datetime.now(timezone.utc),
            )
            self.db.add(alert)
            count += 1

        await self.db.flush()
        return count

    async def _seed_network_trend_data(self) -> int:
        """Seed network-wide fraud trend data from simulated external institutions.

        This creates FraudSharedArtifact records from fake "other" tenants to populate
        the Network Fraud Trends dashboard with realistic demo data.
        """
        count = 0

        # Simulated external financial institutions (max 36 chars for tenant_id)
        external_tenants = [
            "DEMO-NET-BANK-A-0000000000000001",
            "DEMO-NET-BANK-B-0000000000000002",
            "DEMO-NET-BANK-C-0000000000000003",
            "DEMO-NET-CREDIT-000000000000004",
            "DEMO-NET-REGION-000000000000005",
        ]

        fraud_types = list(FraudType)
        channels = list(FraudChannel)

        # Generate data for the last 6 months
        now = datetime.now(timezone.utc)

        for months_ago in range(6):
            month_date = now - timedelta(days=30 * months_ago)
            occurred_month = month_date.strftime("%Y-%m")

            # Each month, create varying amounts of fraud data from different institutions
            for tenant_id in external_tenants:
                # Random number of fraud events per institution per month (5-25)
                num_events = random.randint(5, 25)

                for _ in range(num_events):
                    fraud_type = random.choice(fraud_types)
                    channel = random.choice(channels)

                    # Realistic amount distribution
                    amount = Decimal(str(random.choice([
                        random.uniform(100, 500),
                        random.uniform(500, 2000),
                        random.uniform(2000, 10000),
                        random.uniform(10000, 50000),
                    ]))).quantize(Decimal("0.01"))

                    # Random day within the month
                    day_offset = random.randint(0, 28)
                    occurred_at = month_date.replace(day=1) + timedelta(days=day_offset)

                    artifact = FraudSharedArtifact(
                        id=str(uuid.uuid4()),
                        tenant_id=tenant_id,
                        fraud_event_id=None,  # No linked fraud event for network data
                        sharing_level=SharingLevel.AGGREGATE.value,  # Level 1 - aggregate sharing
                        occurred_at=occurred_at,
                        occurred_month=occurred_month,
                        fraud_type=fraud_type,
                        channel=channel,
                        amount_bucket=get_amount_bucket(amount),
                        indicators_json=None,  # No indicators for aggregate sharing
                        pepper_version=1,
                        is_active=True,
                    )
                    self.db.add(artifact)
                    count += 1

        # Also create some trend data for the demo tenant to show "your bank" comparison
        for months_ago in range(6):
            month_date = now - timedelta(days=30 * months_ago)
            occurred_month = month_date.strftime("%Y-%m")

            # Fewer events for "your bank" (3-12 per month)
            num_events = random.randint(3, 12)

            for _ in range(num_events):
                fraud_type = random.choice(fraud_types)
                channel = random.choice(channels)

                amount = Decimal(str(random.uniform(500, 25000))).quantize(Decimal("0.01"))
                day_offset = random.randint(0, 28)
                occurred_at = month_date.replace(day=1) + timedelta(days=day_offset)

                artifact = FraudSharedArtifact(
                    id=str(uuid.uuid4()),
                    tenant_id="DEMO-TENANT-000000000000000000000000",
                    fraud_event_id=None,
                    sharing_level=SharingLevel.AGGREGATE.value,
                    occurred_at=occurred_at,
                    occurred_month=occurred_month,
                    fraud_type=fraud_type,
                    channel=channel,
                    amount_bucket=get_amount_bucket(amount),
                    indicators_json=None,
                    pepper_version=1,
                    is_active=True,
                )
                self.db.add(artifact)
                count += 1

        await self.db.flush()
        return count

    def _select_queue_for_status(self, status: CheckStatus, requires_dual_control: bool) -> Queue | None:
        """Select appropriate queue based on status."""
        if status == CheckStatus.PENDING_DUAL_CONTROL:
            return self.demo_queues.get("Demo Dual Control")
        elif status == CheckStatus.ESCALATED:
            return self.demo_queues.get("Demo Escalation")
        elif status in [CheckStatus.NEW, CheckStatus.IN_REVIEW]:
            return self.demo_queues.get("Demo Standard Review")
        return None

    def _calculate_priority(self, scenario_config, amount: Decimal) -> int:
        """Calculate priority based on scenario and amount."""
        base_priority = {"low": 10, "medium": 50, "high": 75, "critical": 100}.get(
            scenario_config.risk_level, 10
        )

        # Boost priority for high amounts
        if amount >= settings.HIGH_PRIORITY_THRESHOLD:
            base_priority += 25

        return min(base_priority, 100)


async def seed_demo_data(reset: bool = False, count: int = 60) -> dict:
    """Main entry point for seeding demo data."""
    async with AsyncSessionLocal() as db:
        seeder = DemoSeeder(db, count)
        stats = await seeder.seed_all(reset=reset)
        return stats


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Seed demo data for Check Review Console")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Clear existing demo data before seeding",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=60,
        help="Number of check items to create (default: 60)",
    )

    args = parser.parse_args()

    print("=" * 60)
    print("Demo Data Seeder")
    print("=" * 60)
    print(f"Environment: {settings.ENVIRONMENT}")
    print(f"Demo Mode: {settings.DEMO_MODE}")
    print(f"Reset: {args.reset}")
    print(f"Count: {args.count}")
    print("=" * 60)

    if settings.ENVIRONMENT == "production":
        print("ERROR: Cannot seed demo data in production environment!")
        return 1

    stats = asyncio.run(seed_demo_data(reset=args.reset, count=args.count))

    print("\nSeeding complete!")
    print("-" * 40)
    for key, value in stats.items():
        print(f"  {key}: {value}")
    print("-" * 40)

    return 0


if __name__ == "__main__":
    exit(main())
