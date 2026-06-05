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


# Synthetic account data - NO REAL PII.
# Generated procedurally to mirror a ~$2B-asset community/retail bank's deposit
# base: mostly consumer households and small businesses, with a smaller tail of
# commercial relationships and a few nonprofits/municipal accounts. All names,
# balances and behavior are fully synthetic. Generation is deterministic (fixed
# seed) so account IDs are stable across the API and the seeder within a run.
import random as _random

_FIRST_NAMES = [
    "James",
    "Mary",
    "Robert",
    "Patricia",
    "John",
    "Jennifer",
    "Michael",
    "Linda",
    "David",
    "Elizabeth",
    "William",
    "Barbara",
    "Richard",
    "Susan",
    "Joseph",
    "Jessica",
    "Thomas",
    "Karen",
    "Christopher",
    "Sarah",
    "Daniel",
    "Nancy",
    "Matthew",
    "Lisa",
    "Anthony",
    "Margaret",
    "Mark",
    "Sandra",
    "Carlos",
    "Maria",
    "Luis",
    "Elena",
    "Wei",
    "Mei",
    "Aisha",
    "Omar",
    "Priya",
    "Raj",
    "Sofia",
    "Diego",
]
_LAST_NAMES = [
    "Smith",
    "Johnson",
    "Williams",
    "Brown",
    "Jones",
    "Garcia",
    "Miller",
    "Davis",
    "Rodriguez",
    "Martinez",
    "Hernandez",
    "Lopez",
    "Gonzalez",
    "Wilson",
    "Anderson",
    "Thomas",
    "Taylor",
    "Moore",
    "Jackson",
    "Martin",
    "Lee",
    "Perez",
    "Thompson",
    "White",
    "Harris",
    "Clark",
    "Nguyen",
    "Patel",
    "Kim",
    "Cohen",
    "Murphy",
    "Reed",
    "Bailey",
    "Foster",
    "Hughes",
]
_BUSINESS_NAMES = [
    "Acme Industrial Corp",
    "Williams Property Management LLC",
    "Garcia Landscaping Services",
    "Summit Office Supplies Inc",
    "BrightWell Cleaning Services",
    "Apex Contracting LLC",
    "Northstar Marketing Agency",
    "Brightline IT Solutions",
    "Cardinal Shipping & Logistics",
    "Henderson Legal Group",
    "Whitaker & Associates CPAs",
    "Precision Maintenance Co",
    "Beacon Consulting Group",
    "Sentry Security Services",
    "Garden State Catering",
    "Pinnacle Training Institute",
    "Lakeside Auto Repair",
    "Maplewood Family Dental",
    "Riverbend Hardware Supply",
    "Copperline Electric Co",
    "Fairfax Medical Associates",
    "Oakhurst Veterinary Clinic",
    "Harbor Point Restaurant Group",
    "Stonebridge Construction LLC",
]
_COMMERCIAL_NAMES = [
    "Davis Industries Inc",
    "Meridian Manufacturing Co",
    "Continental Freight Systems",
    "Vanguard Distribution LLC",
    "Ironwood Building Products",
    "Atlas Food Wholesale Inc",
]
_NONPROFIT_NAMES = [
    "Riverside Community Foundation",
    "Hope Valley Food Bank",
    "Lincoln County Youth Center",
    "St. Augustine Parish",
]


def _person_name(rng):
    return f"{rng.choice(_FIRST_NAMES)} {rng.choice(_LAST_NAMES)}"


