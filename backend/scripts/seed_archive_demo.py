"""Seed demo data for the Archive page.

Creates archived check items with decisions for the default-tenant.
This allows testing the Archive functionality with the standard test users.

Usage:
    cd backend
    python -m scripts.seed_archive_demo
"""

import asyncio
import random
import sys
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.config import settings

# Environment guard - block in secure environments
BLOCKED_ENVIRONMENTS = {"production", "pilot", "staging", "uat"}

if settings.ENVIRONMENT.lower() in BLOCKED_ENVIRONMENTS:
    print("=" * 60, file=sys.stderr)
    print("ERROR: seed_archive_demo.py cannot run in secure environments!", file=sys.stderr)
    print("=" * 60, file=sys.stderr)
    sys.exit(1)

from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models.audit import AuditAction, AuditLog
from app.models.check import (
    AccountType,
    CheckImage,
    CheckItem,
    CheckStatus,
    ItemType,
    RiskLevel,
)
from app.models.decision import Decision, DecisionAction, DecisionType
from app.models.user import User

# Demo data templates
DEMO_PAYEES = [
    "ACME Corporation",
    "Smith Construction LLC",
    "Johnson Medical Group",
    "Metro Utilities",
    "First National Insurance",
    "Global Supply Co",
    "Anderson & Associates",
    "City Water Services",
    "Pacific Electric",
    "Mountain View Properties",
    "Sunrise Healthcare",
    "Premium Auto Parts",
    "Oak Valley Farms",
    "Summit Engineering",
    "Riverside Manufacturing",
]

DEMO_ACCOUNTS = [
    {"id": "acct-001", "masked": "****1234", "type": AccountType.CONSUMER, "tenure": 1825},
    {"id": "acct-002", "masked": "****5678", "type": AccountType.BUSINESS, "tenure": 730},
    {"id": "acct-003", "masked": "****9012", "type": AccountType.COMMERCIAL, "tenure": 365},
    {"id": "acct-004", "masked": "****3456", "type": AccountType.CONSUMER, "tenure": 90},
    {"id": "acct-005", "masked": "****7890", "type": AccountType.BUSINESS, "tenure": 2555},
    {"id": "acct-006", "masked": "****2468", "type": AccountType.NON_PROFIT, "tenure": 1095},
    {"id": "acct-007", "masked": "****1357", "type": AccountType.CONSUMER, "tenure": 45},
    {"id": "acct-008", "masked": "****8642", "type": AccountType.COMMERCIAL, "tenure": 1460},
]

DEMO_ROUTING_NUMBERS = [
    "021000021",
    "011401533",
    "091000019",
    "071000013",
    "081000032",
]


