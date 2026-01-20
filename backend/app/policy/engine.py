"""Policy engine for evaluating business rules."""

import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.check import CheckItem
from app.models.policy import Policy, PolicyRule, PolicyStatus, PolicyVersion, RuleConditionOperator
from app.schemas.policy import PolicyEvaluationResult, RuleAction, RuleCondition


class PolicyEngine:
    """
    Engine for evaluating policy rules against check items.

    The policy engine supports configurable rules with conditions and actions.
    Rules are versioned and auditable, with effective dates for compliance.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_active_policy(self, account_type: str | None = None) -> PolicyVersion | None:
        """Get the currently active policy version."""
        query = (
            select(PolicyVersion)
            .join(Policy)
            .options(selectinload(PolicyVersion.rules))
            .where(
                Policy.status == PolicyStatus.ACTIVE,
                PolicyVersion.is_current == True,
                PolicyVersion.effective_date <= datetime.now(timezone.utc),
            )
        )

        # Filter by account type if specified
        if account_type:
            query = query.where(
                Policy.applies_to_account_types.is_(None)
                | Policy.applies_to_account_types.contains(account_type)
            )

        # Prefer default policy, then by most recent effective date
        query = query.order_by(Policy.is_default.desc(), PolicyVersion.effective_date.desc())

        result = await self.db.execute(query)
        # Use scalars().first() to safely get first matching policy
        # (handles multiple matches gracefully)
        return result.scalars().first()

    async def evaluate(self, check_item: CheckItem) -> PolicyEvaluationResult:
        """
        Evaluate all applicable policy rules against a check item.

        Returns:
            PolicyEvaluationResult with triggered rules and required actions
        """
        policy_version = await self.get_active_policy(check_item.account_type.value)

        if not policy_version:
            # Return default result if no policy is active
            return PolicyEvaluationResult(
                policy_id="",
                policy_version_id="",
                rules_triggered=[],
                requires_dual_control=check_item.amount >= 5000,
                risk_level=check_item.risk_level.value,
            )

        rules_triggered = []
        requires_dual_control = False
        risk_level = check_item.risk_level.value
        routing_queue_id = None
        required_reason_categories = []
        flags = []

        # Evaluate each enabled rule
        for rule in policy_version.rules:
            if not rule.is_enabled:
                continue

            if self._evaluate_rule_conditions(rule, check_item):
                rules_triggered.append(rule.id)

                # Process rule actions
                actions = self._parse_actions(rule.actions)
                for action in actions:
                    if action.action == "require_dual_control":
                        requires_dual_control = True
                    elif action.action == "set_risk_level":
                        if action.params and "level" in action.params:
                            risk_level = action.params["level"]
                    elif action.action == "route_to_queue":
                        if action.params and "queue_id" in action.params:
                            routing_queue_id = action.params["queue_id"]
                    elif action.action == "require_reason":
                        if action.params and "category" in action.params:
                            required_reason_categories.append(action.params["category"])
                    elif action.action == "add_flag":
                        if action.params and "flag" in action.params:
                            flags.append(action.params["flag"])

        return PolicyEvaluationResult(
            policy_id=policy_version.policy_id,
            policy_version_id=policy_version.id,
            rules_triggered=rules_triggered,
            requires_dual_control=requires_dual_control,
            risk_level=risk_level,
            routing_queue_id=routing_queue_id,
            required_reason_categories=required_reason_categories,
            flags=flags,
        )

    def _evaluate_rule_conditions(self, rule: PolicyRule, item: CheckItem) -> bool:
        """Evaluate all conditions for a rule. All conditions must be true (AND logic)."""
        try:
            conditions = self._parse_conditions(rule.conditions)
        except (json.JSONDecodeError, TypeError):
            return False

        for condition in conditions:
            if not self._evaluate_condition(condition, item):
                return False

        return True

    def _parse_conditions(self, conditions_json: str) -> list[RuleCondition]:
        """Parse conditions from JSON string."""
        data = json.loads(conditions_json)
        if isinstance(data, list):
            return [RuleCondition(**c) for c in data]
        return [RuleCondition(**data)]

    def _parse_actions(self, actions_json: str) -> list[RuleAction]:
        """Parse actions from JSON string."""
        data = json.loads(actions_json)
        if isinstance(data, list):
            return [RuleAction(**a) for a in data]
        return [RuleAction(**data)]

    def _evaluate_condition(self, condition: RuleCondition, item: CheckItem) -> bool:
        """Evaluate a single condition against a check item."""
        # Get the field value from the check item
        field_value = self._get_field_value(condition.field, item)
        target_value = self._convert_value(condition.value, condition.value_type)

        if field_value is None:
            return False

        operator = condition.operator

        if operator == RuleConditionOperator.EQUALS:
            return field_value == target_value

        elif operator == RuleConditionOperator.NOT_EQUALS:
            return field_value != target_value

        elif operator == RuleConditionOperator.GREATER_THAN:
            return field_value > target_value

        elif operator == RuleConditionOperator.LESS_THAN:
            return field_value < target_value

        elif operator == RuleConditionOperator.GREATER_OR_EQUAL:
            return field_value >= target_value

        elif operator == RuleConditionOperator.LESS_OR_EQUAL:
            return field_value <= target_value

        elif operator == RuleConditionOperator.IN:
            if isinstance(target_value, list):
                return field_value in target_value
            return False

        elif operator == RuleConditionOperator.NOT_IN:
            if isinstance(target_value, list):
                return field_value not in target_value
            return False

        elif operator == RuleConditionOperator.CONTAINS:
            if isinstance(field_value, str) and isinstance(target_value, str):
                return target_value.lower() in field_value.lower()
            return False

        elif operator == RuleConditionOperator.BETWEEN:
            if isinstance(target_value, list) and len(target_value) == 2:
                return target_value[0] <= field_value <= target_value[1]
            return False

        return False

    def _get_field_value(self, field: str, item: CheckItem) -> Any:
        """Get a field value from a check item by field name.

        Note: Numeric fields are converted to float for consistent comparisons.
        """
        # Helper to safely convert Decimal to float
        def to_float(val):
            return float(val) if val is not None else None

        # Convert Decimal/numeric fields to float for consistent comparisons
        field_mapping = {
            # Basic check info
            "amount": to_float(item.amount),
            "account_type": item.account_type.value if item.account_type else None,
            "item_type": item.item_type.value if item.item_type else None,
            "risk_level": item.risk_level.value if item.risk_level else None,
            "payee_name": item.payee_name,
            "memo": item.memo,

            # Account tenure and balance
            "account_tenure_days": item.account_tenure_days,
            "current_balance": to_float(item.current_balance),
            "average_balance_30d": to_float(item.average_balance_30d),

            # Check amount history
            "avg_check_amount_30d": to_float(item.avg_check_amount_30d),
            "avg_check_amount_90d": to_float(item.avg_check_amount_90d),
            "avg_check_amount_365d": to_float(item.avg_check_amount_365d),
            "check_std_dev_30d": to_float(item.check_std_dev_30d),
            "max_check_amount_90d": to_float(item.max_check_amount_90d),

            # Check frequency
            "check_frequency_30d": item.check_frequency_30d,
            "check_count_7d": item.check_count_7d,
            "check_count_14d": item.check_count_14d,
            "total_check_amount_7d": to_float(item.total_check_amount_7d),
            "total_check_amount_14d": to_float(item.total_check_amount_14d),

            # Returns and exceptions
            "returned_item_count_90d": item.returned_item_count_90d,
            "exception_count_90d": item.exception_count_90d,

            # Overdraft history
            "overdraft_count_30d": item.overdraft_count_30d,
            "overdraft_count_90d": item.overdraft_count_90d,
            "nsf_count_90d": item.nsf_count_90d,

            # Customer/relationship context
            "relationship_tenure_years": to_float(item.relationship_tenure_years),
            "is_payroll_account": item.is_payroll_account,
            "has_direct_deposit": item.has_direct_deposit,
            "deposit_regularity_score": item.deposit_regularity_score,

            # Check number sequence
            "check_number_gap": item.check_number_gap,
            "is_duplicate_check_number": item.is_duplicate_check_number,
            "is_out_of_sequence": item.is_out_of_sequence,

            # Check age/staleness
            "check_age_days": item.check_age_days,
            "is_stale_dated": item.is_stale_dated,
            "is_post_dated": item.is_post_dated,

            # Image quality signals
            "has_micr_anomaly": item.has_micr_anomaly,
            "micr_confidence_score": item.micr_confidence_score,
            "has_alteration_flag": item.has_alteration_flag,
            "signature_match_score": item.signature_match_score,

            # Prior review history
            "prior_review_count": item.prior_review_count,
            "prior_approval_count": item.prior_approval_count,
            "prior_rejection_count": item.prior_rejection_count,
        }

        # Support computed fields
        if field == "amount_vs_avg_ratio":
            if item.avg_check_amount_30d and item.avg_check_amount_30d > 0:
                return float(item.amount) / float(item.avg_check_amount_30d)
            return None

        if field == "amount_vs_max_ratio":
            if item.max_check_amount_90d and item.max_check_amount_90d > 0:
                return float(item.amount) / float(item.max_check_amount_90d)
            return None

        if field == "amount_vs_balance_ratio":
            if item.current_balance and item.current_balance > 0:
                return float(item.amount) / float(item.current_balance)
            return None

        if field == "velocity_7d_ratio":
            # Check amount relative to 7-day velocity
            if item.total_check_amount_7d and item.total_check_amount_7d > 0:
                return float(item.amount) / float(item.total_check_amount_7d)
            return None

        return field_mapping.get(field)

    def _convert_value(self, value: Any, value_type: str) -> Any:
        """Convert a value to the appropriate type.

        Note: We use float for numeric comparisons to ensure consistency
        with computed fields (like ratios) which return float values.
        Using Decimal would cause TypeError when comparing float >= Decimal.
        """
        if value is None:
            return None

        if value_type == "number":
            if isinstance(value, list):
                return [float(v) for v in value]
            return float(value)

        if value_type == "boolean":
            return bool(value)

        if value_type == "array":
            if isinstance(value, list):
                return value
            return [value]

        return value


async def create_default_policy(db: AsyncSession) -> Policy:
    """Create a default policy with standard rules."""
    policy = Policy(
        name="Default Check Review Policy",
        description="Standard policy for check review with configurable thresholds",
        status=PolicyStatus.ACTIVE,
        is_default=True,
    )
    db.add(policy)
    await db.flush()

    version = PolicyVersion(
        policy_id=policy.id,
        version_number=1,
        effective_date=datetime.now(timezone.utc),
        is_current=True,
        change_notes="Initial policy creation",
    )
    db.add(version)
    await db.flush()

    # Dual control rule for high amounts
    dual_control_rule = PolicyRule(
        policy_version_id=version.id,
        name="Dual Control for High Value Checks",
        description="Require dual control approval for checks over $10,000",
        rule_type="dual_control",
        priority=100,
        conditions=json.dumps(
            [
                {
                    "field": "amount",
                    "operator": "greater_or_equal",
                    "value": 10000,
                    "value_type": "number",
                }
            ]
        ),
        actions=json.dumps([{"action": "require_dual_control", "params": None}]),
        amount_threshold=10000.0,
    )
    db.add(dual_control_rule)

    # Escalation rule for unusual amounts
    escalation_rule = PolicyRule(
        policy_version_id=version.id,
        name="Escalate Unusual Amount Checks",
        description="Escalate checks that are 5x the account average",
        rule_type="escalation",
        priority=90,
        conditions=json.dumps(
            [
                {
                    "field": "amount_vs_avg_ratio",
                    "operator": "greater_or_equal",
                    "value": 5,
                    "value_type": "number",
                }
            ]
        ),
        actions=json.dumps(
            [
                {"action": "set_risk_level", "params": {"level": "high"}},
                {"action": "add_flag", "params": {"flag": "UNUSUAL_AMOUNT"}},
            ]
        ),
    )
    db.add(escalation_rule)

    # New account rule
    new_account_rule = PolicyRule(
        policy_version_id=version.id,
        name="New Account Review",
        description="Flag checks from accounts less than 30 days old",
        rule_type="threshold",
        priority=80,
        conditions=json.dumps(
            [
                {
                    "field": "account_tenure_days",
                    "operator": "less_than",
                    "value": 30,
                    "value_type": "number",
                },
                {
                    "field": "amount",
                    "operator": "greater_or_equal",
                    "value": 2500,
                    "value_type": "number",
                },
            ]
        ),
        actions=json.dumps(
            [
                {"action": "add_flag", "params": {"flag": "NEW_ACCOUNT"}},
                {"action": "require_reason", "params": {"category": "new_account"}},
            ]
        ),
    )
    db.add(new_account_rule)

    # Prior returns rule
    returns_rule = PolicyRule(
        policy_version_id=version.id,
        name="Prior Returns Flag",
        description="Flag checks from accounts with prior returns",
        rule_type="threshold",
        priority=70,
        conditions=json.dumps(
            [
                {
                    "field": "returned_item_count_90d",
                    "operator": "greater_than",
                    "value": 0,
                    "value_type": "number",
                }
            ]
        ),
        actions=json.dumps([{"action": "add_flag", "params": {"flag": "PRIOR_RETURNS"}}]),
    )
    db.add(returns_rule)

    await db.commit()
    return policy
