"""
Demo scenarios and synthetic data patterns.

This module defines the "story arcs" for demo data - realistic scenarios
that demonstrate the system's capabilities without using real PII.

ALL DATA IN THIS FILE IS SYNTHETIC AND FOR DEMONSTRATION PURPOSES ONLY.
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

    # Suspicious scenarios - need review/flags
    ALTERED_AMOUNT = "altered_amount"
    SUSPICIOUS_ENDORSEMENT = "suspicious_endorsement"
    MISMATCHED_SIGNATURE = "mismatched_signature"
    STALE_DATED = "stale_dated"
    POST_DATED = "post_dated"
    DUPLICATE_CHECK = "duplicate_check"
    UNUSUAL_AMOUNT = "unusual_amount"
    NEW_ACCOUNT_HIGH_VALUE = "new_account_high_value"
    VELOCITY_SPIKE = "velocity_spike"

    # Fraud indicators
    COUNTERFEIT_CHECK = "counterfeit_check"
    FORGED_SIGNATURE = "forged_signature"
    ACCOUNT_TAKEOVER = "account_takeover"


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

# Scenario configurations
DEMO_SCENARIOS = {
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
    DemoScenario.ALTERED_AMOUNT: DemoCheckScenario(
        scenario=DemoScenario.ALTERED_AMOUNT,
        amount_range=(Decimal("5000.00"), Decimal("25000.00")),
        risk_level="high",
        ai_recommendation="needs_review",
        ai_confidence=0.78,
        flags=["AMOUNT_ALTERATION", "INK_INCONSISTENCY"],
        explanation="Potential amount alteration detected. Written amount appears to have been modified. Recommend visual inspection of check image.",
        requires_dual_control=True,
    ),
    DemoScenario.SUSPICIOUS_ENDORSEMENT: DemoCheckScenario(
        scenario=DemoScenario.SUSPICIOUS_ENDORSEMENT,
        amount_range=(Decimal("3000.00"), Decimal("20000.00")),
        risk_level="high",
        ai_recommendation="needs_review",
        ai_confidence=0.72,
        flags=["ENDORSEMENT_IRREGULAR", "THIRD_PARTY_DEPOSIT"],
        explanation="Endorsement pattern is inconsistent with expected format. Third-party endorsement detected.",
        requires_dual_control=True,
    ),
    DemoScenario.MISMATCHED_SIGNATURE: DemoCheckScenario(
        scenario=DemoScenario.MISMATCHED_SIGNATURE,
        amount_range=(Decimal("5000.00"), Decimal("50000.00")),
        risk_level="critical",
        ai_recommendation="needs_review",
        ai_confidence=0.65,
        flags=["SIGNATURE_MISMATCH", "POSSIBLE_FORGERY"],
        explanation="Signature does not match historical signature patterns for this account. Manual verification required.",
        requires_dual_control=True,
    ),
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
    DemoScenario.DUPLICATE_CHECK: DemoCheckScenario(
        scenario=DemoScenario.DUPLICATE_CHECK,
        amount_range=(Decimal("500.00"), Decimal("5000.00")),
        risk_level="high",
        ai_recommendation="likely_fraud",
        ai_confidence=0.94,
        flags=["DUPLICATE_ITEM", "POSSIBLE_DOUBLE_DEPOSIT"],
        explanation="This check appears to match a previously deposited item. Potential duplicate deposit.",
        requires_dual_control=True,
    ),
    DemoScenario.UNUSUAL_AMOUNT: DemoCheckScenario(
        scenario=DemoScenario.UNUSUAL_AMOUNT,
        amount_range=(Decimal("50000.00"), Decimal("150000.00")),
        risk_level="high",
        ai_recommendation="needs_review",
        ai_confidence=0.70,
        flags=["AMOUNT_EXCEEDS_PATTERN", "LARGE_VALUE"],
        explanation="Check amount significantly exceeds historical patterns for this account. 4.5x standard deviation from average.",
        requires_dual_control=True,
    ),
    DemoScenario.NEW_ACCOUNT_HIGH_VALUE: DemoCheckScenario(
        scenario=DemoScenario.NEW_ACCOUNT_HIGH_VALUE,
        amount_range=(Decimal("15000.00"), Decimal("75000.00")),
        risk_level="high",
        ai_recommendation="needs_review",
        ai_confidence=0.68,
        flags=["NEW_ACCOUNT", "HIGH_VALUE", "LIMITED_HISTORY"],
        explanation="High-value check on account with less than 90 days history. Insufficient data for pattern analysis.",
        requires_dual_control=True,
    ),
    DemoScenario.VELOCITY_SPIKE: DemoCheckScenario(
        scenario=DemoScenario.VELOCITY_SPIKE,
        amount_range=(Decimal("2000.00"), Decimal("8000.00")),
        risk_level="medium",
        ai_recommendation="needs_review",
        ai_confidence=0.75,
        flags=["VELOCITY_ANOMALY", "MULTIPLE_ITEMS"],
        explanation="Unusual increase in check activity. 5 items in 48 hours vs. average of 2 per week.",
    ),
    DemoScenario.COUNTERFEIT_CHECK: DemoCheckScenario(
        scenario=DemoScenario.COUNTERFEIT_CHECK,
        amount_range=(Decimal("10000.00"), Decimal("50000.00")),
        risk_level="critical",
        ai_recommendation="likely_fraud",
        ai_confidence=0.89,
        flags=["COUNTERFEIT_INDICATORS", "STOCK_MISMATCH", "MICR_ANOMALY"],
        explanation="Multiple counterfeit indicators detected: check stock does not match known patterns, MICR line anomalies.",
        requires_dual_control=True,
    ),
    DemoScenario.FORGED_SIGNATURE: DemoCheckScenario(
        scenario=DemoScenario.FORGED_SIGNATURE,
        amount_range=(Decimal("5000.00"), Decimal("35000.00")),
        risk_level="critical",
        ai_recommendation="likely_fraud",
        ai_confidence=0.82,
        flags=["SIGNATURE_FORGERY", "UNAUTHORIZED_SIGNER"],
        explanation="Signature analysis indicates likely forgery. Significant deviation from authenticated signature samples.",
        requires_dual_control=True,
    ),
    DemoScenario.ACCOUNT_TAKEOVER: DemoCheckScenario(
        scenario=DemoScenario.ACCOUNT_TAKEOVER,
        amount_range=(Decimal("25000.00"), Decimal("100000.00")),
        risk_level="critical",
        ai_recommendation="likely_fraud",
        ai_confidence=0.86,
        flags=["ACCOUNT_TAKEOVER", "ADDRESS_CHANGE", "PAYEE_ANOMALY", "BEHAVIOR_ANOMALY"],
        explanation="Multiple indicators of potential account takeover: recent address change, unusual payee, behavior pattern deviation.",
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
DEMO_CREDENTIALS = {
    "reviewer": {
        "username": "reviewer_demo",
        "password": "DemoReviewer123!",
        "role": "reviewer",
        "description": "Check reviewer with standard permissions",
    },
    "approver": {
        "username": "approver_demo",
        "password": "DemoApprover123!",
        "role": "approver",
        "description": "Dual control approver with elevated permissions",
    },
    "admin": {
        "username": "admin_demo",
        "password": "DemoAdmin123!",
        "role": "admin",
        "description": "Administrator with full system access",
    },
}