def _build_demo_accounts():
    rng = _random.Random(20240601)
    accounts = []
    # Community/retail deposit mix: consumer-heavy with a small-business core.
    mix = ["consumer"] * 24 + ["business"] * 10 + ["commercial"] * 4 + ["non_profit"] * 2
    biz_names = _BUSINESS_NAMES.copy()
    comm_names = _COMMERCIAL_NAMES.copy()
    np_names = _NONPROFIT_NAMES.copy()
    rng.shuffle(biz_names)
    rng.shuffle(comm_names)
    rng.shuffle(np_names)
    bi = ci = ni = 0

    for i, acct_type in enumerate(mix, start=1):
        # ~10% of accounts are newly opened (<90 days) - drives new-account holds.
        if rng.random() < 0.10:
            tenure = rng.randint(5, 89)
        else:
            tenure = rng.randint(180, 18 * 365)

        if acct_type == "consumer":
            avg_balance = Decimal(str(round(rng.uniform(400, 18000), 2)))
            avg_check = Decimal(str(round(rng.uniform(45, 1200), 2)))
            freq = rng.randint(1, 12)
            holder = _person_name(rng)
            business = None
        elif acct_type == "business":
            avg_balance = Decimal(str(round(rng.uniform(8000, 160000), 2)))
            avg_check = Decimal(str(round(rng.uniform(900, 15000), 2)))
            freq = rng.randint(8, 40)
            business = biz_names[bi % len(biz_names)]
            bi += 1
            holder = _person_name(rng)
        elif acct_type == "commercial":
            avg_balance = Decimal(str(round(rng.uniform(120000, 1100000), 2)))
            avg_check = Decimal(str(round(rng.uniform(10000, 60000), 2)))
            freq = rng.randint(20, 80)
            business = comm_names[ci % len(comm_names)]
            ci += 1
            holder = _person_name(rng)
        else:  # non_profit
            avg_balance = Decimal(str(round(rng.uniform(20000, 220000), 2)))
            avg_check = Decimal(str(round(rng.uniform(1500, 12000), 2)))
            freq = rng.randint(4, 25)
            business = np_names[ni % len(np_names)]
            ni += 1
            holder = business

        # A minority of accounts have prior returned items (drives risk history).
        returned = rng.randint(1, 3) if rng.random() < 0.18 else 0

        accounts.append(
            DemoAccount(
                account_id=f"DEMO-ACCT-{i:03d}",
                account_number_masked=f"****{rng.randint(0, 9999):04d}",
                account_type=acct_type,
                tenure_days=tenure,
                avg_balance=avg_balance,
                avg_check_amount=avg_check,
                check_frequency=freq,
                returned_items=returned,
                holder_name=holder,
                business_name=business,
            )
        )
    return accounts


DEMO_ACCOUNTS = _build_demo_accounts()

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
    "Summit Office Supplies Inc",
    "BrightWell Cleaning Services",
    "Michael Donovan",
    "Sarah Chen",
    "Metro Water & Power",
    "Liberty Mutual Insurance",
    "Hawthorne Property Group",
    "Apex Contracting LLC",
    "Northstar Marketing Agency",
    "Brightline IT Solutions",
    "Cardinal Shipping & Logistics",
    "Henderson Legal Group",
    "Whitaker & Associates CPAs",
    "Precision Maintenance Co",
    "Beacon Consulting Group",
    "Sentry Security Services",
    "Garden State Catering",
    "Pinnacle Training Institute",
    # Utilities & telecom
    "Regional Gas & Electric",
    "Clearstream Communications",
    "Citywide Waste Management",
    "Verizon Business",
    # Insurance, mortgage & financial
    "Allstate Insurance Agency",
    "Heartland Mortgage Servicing",
    "First Capital Leasing",
    "Enterprise Fleet Management",
    # Government & tax
    "State Department of Revenue",
    "County Tax Collector",
    "U.S. Treasury",
    "Municipal Court Clerk",
    # Healthcare
    "Fairfax Medical Associates",
    "Lakeview Family Pharmacy",
    "Mercy Regional Hospital",
    "Brightsmile Dental Care",
    # Retail, vendors & payroll
    "Costco Wholesale",
    "Home Depot Pro",
    "Staples Business Advantage",
    "ADP Payroll Services",
    "Paychex Inc",
    "Grainger Industrial Supply",
    # Individuals (consumer payees)
    "Daniel Kim",
    "Aisha Hernandez",
    "Thomas Reed",
    "Priya Patel",
    "Carlos Martinez",
    "Susan Bailey",
    "Omar Foster",
    "Jennifer Murphy",
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


