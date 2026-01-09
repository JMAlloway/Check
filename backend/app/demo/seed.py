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
from app.models.check import CheckHistory, CheckImage, CheckItem, CheckStatus, RiskLevel, AccountType
from app.models.decision import Decision, DecisionAction, DecisionType
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
            "check_items": 0,
            "check_images": 0,
            "check_history": 0,
            "decisions": 0,
            "audit_events": 0,
        }

        if reset:
            await self._clear_demo_data()
            print("Cleared existing demo data")

        # Seed in order of dependencies
        stats["users"] = await self._seed_users()
        stats["queues"] = await self._seed_queues()
        stats["check_items"], stats["check_images"] = await self._seed_checks()
        stats["check_history"] = await self._seed_check_history()
        stats["decisions"] = await self._seed_decisions()
        stats["audit_events"] = await self._seed_audit_events()

        await self.db.commit()
        return stats

    async def _clear_demo_data(self):
        """Clear all demo data from the database using is_demo flag."""
        # Delete in reverse order of dependencies using is_demo column

        # Clear audit logs first
        await self.db.execute(delete(AuditLog).where(AuditLog.is_demo == True))

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
                tenant_id="demo",
                email=f"{creds['username']}@demo.example.com",
                username=creds["username"],
                hashed_password=get_password_hash(creds["password"]),
                full_name=f"Demo {role.title()} User",
                is_active=True,
                is_superuser=(role == "admin"),
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

            check_item = CheckItem(
                id=str(uuid.uuid4()),
                external_item_id=f"DEMO-CHECK-{i+1:04d}-{uuid.uuid4().hex[:8]}",
                source_system="demo",
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
                check_item.assigned_reviewer_id = self.demo_users.get("reviewer", self.demo_users.get("admin")).id

            if status == CheckStatus.PENDING_DUAL_CONTROL:
                check_item.assigned_approver_id = self.demo_users.get("approver", self.demo_users.get("admin")).id

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
        """Create historical check data for side-by-side comparison."""
        count = 0

        for account in DEMO_ACCOUNTS:
            # Create 5-15 historical checks per account
            history_count = random.randint(5, 15)

            for i in range(history_count):
                check_date = datetime.now(timezone.utc) - timedelta(
                    days=random.randint(30, 365)
                )
                amount = account.avg_check_amount * Decimal(str(random.uniform(0.5, 1.5)))

                history = CheckHistory(
                    id=str(uuid.uuid4()),
                    account_id=account.account_id,
                    check_number=f"{random.randint(1000, 9999)}",
                    amount=amount.quantize(Decimal("0.01")),
                    check_date=check_date,
                    payee_name=random.choice(DEMO_PAYEES),
                    status=random.choice(["cleared", "cleared", "cleared", "returned"]),
                    return_reason="NSF" if random.random() < 0.1 else None,
                    external_item_id=f"DEMO-HIST-{account.account_id}-{i}",
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

                reviewer = self.demo_users.get("reviewer", self.demo_users.get("admin"))
                decision = Decision(
                    id=str(uuid.uuid4()),
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
                    approver = self.demo_users.get("approver", self.demo_users.get("admin"))
                    approval_decision = Decision(
                        id=str(uuid.uuid4()),
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
            reviewer = self.demo_users.get("reviewer", self.demo_users.get("admin"))
            login_time = check.presented_date - timedelta(minutes=random.randint(5, 60))

            audit_log = AuditLog(
                id=str(uuid.uuid4()),
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
