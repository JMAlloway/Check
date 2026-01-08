"""Entitlement service for checking approval permissions."""

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.check import CheckItem
from app.models.queue import ApprovalEntitlement, ApprovalEntitlementType
from app.models.user import User


class EntitlementCheckResult:
    """Result of an entitlement check."""

    def __init__(
        self,
        allowed: bool,
        entitlement_id: str | None = None,
        denial_reason: str | None = None,
        entitlement_details: dict | None = None,
    ):
        self.allowed = allowed
        self.entitlement_id = entitlement_id
        self.denial_reason = denial_reason
        self.entitlement_details = entitlement_details or {}

    def to_dict(self) -> dict:
        return {
            "allowed": self.allowed,
            "entitlement_id": self.entitlement_id,
            "denial_reason": self.denial_reason,
            "entitlement_details": self.entitlement_details,
        }


class EntitlementService:
    """
    Service for checking user entitlements against check items.

    Entitlements define what a user can approve based on:
    - Amount thresholds
    - Account types
    - Queue assignments
    - Risk levels
    - Business lines
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_user_entitlements(
        self,
        user: User,
        entitlement_type: ApprovalEntitlementType,
    ) -> list[ApprovalEntitlement]:
        """Get all active entitlements for a user (direct + role-based)."""
        now = datetime.now(timezone.utc)

        # Get role IDs for user
        role_ids = [role.id for role in user.roles] if user.roles else []

        # Build query for user's entitlements (direct or via role)
        conditions = [
            ApprovalEntitlement.entitlement_type == entitlement_type,
            ApprovalEntitlement.is_active == True,
            ApprovalEntitlement.effective_from <= now,
            or_(
                ApprovalEntitlement.effective_until.is_(None),
                ApprovalEntitlement.effective_until > now,
            ),
        ]

        # Add user/role filter
        if role_ids:
            conditions.append(
                or_(
                    ApprovalEntitlement.user_id == user.id,
                    ApprovalEntitlement.role_id.in_(role_ids),
                )
            )
        else:
            conditions.append(ApprovalEntitlement.user_id == user.id)

        query = select(ApprovalEntitlement).where(*conditions)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def check_review_entitlement(
        self,
        user: User,
        check_item: CheckItem,
    ) -> EntitlementCheckResult:
        """Check if user can make a review recommendation for this item."""
        entitlements = await self.get_user_entitlements(user, ApprovalEntitlementType.REVIEW)

        if not entitlements:
            # No explicit entitlements - check basic permissions
            # By default, users with "review" permission can review
            if any(p.name == "review" for r in (user.roles or []) for p in (r.permissions or [])):
                return EntitlementCheckResult(allowed=True)
            return EntitlementCheckResult(
                allowed=False,
                denial_reason="No review entitlement found",
            )

        # Check if any entitlement allows this item
        return self._check_entitlements_against_item(entitlements, check_item, "review")

    async def check_approval_entitlement(
        self,
        user: User,
        check_item: CheckItem,
    ) -> EntitlementCheckResult:
        """
        Check if user can approve (dual control) this item.

        This is the key check for dual control workflow - it ensures the
        approver has the appropriate entitlement for the item's characteristics.
        """
        entitlements = await self.get_user_entitlements(user, ApprovalEntitlementType.APPROVE)

        if not entitlements:
            return EntitlementCheckResult(
                allowed=False,
                denial_reason="No approval entitlement found",
            )

        return self._check_entitlements_against_item(entitlements, check_item, "approve")

    async def check_override_entitlement(
        self,
        user: User,
        check_item: CheckItem,
    ) -> EntitlementCheckResult:
        """Check if user can override policy for this item."""
        entitlements = await self.get_user_entitlements(user, ApprovalEntitlementType.OVERRIDE)

        if not entitlements:
            return EntitlementCheckResult(
                allowed=False,
                denial_reason="No override entitlement found",
            )

        return self._check_entitlements_against_item(entitlements, check_item, "override")

    def _check_entitlements_against_item(
        self,
        entitlements: list[ApprovalEntitlement],
        check_item: CheckItem,
        action_type: str,
    ) -> EntitlementCheckResult:
        """Check if any entitlement allows the action on this item."""
        denial_reasons = []

        for entitlement in entitlements:
            result = self._check_single_entitlement(entitlement, check_item)
            if result.allowed:
                return EntitlementCheckResult(
                    allowed=True,
                    entitlement_id=entitlement.id,
                    entitlement_details={
                        "max_amount": float(entitlement.max_amount) if entitlement.max_amount else None,
                        "allowed_account_types": entitlement.allowed_account_types,
                        "allowed_risk_levels": entitlement.allowed_risk_levels,
                    },
                )
            if result.denial_reason:
                denial_reasons.append(result.denial_reason)

        # No entitlement allowed this item
        unique_reasons = set(denial_reasons) if denial_reasons else {"no matching entitlement"}
        return EntitlementCheckResult(
            allowed=False,
            denial_reason=f"No {action_type} entitlement covers this item: {'; '.join(unique_reasons)}",
        )

    def _check_single_entitlement(
        self,
        entitlement: ApprovalEntitlement,
        check_item: CheckItem,
    ) -> EntitlementCheckResult:
        """Check a single entitlement against a check item."""
        amount = Decimal(str(check_item.amount))

        # Check amount limits
        if entitlement.min_amount is not None and amount < entitlement.min_amount:
            return EntitlementCheckResult(
                allowed=False,
                denial_reason=f"Amount {amount} below minimum {entitlement.min_amount}",
            )

        if entitlement.max_amount is not None and amount > entitlement.max_amount:
            return EntitlementCheckResult(
                allowed=False,
                denial_reason=f"Amount {amount} exceeds maximum {entitlement.max_amount}",
            )

        # Check account type
        if entitlement.allowed_account_types:
            account_type = check_item.account_type.value if check_item.account_type else None
            if account_type not in entitlement.allowed_account_types:
                return EntitlementCheckResult(
                    allowed=False,
                    denial_reason=f"Account type '{account_type}' not in allowed types",
                )

        # Check queue restriction
        if entitlement.allowed_queue_ids:
            if check_item.queue_id not in entitlement.allowed_queue_ids:
                return EntitlementCheckResult(
                    allowed=False,
                    denial_reason=f"Queue '{check_item.queue_id}' not in allowed queues",
                )

        # Check risk level
        if entitlement.allowed_risk_levels:
            risk_level = check_item.risk_level.value if check_item.risk_level else None
            if risk_level not in entitlement.allowed_risk_levels:
                return EntitlementCheckResult(
                    allowed=False,
                    denial_reason=f"Risk level '{risk_level}' not in allowed levels",
                )

        # Check tenant (multi-tenant isolation)
        if entitlement.tenant_id:
            # Would need to get tenant from user or item
            # For now, skip this check if not implemented
            pass

        # All checks passed
        return EntitlementCheckResult(allowed=True, entitlement_id=entitlement.id)

    async def get_max_approval_amount(self, user: User) -> Decimal | None:
        """Get the maximum amount a user can approve (across all entitlements)."""
        entitlements = await self.get_user_entitlements(user, ApprovalEntitlementType.APPROVE)

        if not entitlements:
            return None

        max_amounts = [e.max_amount for e in entitlements if e.max_amount is not None]
        if not max_amounts:
            return None  # No limit

        return max(max_amounts)

    async def get_entitlement_summary(self, user: User) -> dict:
        """Get a summary of user's entitlements for UI display."""
        review_entitlements = await self.get_user_entitlements(user, ApprovalEntitlementType.REVIEW)
        approve_entitlements = await self.get_user_entitlements(user, ApprovalEntitlementType.APPROVE)
        override_entitlements = await self.get_user_entitlements(user, ApprovalEntitlementType.OVERRIDE)

        def summarize(entitlements: list[ApprovalEntitlement]) -> dict:
            if not entitlements:
                return {"has_entitlement": False}

            max_amounts = [e.max_amount for e in entitlements if e.max_amount is not None]
            all_account_types = set()
            all_risk_levels = set()

            for e in entitlements:
                if e.allowed_account_types:
                    all_account_types.update(e.allowed_account_types)
                if e.allowed_risk_levels:
                    all_risk_levels.update(e.allowed_risk_levels)

            return {
                "has_entitlement": True,
                "max_amount": float(max(max_amounts)) if max_amounts else None,
                "account_types": list(all_account_types) if all_account_types else None,
                "risk_levels": list(all_risk_levels) if all_risk_levels else None,
            }

        return {
            "review": summarize(review_entitlements),
            "approve": summarize(approve_entitlements),
            "override": summarize(override_entitlements),
        }
