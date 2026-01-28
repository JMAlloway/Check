"""
Demo scenarios and synthetic data patterns.

This module defines the "story arcs" for demo data - realistic scenarios
that demonstrate the system's capabilities without using real PII.

ALL DATA IN THIS FILE IS SYNTHETIC AND FOR DEMONSTRATION PURPOSES ONLY.

IMPORTANT: Detection flags in this file correspond to REAL capabilities:
- Amount-based flags: Calculated from avg_check_amount_30d, max_check_amount_90d
- Account tenure flags: Based on account_tenure_days
- Velocity flags: Based on check_count_7d, check_count_14d
- History flags: Based on returned_item_count_90d, overdraft_count_90d
- Date flags: Stale-dated (>180 days) and post-dated checks

NOT IMPLEMENTED (removed from demo):
- Image analysis (endorsement detection, alteration detection)
- Signature matching/verification
- Check stock analysis
- MICR image analysis
"""

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Any


class DemoScenario(str, Enum):
    """Demo scenario types for check review training."""

    # Normal scenarios - should be approved
    ROUTINE_PAYROLL = "routine_payroll"
    REGULAR_VENDOR_PAYMENT = "regular_vendor_payment"
    KNOWN_CUSTOMER_CHECK = "known_customer_check"

    # Suspicious scenarios - need review/flags (REAL detection capabilities)
    STALE_DATED = "stale_dated"
    POST_DATED = "post_dated"
    DUPLICATE_CHECK = "duplicate_check"
    UNUSUAL_AMOUNT = "unusual_amount"
    NEW_ACCOUNT_HIGH_VALUE = "new_account_high_value"
    VELOCITY_SPIKE = "velocity_spike"
    HIGH_RISK_HISTORY = "high_risk_history"
    AMOUNT_EXCEEDS_BALANCE = "amount_exceeds_balance"


@dataclass
class DemoAccount:
    """Synthetic account for demo purposes."""

    account_id: str
    account_number_masked: str
    account_type: str
    tenure_days: int
    avg_balance: Decimal
    avg_check_amount: Decimal
    check_frequency: int
    returned_items: int
    holder_name: str  # Synthetic name only
    business_name: str | None = None


@dataclass
class DemoCheckScenario:
    """Configuration for a demo check scenario."""

    scenario: DemoScenario
    amount_range: tuple[Decimal, Decimal]
    risk_level: str
    ai_recommendation: str
    ai_confidence: float
    flags: list[str]
    explanation: str
    requires_dual_control: bool = False


# Synthetic account data - NO REAL PII
DEMO_ACCOUNTS = [
    DemoAccount(
        account_id="DEMO-ACCT-001",
        account_number_masked="****1234",
        account_type="business",
        tenure_days=1825,  # 5 years
        avg_balance=Decimal("125000.00"),
        avg_check_amount=Decimal("8500.00"),
        check_frequency=15,
        returned_items=0,
        holder_name="DEMO-HOLDER-JOHNSON",
        business_name="DEMO-BIZ-ACME-CORP",
    ),
    DemoAccount(
        account_id="DEMO-ACCT-002",
        account_number_masked="****5678",
        account_type="consumer",
        tenure_days=365,
        avg_balance=Decimal("5200.00"),
        avg_check_amount=Decimal("450.00"),
        check_frequency=4,
        returned_items=1,
        holder_name="DEMO-HOLDER-SMITH",
    ),
    DemoAccount(
        account_id="DEMO-ACCT-003",
        account_number_masked="****9012",
        account_type="business",
        tenure_days=730,  # 2 years
        avg_balance=Decimal("45000.00"),
        avg_check_amount=Decimal("3200.00"),
        check_frequency=8,
        returned_items=0,
        holder_name="DEMO-HOLDER-WILLIAMS",
        business_name="DEMO-BIZ-WILLIAMS-LLC",
    ),
    DemoAccount(
        account_id="DEMO-ACCT-004",
        account_number_masked="****3456",
        account_type="consumer",
        tenure_days=90,  # New account
        avg_balance=Decimal("2100.00"),
        avg_check_amount=Decimal("350.00"),
        check_frequency=2,
        returned_items=0,
        holder_name="DEMO-HOLDER-BROWN",
    ),
    DemoAccount(
        account_id="DEMO-ACCT-005",
        account_number_masked="****7890",
        account_type="commercial",
        tenure_days=3650,  # 10 years
        avg_balance=Decimal("500000.00"),
        avg_check_amount=Decimal("25000.00"),
        check_frequency=25,
        returned_items=0,
        holder_name="DEMO-HOLDER-DAVIS",
        business_name="DEMO-BIZ-DAVIS-INDUSTRIES",
    ),
    DemoAccount(
        account_id="DEMO-ACCT-006",
        account_number_masked="****2468",
        account_type="business",
        tenure_days=180,
        avg_balance=Decimal("15000.00"),
        avg_check_amount=Decimal("2000.00"),
        check_frequency=5,
        returned_items=2,
        holder_name="DEMO-HOLDER-GARCIA",
        business_name="DEMO-BIZ-GARCIA-SERVICES",
    ),
    DemoAccount(
        account_id="DEMO-ACCT-007",
        account_number_masked="****1357",
        account_type="consumer",
        tenure_days=1095,  # 3 years
        avg_balance=Decimal("8500.00"),
        avg_check_amount=Decimal("750.00"),
        check_frequency=6,
        returned_items=0,
        holder_name="DEMO-HOLDER-MARTINEZ",
    ),
    DemoAccount(
        account_id="DEMO-ACCT-008",
        account_number_masked="****8642",
        account_type="non_profit",
        tenure_days=2555,  # 7 years
        avg_balance=Decimal("75000.00"),
        avg_check_amount=Decimal("5500.00"),
        check_frequency=12,
        returned_items=0,
        holder_name="DEMO-HOLDER-NONPROFIT",
        business_name="DEMO-BIZ-COMMUNITY-FOUNDATION",
    ),
]

