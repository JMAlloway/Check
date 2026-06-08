"""Per-persona (role-based) integration tests for the demo.

These tests exercise the REAL RBAC + entitlement stack by seeding actual users
with real roles (via the demo RBAC catalog) and real approval entitlements,
rather than synthesizing permissions in the JWT. That distinction matters: the
token-synthesis path in conftest materializes permissions as bare action names
(``"review"``) which trips the EntitlementService's permission-name fallback,
masking the entitlement requirement. Real users carry permission names like
``check_item:review`` and therefore require an explicit entitlement -- the exact
gap that let a "reviewers can't record decisions" regression ship green.

What this guards:
- Every demo role can load the screens it should, and is denied the ones it
  shouldn't (no silent 500s, intentional 403s).
- A front-line reviewer can actually record a decision (REVIEW entitlement).
- Dual control is genuinely two-person and entitlement-gated.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
import pytest_asyncio

from app.core.security import create_access_token, get_password_hash
from app.demo.rbac import seed_rbac
from app.models.check import CheckItem, CheckStatus, ItemType, RiskLevel
from app.models.decision import Decision, DecisionAction, DecisionType
from app.models.queue import ApprovalEntitlement, ApprovalEntitlementType
from app.models.user import User

TID = "DEMO-TENANT-000000000000000000000000"

# role -> approval entitlement types (mirrors app/demo/seed.py)
ENTITLEMENTS = {
    "reviewer": [ApprovalEntitlementType.REVIEW],
    "senior_reviewer": [ApprovalEntitlementType.REVIEW, ApprovalEntitlementType.APPROVE],
    "supervisor": [ApprovalEntitlementType.REVIEW, ApprovalEntitlementType.APPROVE],
    "administrator": [ApprovalEntitlementType.REVIEW, ApprovalEntitlementType.APPROVE],
    "auditor": [],
    "system_admin": [],
}


def _headers(user: User) -> dict:
    token = create_access_token(
        subject=user.id,
        additional_claims={"tenant_id": user.tenant_id, "username": user.username},
    )
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def personas(db_session):
    """Seed the 6 demo roles as real users with entitlements + a few checks."""
    role_map = await seed_rbac(db_session)
    now = datetime.now(timezone.utc)

    users: dict[str, User] = {}
    for role in role_map:
        u = User(
            id=f"persona-{role}",
            tenant_id=TID,
            username=f"{role}_persona",
            email=f"{role}@persona.test",
            full_name=f"{role} persona",
            hashed_password=get_password_hash("Passw0rd!"),
            is_active=True,
            is_superuser=(role == "system_admin"),
            mfa_enabled=False,
        )
        u.roles = [role_map[role]]
        db_session.add(u)
        for etype in ENTITLEMENTS[role]:
            db_session.add(
                ApprovalEntitlement(
                    tenant_id=TID,
                    user_id=u.id,
                    entitlement_type=etype,
                    is_active=True,
                    effective_from=now - timedelta(days=1),
                )
            )
        users[role] = u

    # A simple low-value item (no dual control) and a dual-control item with a
    # pending recommendation by the reviewer.
    simple = CheckItem(
        id="persona-simple",
        tenant_id=TID,
        source_system="test_core",
        external_item_id="EXT-SIMPLE",
        account_id="acct-s",
        account_number_masked="****0001",
        account_type="consumer",
        amount=Decimal("750.00"),
        status=CheckStatus.NEW,
        risk_level=RiskLevel.LOW,
        item_type=ItemType.ON_US,
        requires_dual_control=False,
        presented_date=now,
    )
    db_session.add(simple)

    dc_item = CheckItem(
        id="persona-dc",
        tenant_id=TID,
        source_system="test_core",
        external_item_id="EXT-DC",
        account_id="acct-d",
        account_number_masked="****0002",
        account_type="business",
        amount=Decimal("85000.00"),
        status=CheckStatus.PENDING_DUAL_CONTROL,
        risk_level=RiskLevel.HIGH,
        item_type=ItemType.TRANSIT,
        requires_dual_control=True,
        presented_date=now,
    )
    db_session.add(dc_item)
    await db_session.flush()

    rec = Decision(
        id="persona-dc-rec",
        tenant_id=TID,
        check_item_id=dc_item.id,
        user_id=users["reviewer"].id,
        decision_type=DecisionType.REVIEW_RECOMMENDATION,
        action=DecisionAction.APPROVE,
        is_dual_control_required=True,
        dual_control_approved_at=None,
        previous_status=CheckStatus.IN_REVIEW.value,
        new_status=CheckStatus.PENDING_DUAL_CONTROL.value,
    )
    db_session.add(rec)
    dc_item.pending_dual_control_decision_id = rec.id

    await db_session.commit()
    return {"users": users}


# (role, endpoint) -> expected status. Encodes the verified access matrix.
MATRIX = [
    # everyone can see their dashboard / queues / checks
    ("reviewer", "/api/v1/reports/dashboard", 200),
    ("auditor", "/api/v1/reports/dashboard", 200),
    ("system_admin", "/api/v1/reports/dashboard", 200),
    # audit log: privileged + auditor only
    ("reviewer", "/api/v1/audit/logs?page_size=5", 403),
    ("senior_reviewer", "/api/v1/audit/logs?page_size=5", 403),
    ("supervisor", "/api/v1/audit/logs?page_size=5", 200),
    ("auditor", "/api/v1/audit/logs?page_size=5", 200),
    # approvals queue: approvers only (not reviewer, not auditor)
    ("reviewer", "/api/v1/decisions/pending-approvals", 403),
    ("senior_reviewer", "/api/v1/decisions/pending-approvals", 200),
    ("auditor", "/api/v1/decisions/pending-approvals", 403),
    # decision commit service (connector): supervisor+ only
    ("reviewer", "/api/v1/connector/dashboard", 403),
    ("supervisor", "/api/v1/connector/dashboard", 200),
    ("administrator", "/api/v1/connector/dashboard", 200),
    # decisions CSV export: report:export holders
    ("reviewer", "/api/v1/reports/export/decisions", 403),
    ("supervisor", "/api/v1/reports/export/decisions", 200),
    ("auditor", "/api/v1/reports/export/decisions", 200),
    # security incidents: superuser only
    ("administrator", "/api/v1/security/incidents", 403),
    ("system_admin", "/api/v1/security/incidents", 200),
    # image intake connector: supervisor+ only
    ("reviewer", "/api/v1/image-connectors/", 403),
    ("administrator", "/api/v1/image-connectors/", 200),
    # tenant fraud config: administrator role (+ superuser) only
    ("administrator", "/api/v1/fraud/config", 200),
    ("supervisor", "/api/v1/fraud/config", 403),
    ("auditor", "/api/v1/fraud/config", 403),
    ("system_admin", "/api/v1/fraud/config", 200),
]


@pytest.mark.parametrize("role,endpoint,expected", MATRIX)
def test_persona_access_matrix(personas, client, role, endpoint, expected):
    """Each role gets exactly the access it should on the screens it loads."""
    user = personas["users"][role]
    resp = client.get(endpoint, headers=_headers(user))
    assert (
        resp.status_code == expected
    ), f"{role} {endpoint} -> {resp.status_code} (want {expected})"


def test_reviewer_can_record_decision(personas, client):
    """A front-line reviewer must be able to record a recommendation.

    This is the regression guard: a real reviewer (permission ``check_item:review``)
    with a REVIEW entitlement can decide; without the entitlement they'd 403.
    """
    user = personas["users"]["reviewer"]
    resp = client.post(
        "/api/v1/decisions",
        headers=_headers(user),
        json={
            "check_item_id": "persona-simple",
            "decision_type": "review_recommendation",
            "action": "approve",
            "notes": "Looks good",
        },
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["new_status"] == "approved"


def test_auditor_cannot_record_decision(personas, client):
    """Read-only auditors must not be able to record decisions."""
    user = personas["users"]["auditor"]
    resp = client.post(
        "/api/v1/decisions",
        headers=_headers(user),
        json={
            "check_item_id": "persona-simple",
            "decision_type": "review_recommendation",
            "action": "approve",
        },
    )
    assert resp.status_code == 403, resp.text


def test_dual_control_is_two_person(personas, client):
    """A different approver clears dual control; the author cannot self-approve."""
    users = personas["users"]

    # The original reviewer cannot approve (no approve permission at all).
    resp = client.post(
        "/api/v1/decisions/dual-control",
        headers=_headers(users["reviewer"]),
        json={"decision_id": "persona-dc-rec", "approve": True},
    )
    assert resp.status_code == 403

    # A senior reviewer (approve permission + APPROVE entitlement) clears it.
    resp = client.post(
        "/api/v1/decisions/dual-control",
        headers=_headers(users["senior_reviewer"]),
        json={"decision_id": "persona-dc-rec", "approve": True},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["new_status"] == "approved"