# ---------------------------------------------------------------------------
# Daily volume backdrop (demo-only, illustrative)
#
# A ~$2B-asset community bank presents thousands of deposited items per day,
# the vast majority of which clear straight through automatically. Only a small
# exception slice (large-dollar holds, new-account holds, date/velocity flags,
# suspected fraud) is routed to the human review queue modeled by the seeded
# check items. These helpers produce a stable, realistic daily-volume context
# so the dashboard can frame the review queue against whole-bank throughput.
#
# The numbers are illustrative and deterministic per calendar date; they are
# NOT backed by per-item rows and are clearly labeled as context in the UI.
# ---------------------------------------------------------------------------
import datetime as _dt
import random as _rnd

# Share of presented items routed to a human review queue (the exception rate).
# ~2.67% routed => ~97.33% straight-through, which for a ~267-item exception
# queue implies ~10,000 items presented per normal business day.
DEMO_EXCEPTION_RATE = 0.0267
DEMO_STP_RATE = round(1 - DEMO_EXCEPTION_RATE, 4)  # 0.9733
# Baseline items presented on a normal mid-week day for a ~$2B community bank.
DEMO_BASE_PRESENTED = 10000
# Relative presented volume by weekday (Mon heavy, weekends light).
_WEEKDAY_FACTOR = {0: 1.12, 1: 1.04, 2: 1.0, 3: 1.0, 4: 1.06, 5: 0.32, 6: 0.16}


def _presented_for_date(target_date: _dt.date) -> int:
    """Deterministic presented-volume for a date.

    Seeded by the date only, so the value is stable for a given day (and across
    reseeds) but varies realistically day to day. The wobble is kept tight so
    the headline reads like a real, steady daily volume rather than noise.
    """
    rng = _rnd.Random(target_date.toordinal())
    factor = _WEEKDAY_FACTOR[target_date.weekday()]
    return int(round(DEMO_BASE_PRESENTED * factor * rng.uniform(0.985, 1.015)))


def get_daily_volume_context(
    target_date: _dt.date | None = None,
    routed_to_review: int | None = None,
) -> dict:
    """Return an illustrative whole-bank item-volume snapshot for a date.

    A single exception-rate model is used everywhere so the dashboard and the
    reports never tell a contradictory story:
      straight-through rate = DEMO_STP_RATE (fixed, ~97.3%)
      presented = routed / exception_rate  (when anchored to the live queue)
                = deterministic per-date baseline (for historical days)

    When ``routed_to_review`` is supplied (the live count of items in the review
    queue) the whole-bank figures are anchored to it, so "Today across the bank"
    stays consistent with the real queue (~267 routed => ~10k presented).
    """
    target_date = target_date or _dt.date.today()

    if routed_to_review is not None:
        routed = max(int(routed_to_review), 0)
        presented = round(routed / DEMO_EXCEPTION_RATE) if routed > 0 else 0
        straight_through = presented - routed
    else:
        presented = _presented_for_date(target_date)
        routed = round(presented * DEMO_EXCEPTION_RATE)
        straight_through = presented - routed

    return {
        "date": target_date.isoformat(),
        "presented": presented,
        "straight_through_cleared": straight_through,
        "straight_through_rate": DEMO_STP_RATE,
        "routed_to_review": routed,
    }


def get_daily_volume_series(days: int = 7, end_date: _dt.date | None = None) -> list[dict]:
    """Return the daily volume backdrop for the last ``days`` days (inclusive)."""
    end_date = end_date or _dt.date.today()
    return [
        get_daily_volume_context(end_date - _dt.timedelta(days=offset))
        for offset in range(days - 1, -1, -1)
    ]