async def seed_archive_data():
    """Create archived check items with decisions."""
    tenant_id = "default-tenant"

    async with AsyncSessionLocal() as db:
        # Get the reviewer user for creating decisions
        result = await db.execute(
            select(User).where(User.tenant_id == tenant_id, User.username == "reviewer")
        )
        reviewer = result.scalar_one_or_none()

        result = await db.execute(
            select(User).where(User.tenant_id == tenant_id, User.username == "senior_reviewer")
        )
        senior_reviewer = result.scalar_one_or_none()

        if not reviewer:
            print("Error: reviewer user not found. Run seed_db.py first.")
            sys.exit(1)

        reviewer_id = reviewer.id
        approver_id = senior_reviewer.id if senior_reviewer else reviewer.id

        # Check if we already have archived demo data
        result = await db.execute(
            select(CheckItem)
            .where(
                CheckItem.tenant_id == tenant_id,
                CheckItem.status.in_(
                    [CheckStatus.APPROVED, CheckStatus.REJECTED, CheckStatus.RETURNED]
                ),
                CheckItem.external_item_id.like("ARCHIVE-DEMO-%"),
            )
            .limit(1)
        )
        if result.scalar_one_or_none():
            print("Archive demo data already exists. Skipping.")
            return

        print("Creating archive demo data...")

        # Create 50 archived items with various statuses
        archive_configs = [
            # Approved items (30)
            {"status": CheckStatus.APPROVED, "action": DecisionAction.APPROVE, "count": 30},
            # Rejected items (12)
            {"status": CheckStatus.REJECTED, "action": DecisionAction.REJECT, "count": 12},
            # Returned items (8)
            {"status": CheckStatus.RETURNED, "action": DecisionAction.RETURN, "count": 8},
        ]

        item_count = 0
        decision_count = 0

        for config in archive_configs:
            for i in range(config["count"]):
                item_count += 1

                # Select random account
                account = random.choice(DEMO_ACCOUNTS)

                # Generate dates (items from last 90 days)
                days_ago = random.randint(1, 90)
                presented_date = datetime.now(timezone.utc) - timedelta(days=days_ago)
                check_date = presented_date - timedelta(days=random.randint(0, 14))
                decision_date = presented_date + timedelta(hours=random.randint(1, 48))

                # Generate amount
                amount_ranges = [
                    (50, 500),  # Small checks
                    (500, 2000),  # Medium checks
                    (2000, 10000),  # Large checks
                    (10000, 50000),  # High value (requires dual control)
                ]
                amount_range = random.choice(amount_ranges)
                amount = Decimal(str(random.uniform(*amount_range))).quantize(Decimal("0.01"))

                # Determine risk level based on amount and randomness
                if amount > 25000:
                    risk_level = random.choice([RiskLevel.HIGH, RiskLevel.CRITICAL])
                elif amount > 10000:
                    risk_level = random.choice([RiskLevel.MEDIUM, RiskLevel.HIGH])
                elif amount > 5000:
                    risk_level = random.choice([RiskLevel.LOW, RiskLevel.MEDIUM])
                else:
                    risk_level = RiskLevel.LOW

                # Dual control for high value items
                requires_dual_control = amount >= settings.DUAL_CONTROL_THRESHOLD

                item_type = ItemType.ON_US if random.random() < 0.4 else ItemType.TRANSIT

                check_item = CheckItem(
                    id=str(uuid.uuid4()),
                    tenant_id=tenant_id,
                    external_item_id=f"ARCHIVE-DEMO-{item_count:04d}-{uuid.uuid4().hex[:8]}",
                    source_system="archive-demo",
                    item_type=item_type,
                    account_id=account["id"],
                    account_number_masked=account["masked"],
                    account_type=account["type"],
                    routing_number=random.choice(DEMO_ROUTING_NUMBERS),
                    check_number=f"{random.randint(1000, 9999)}",
                    amount=amount,
                    currency="USD",
                    payee_name=random.choice(DEMO_PAYEES),
                    memo=f"Archive demo - {config['status'].value}",
                    micr_line=f"ARCH-MICR-{item_count:06d}",
                    micr_account=account["masked"].replace("*", "0"),
                    micr_routing=random.choice(DEMO_ROUTING_NUMBERS),
                    micr_check_number=f"{random.randint(1000, 9999)}",
                    presented_date=presented_date,
                    check_date=check_date,
                    status=config["status"],
                    risk_level=risk_level,
                    priority=0,
                    assigned_reviewer_id=reviewer_id,
                    sla_due_at=presented_date + timedelta(hours=settings.DEFAULT_SLA_HOURS),
                    sla_breached=random.random() < 0.05,  # 5% SLA breach
                    requires_dual_control=requires_dual_control,
                    dual_control_reason="amount_threshold" if requires_dual_control else None,
                    has_ai_flags=random.random() < 0.3,  # 30% have AI flags
                    ai_risk_score=Decimal(str(random.uniform(0.1, 0.9))).quantize(
                        Decimal("0.0001")
                    ),
                    ai_model_id="archive-demo-analyzer",
                    ai_model_version="1.0.0",
                    ai_analyzed_at=presented_date,
                    ai_recommendation=(
                        "approve" if config["action"] == DecisionAction.APPROVE else "review"
                    ),
                    ai_confidence=Decimal(str(random.uniform(0.7, 0.95))).quantize(
                        Decimal("0.0001")
                    ),
                    account_tenure_days=account["tenure"],
                    current_balance=Decimal(str(random.uniform(5000, 100000))).quantize(
                        Decimal("0.01")
                    ),
                    average_balance_30d=Decimal(str(random.uniform(5000, 100000))).quantize(
                        Decimal("0.01")
                    ),
                    avg_check_amount_30d=Decimal(str(random.uniform(500, 5000))).quantize(
                        Decimal("0.01")
                    ),
                    check_frequency_30d=random.randint(1, 20),
                    is_demo=True,
                    created_at=presented_date,
                    updated_at=decision_date,
                )
                db.add(check_item)

                # Create check images
                for image_type in ["front", "back"]:
                    image = CheckImage(
                        id=str(uuid.uuid4()),
                        check_item_id=check_item.id,
                        image_type=image_type,
                        external_image_id=f"ARCH-IMG-{check_item.id}-{image_type}",
                        storage_path=f"/archive-demo/images/{check_item.id}/{image_type}.png",
                        content_type="image/png",
                        file_size=random.randint(50000, 200000),
                        width=1200,
                        height=600,
                        dpi=200,
                        is_demo=True,
                    )
                    db.add(image)

                # Create decision record
                decision_notes = {
                    DecisionAction.APPROVE: [
                        "Verified signature matches account holder records",
                        "Amount consistent with account history",
                        "All security features validated",
                        "Customer verified via callback",
                        "Standard business payment - approved",
                    ],
                    DecisionAction.REJECT: [
                        "Signature mismatch detected",
                        "Account flagged for suspicious activity",
                        "Check appears altered",
                        "Duplicate deposit attempt",
                        "Customer reported check stolen",
                    ],
                    DecisionAction.RETURN: [
                        "Insufficient funds in account",
                        "Account closed - return to maker",
                        "Stop payment requested",
                        "Stale dated check",
                        "Post-dated check - returning",
                    ],
                }

                decision = Decision(
                    id=str(uuid.uuid4()),
                    tenant_id=tenant_id,
                    check_item_id=check_item.id,
                    user_id=reviewer_id,
                    decision_type=(
                        DecisionType.REVIEW_RECOMMENDATION
                        if requires_dual_control
                        else DecisionType.APPROVAL_DECISION
                    ),
                    action=config["action"],
                    notes=random.choice(decision_notes[config["action"]]),
                    previous_status=CheckStatus.IN_REVIEW.value,
                    new_status=config["status"].value,
                    is_dual_control_required=requires_dual_control,
                    ai_assisted=random.random() < 0.4,
                    is_demo=True,
                    created_at=decision_date,
                )
                db.add(decision)
                decision_count += 1

                # Add approver decision for dual control items
                if requires_dual_control:
                    approval_decision = Decision(
                        id=str(uuid.uuid4()),
                        tenant_id=tenant_id,
                        check_item_id=check_item.id,
                        user_id=approver_id,
                        decision_type=DecisionType.APPROVAL_DECISION,
                        action=config["action"],
                        notes=f"Dual control approval - {config['status'].value}",
                        previous_status=CheckStatus.PENDING_DUAL_CONTROL.value,
                        new_status=config["status"].value,
                        dual_control_approver_id=approver_id,
                        dual_control_approved_at=decision_date
                        + timedelta(hours=random.randint(1, 4)),
                        is_demo=True,
                        created_at=decision_date + timedelta(hours=random.randint(1, 4)),
                    )
                    db.add(approval_decision)
                    decision_count += 1

                # Create audit log entry for the decision
                audit_log = AuditLog(
                    id=str(uuid.uuid4()),
                    tenant_id=tenant_id,
                    timestamp=decision_date,
                    user_id=reviewer_id,
                    username=reviewer.username,
                    ip_address="127.0.0.1",
                    action=AuditAction.DECISION_MADE,
                    resource_type="check_item",
                    resource_id=check_item.id,
                    description=f"Decision: {config['action'].value} - {check_item.external_item_id}",
                    is_demo=True,
                )
                db.add(audit_log)

        await db.commit()

        print(f"Created {item_count} archived check items")
        print(f"Created {decision_count} decision records")
        print("\nArchive demo data seeded successfully!")
        print("\nData breakdown:")
        print("  - 30 Approved items")
        print("  - 12 Rejected items")
        print("  - 8 Returned items")
        print("\nYou can now view the Archive page with demo data.")


if __name__ == "__main__":
    asyncio.run(seed_archive_data())