# Scenario configurations - ONLY flags with REAL detection capabilities
# All flags here can be calculated from account context data
DEMO_SCENARIOS = {
    # === NORMAL SCENARIOS (no flags) ===
    DemoScenario.ROUTINE_PAYROLL: DemoCheckScenario(
        scenario=DemoScenario.ROUTINE_PAYROLL,
        amount_range=(Decimal("2500.00"), Decimal("8500.00")),
        risk_level="low",
        ai_recommendation="likely_legitimate",
        ai_confidence=0.92,
        flags=[],
        explanation="Regular payroll check consistent with account history and business pattern.",
    ),
    DemoScenario.REGULAR_VENDOR_PAYMENT: DemoCheckScenario(
        scenario=DemoScenario.REGULAR_VENDOR_PAYMENT,
        amount_range=(Decimal("1000.00"), Decimal("15000.00")),
        risk_level="low",
        ai_recommendation="likely_legitimate",
        ai_confidence=0.88,
        flags=[],
        explanation="Vendor payment matches established pattern for this business account.",
    ),
    DemoScenario.KNOWN_CUSTOMER_CHECK: DemoCheckScenario(
        scenario=DemoScenario.KNOWN_CUSTOMER_CHECK,
        amount_range=(Decimal("100.00"), Decimal("2000.00")),
        risk_level="low",
        ai_recommendation="likely_legitimate",
        ai_confidence=0.95,
        flags=[],
        explanation="Personal check from established customer with consistent history.",
    ),
    # === DATE-BASED FLAGS (REAL - calculated from check_date) ===
    DemoScenario.STALE_DATED: DemoCheckScenario(
        scenario=DemoScenario.STALE_DATED,
        amount_range=(Decimal("500.00"), Decimal("5000.00")),
        risk_level="medium",
        ai_recommendation="needs_review",
        ai_confidence=0.85,
        flags=["STALE_DATED"],
        explanation="Check date is more than 180 days old. Verify with customer if still valid.",
    ),
    DemoScenario.POST_DATED: DemoCheckScenario(
        scenario=DemoScenario.POST_DATED,
        amount_range=(Decimal("1000.00"), Decimal("10000.00")),
        risk_level="medium",
        ai_recommendation="needs_review",
        ai_confidence=0.90,
        flags=["POST_DATED"],
        explanation="Check is post-dated. Confirm customer intent before processing.",
    ),
    # === DUPLICATE DETECTION (REAL - database lookup) ===
    DemoScenario.DUPLICATE_CHECK: DemoCheckScenario(
        scenario=DemoScenario.DUPLICATE_CHECK,
        amount_range=(Decimal("500.00"), Decimal("5000.00")),
        risk_level="high",
        ai_recommendation="likely_fraud",
        ai_confidence=0.94,
        flags=["DUPLICATE_CHECK_NUMBER"],
        explanation="Check number has been used previously on this account. Potential duplicate deposit.",
        requires_dual_control=True,
    ),
    # === AMOUNT-BASED FLAGS (REAL - calculated from avg_check_amount_30d) ===
    DemoScenario.UNUSUAL_AMOUNT: DemoCheckScenario(
        scenario=DemoScenario.UNUSUAL_AMOUNT,
        amount_range=(Decimal("50000.00"), Decimal("150000.00")),
        risk_level="high",
        ai_recommendation="needs_review",
        ai_confidence=0.70,
        flags=["AMOUNT_5X_AVG", "EXCEEDS_MAX_90D"],
        explanation="Amount is 5.2x the 30-day average. Exceeds maximum check amount in past 90 days.",
        requires_dual_control=True,
    ),
    # === ACCOUNT TENURE FLAGS (REAL - calculated from account_tenure_days) ===
    DemoScenario.NEW_ACCOUNT_HIGH_VALUE: DemoCheckScenario(
        scenario=DemoScenario.NEW_ACCOUNT_HIGH_VALUE,
        amount_range=(Decimal("15000.00"), Decimal("75000.00")),
        risk_level="high",
        ai_recommendation="needs_review",
        ai_confidence=0.68,
        flags=["NEW_ACCOUNT_30D", "AMOUNT_3X_AVG"],
        explanation="Account is less than 30 days old. Check amount is 3.4x the account average.",
        requires_dual_control=True,
    ),
    # === VELOCITY FLAGS (REAL - calculated from check_count_7d/14d) ===
    DemoScenario.VELOCITY_SPIKE: DemoCheckScenario(
        scenario=DemoScenario.VELOCITY_SPIKE,
        amount_range=(Decimal("2000.00"), Decimal("8000.00")),
        risk_level="medium",
        ai_recommendation="needs_review",
        ai_confidence=0.75,
        flags=["VELOCITY_7D_HIGH", "TOTAL_AMOUNT_14D_HIGH"],
        explanation="7 checks in past 7 days vs. typical 2/week. Total amount this period exceeds normal pattern.",
    ),
    # === HISTORY-BASED FLAGS (REAL - calculated from returned_item_count, overdraft_count) ===
    DemoScenario.HIGH_RISK_HISTORY: DemoCheckScenario(
        scenario=DemoScenario.HIGH_RISK_HISTORY,
        amount_range=(Decimal("3000.00"), Decimal("12000.00")),
        risk_level="high",
        ai_recommendation="needs_review",
        ai_confidence=0.72,
        flags=["RETURNED_ITEMS_90D", "OVERDRAFT_HISTORY"],
        explanation="Account has 3 returned items and 2 overdrafts in past 90 days.",
        requires_dual_control=True,
    ),
    # === BALANCE-BASED FLAGS (REAL - calculated from current_balance) ===
    DemoScenario.AMOUNT_EXCEEDS_BALANCE: DemoCheckScenario(
        scenario=DemoScenario.AMOUNT_EXCEEDS_BALANCE,
        amount_range=(Decimal("8000.00"), Decimal("25000.00")),
        risk_level="high",
        ai_recommendation="needs_review",
        ai_confidence=0.80,
        flags=["EXCEEDS_CURRENT_BALANCE", "AMOUNT_3X_AVG"],
        explanation="Check amount exceeds current account balance. Amount is 3.1x the 30-day average.",
        requires_dual_control=True,
    ),
}

# Synthetic payee names (no real entities)
DEMO_PAYEES = [
    "DEMO-PAYEE-OFFICE-SUPPLIES-INC",
    "DEMO-PAYEE-CLEANING-SERVICES",
    "DEMO-PAYEE-EMPLOYEE-JOHN-DOE",
    "DEMO-PAYEE-EMPLOYEE-JANE-SMITH",
    "DEMO-PAYEE-UTILITY-COMPANY",
    "DEMO-PAYEE-INSURANCE-PROVIDER",
    "DEMO-PAYEE-LANDLORD-PROPERTIES",
    "DEMO-PAYEE-CONTRACTOR-SERVICES",
    "DEMO-PAYEE-MARKETING-AGENCY",
    "DEMO-PAYEE-IT-SOLUTIONS",
    "DEMO-PAYEE-SHIPPING-LOGISTICS",
    "DEMO-PAYEE-LEGAL-SERVICES",
    "DEMO-PAYEE-ACCOUNTING-FIRM",
    "DEMO-PAYEE-MAINTENANCE-CO",
    "DEMO-PAYEE-CONSULTING-GROUP",
    "DEMO-PAYEE-SECURITY-SERVICES",
    "DEMO-PAYEE-CATERING-COMPANY",
    "DEMO-PAYEE-TRAINING-INSTITUTE",
]

# Synthetic routing numbers (not real bank codes)
DEMO_ROUTING_NUMBERS = [
    "000000001",
    "000000002",
    "000000003",
    "000000004",
    "000000005",
]

# Demo user credentials info (for display purposes)
# Roles per Technical Guide Section 2.2
DEMO_CREDENTIALS = {
    "reviewer": {
        "username": "reviewer_demo",
        "password": "DemoReviewer123!",
        "role": "reviewer",
        "description": "View queue, review checks, make decisions",
    },
    "senior_reviewer": {
        "username": "senior_reviewer_demo",
        "password": "DemoSenior123!",
        "role": "senior_reviewer",
        "description": "All reviewer permissions + dual control approval",
    },
    "supervisor": {
        "username": "supervisor_demo",
        "password": "DemoSupervisor123!",
        "role": "supervisor",
        "description": "All senior permissions + queue management, reassignment",
    },
    "administrator": {
        "username": "administrator_demo",
        "password": "DemoAdmin123!",
        "role": "administrator",
        "description": "All supervisor permissions + user management, policies",
    },
    "auditor": {
        "username": "auditor_demo",
        "password": "DemoAuditor123!",
        "role": "auditor",
        "description": "Read-only access to all data and audit logs",
    },
    "system_admin": {
        "username": "system_admin_demo",
        "password": "DemoSysAdmin123!",
        "role": "system_admin",
        "description": "Full system access including configuration",
    },
}
