"""Check item service."""

import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.integrations.adapters.factory import get_adapter
from app.models.check import AccountType, CheckImage, CheckItem, CheckStatus, RiskLevel
from app.schemas.check import (
    AccountContextResponse,
    AIFlagResponse,
    CheckHistoryResponse,
    CheckImageResponse,
    CheckItemCreate,
    CheckItemListResponse,
    CheckItemResponse,
    CheckSearchRequest,
)


class CheckService:
    """Service for check item operations."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.adapter = get_adapter()

    async def sync_presented_items(
        self,
        tenant_id: str,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        amount_min: Decimal | None = None,
    ) -> int:
        """
        Sync presented items from external system.

        This fetches new items from the integration adapter and creates
        check items in the local database for review.

        Args:
            tenant_id: Required tenant ID for multi-tenant isolation
            date_from: Start date for sync (default: last 24 hours)
            date_to: End date for sync (default: now)
            amount_min: Minimum amount threshold (default: dual control threshold)
        """
        if not tenant_id:
            raise ValueError("tenant_id is required for multi-tenant isolation")

        if date_from is None:
            date_from = datetime.now(timezone.utc) - timedelta(hours=24)
        if date_to is None:
            date_to = datetime.now(timezone.utc)
        if amount_min is None:
            amount_min = Decimal(settings.DUAL_CONTROL_THRESHOLD)

        items, total = await self.adapter.get_presented_items(
            date_from=date_from,
            date_to=date_to,
            amount_min=amount_min,
        )

        created_count = 0

        for item in items:
            # Check if item already exists within this tenant
            existing = await self.db.execute(
                select(CheckItem).where(
                    CheckItem.tenant_id == tenant_id,
                    CheckItem.external_item_id == item.external_item_id,
                )
            )
            if existing.scalar_one_or_none():
                continue

            # Get account context
            account_context = await self.adapter.get_account_context(item.account_id)
            behavior_stats = await self.adapter.get_check_behavior_stats(item.account_id)

            # Determine risk level based on amount and context
            risk_level = self._calculate_risk_level(item, account_context, behavior_stats)

            # Check if dual control is required
            requires_dual_control = item.amount >= Decimal(settings.DUAL_CONTROL_THRESHOLD)

            # Calculate SLA due time
            sla_hours = settings.DEFAULT_SLA_HOURS
            if risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]:
                sla_hours = 2
            sla_due_at = datetime.now(timezone.utc) + timedelta(hours=sla_hours)

            # Create check item with tenant isolation
            check_item = CheckItem(
                tenant_id=tenant_id,
                external_item_id=item.external_item_id,
                source_system=item.source_system,
                # Fiserv Director compatibility fields
                batch_id=item.batch_id,
                captured_at=item.captured_at,
                source_status=item.source_status,
                item_type_code=item.item_type_code,
                # Account and check details
                account_id=item.account_id,
                account_number_masked=item.account_number_masked,
                account_type=AccountType(item.account_type),
                routing_number=item.routing_number,
                check_number=item.check_number,
                amount=item.amount,
                currency=item.currency,
                payee_name=item.payee_name,
                memo=item.memo,
                micr_line=item.micr_line,
                micr_account=item.micr_account,
                micr_routing=item.micr_routing,
                micr_check_number=item.micr_check_number,
                presented_date=item.presented_date,
                check_date=item.check_date,
                status=CheckStatus.NEW,
                risk_level=risk_level,
                priority=self._calculate_priority(item.amount, risk_level),
                requires_dual_control=requires_dual_control,
                sla_due_at=sla_due_at,
                risk_flags=json.dumps(item.upstream_flags) if item.upstream_flags else None,
                upstream_flags=json.dumps(item.upstream_flags) if item.upstream_flags else None,
            )

            # Add account context
            if account_context:
                check_item.account_tenure_days = account_context.account_tenure_days
                check_item.current_balance = account_context.current_balance
                check_item.average_balance_30d = account_context.average_balance_30d
                check_item.relationship_id = account_context.relationship_id

            if behavior_stats:
                check_item.avg_check_amount_30d = behavior_stats.avg_check_amount_30d
                check_item.avg_check_amount_90d = behavior_stats.avg_check_amount_90d
                check_item.avg_check_amount_365d = behavior_stats.avg_check_amount_365d
                check_item.check_std_dev_30d = behavior_stats.check_std_dev_30d
                check_item.max_check_amount_90d = behavior_stats.max_check_amount_90d
                check_item.check_frequency_30d = behavior_stats.check_frequency_30d
                check_item.returned_item_count_90d = behavior_stats.returned_item_count_90d
                check_item.exception_count_90d = behavior_stats.exception_count_90d

            # Create image references
            if item.front_image_id:
                front_image = CheckImage(
                    check_item=check_item,
                    image_type="front",
                    external_image_id=item.front_image_id,
                )
                self.db.add(front_image)

            if item.back_image_id:
                back_image = CheckImage(
                    check_item=check_item,
                    image_type="back",
                    external_image_id=item.back_image_id,
                )
                self.db.add(back_image)

            self.db.add(check_item)
            created_count += 1

        await self.db.commit()
        return created_count

    def _calculate_risk_level(self, item, account_context, behavior_stats) -> RiskLevel:
        """Calculate risk level based on item and context."""
        risk_score = 0

        # Amount-based risk
        if item.amount >= 50000:
            risk_score += 40
        elif item.amount >= 25000:
            risk_score += 30
        elif item.amount >= 10000:
            risk_score += 20
        elif item.amount >= 5000:
            risk_score += 10

        # Behavior-based risk
        if behavior_stats:
            if behavior_stats.avg_check_amount_30d:
                ratio = float(item.amount) / float(behavior_stats.avg_check_amount_30d)
                if ratio > 5:
                    risk_score += 30
                elif ratio > 3:
                    risk_score += 20
                elif ratio > 2:
                    risk_score += 10

            if (
                behavior_stats.returned_item_count_90d
                and behavior_stats.returned_item_count_90d > 2
            ):
                risk_score += 20

            if behavior_stats.exception_count_90d and behavior_stats.exception_count_90d > 3:
                risk_score += 15

        # Account tenure risk
        if account_context and account_context.account_tenure_days:
            if account_context.account_tenure_days < 30:
                risk_score += 25
            elif account_context.account_tenure_days < 90:
                risk_score += 15

        # Upstream flags
        if item.upstream_flags:
            risk_score += len(item.upstream_flags) * 10

        # Determine risk level
        if risk_score >= 60:
            return RiskLevel.CRITICAL
        elif risk_score >= 40:
            return RiskLevel.HIGH
        elif risk_score >= 20:
            return RiskLevel.MEDIUM
        else:
            return RiskLevel.LOW

    def _calculate_priority(self, amount: Decimal, risk_level: RiskLevel) -> int:
        """Calculate priority score (higher = more urgent)."""
        priority = 0

        # Risk level contribution
        risk_priorities = {
            RiskLevel.CRITICAL: 100,
            RiskLevel.HIGH: 75,
            RiskLevel.MEDIUM: 50,
            RiskLevel.LOW: 25,
        }
        priority += risk_priorities.get(risk_level, 0)

        # Amount contribution
        if amount >= 100000:
            priority += 50
        elif amount >= 50000:
            priority += 40
        elif amount >= 25000:
            priority += 30
        elif amount >= 10000:
            priority += 20

        return priority

    async def get_check_item(
        self, item_id: str, user_id: str, tenant_id: str
    ) -> CheckItemResponse | None:
        """Get a check item by ID with full details.

        Args:
            item_id: The check item ID
            user_id: The requesting user's ID (for user-bound signed URLs)
            tenant_id: Required for multi-tenant isolation
        """
        result = await self.db.execute(
            select(CheckItem)
            .options(selectinload(CheckItem.images))
            .where(
                CheckItem.id == item_id,
                CheckItem.tenant_id == tenant_id,
            )
        )
        item = result.scalar_one_or_none()

        if not item:
            return None

        return await self._build_check_response(item, user_id)

    async def _build_check_response(self, item: CheckItem, user_id: str) -> CheckItemResponse:
        """Build a complete check item response with context and flags.

        Args:
            item: The check item
            user_id: The requesting user's ID (for user-bound signed URLs)
        """
        # Build image responses with user-bound signed URLs
        images = []
        for img in item.images:
            from app.core.security import generate_signed_url

            # generate_signed_url returns (url, jti) tuple - we only need the URL here
            # jti can be stored for revocation tracking if needed in the future
            image_url, _ = generate_signed_url(
                img.external_image_id or img.id, user_id, tenant_id=item.tenant_id
            )
            thumbnail_url, _ = generate_signed_url(
                f"thumb_{img.external_image_id or img.id}", user_id, tenant_id=item.tenant_id
            )

            images.append(
                CheckImageResponse(
                    id=img.id,
                    image_type=img.image_type,
                    content_type=img.content_type,
                    file_size=img.file_size,
                    width=img.width,
                    height=img.height,
                    image_url=image_url,
                    thumbnail_url=thumbnail_url,
                )
            )

        # Build account context
        account_context = None
        if item.avg_check_amount_30d:
            amount_vs_avg = None
            if item.avg_check_amount_30d and item.avg_check_amount_30d > 0:
                amount_vs_avg = float(item.amount) / float(item.avg_check_amount_30d)

            account_context = AccountContextResponse(
                account_tenure_days=item.account_tenure_days,
                current_balance=item.current_balance,
                average_balance_30d=item.average_balance_30d,
                avg_check_amount_30d=item.avg_check_amount_30d,
                avg_check_amount_90d=item.avg_check_amount_90d,
                avg_check_amount_365d=item.avg_check_amount_365d,
                check_std_dev_30d=item.check_std_dev_30d,
                max_check_amount_90d=item.max_check_amount_90d,
                check_frequency_30d=item.check_frequency_30d,
                returned_item_count_90d=item.returned_item_count_90d,
                exception_count_90d=item.exception_count_90d,
                amount_vs_avg_ratio=amount_vs_avg,
            )

        # Build AI flags
        ai_flags = self._generate_ai_flags(item)

        return CheckItemResponse(
            id=item.id,
            external_item_id=item.external_item_id,
            source_system=item.source_system,
            account_id=item.account_id,
            item_type=item.item_type,
            account_number_masked=item.account_number_masked,
            account_type=item.account_type,
            routing_number=item.routing_number,
            check_number=item.check_number,
            amount=item.amount,
            currency=item.currency,
            payee_name=item.payee_name,
            memo=item.memo,
            check_date=item.check_date,
            micr_line=item.micr_line,
            presented_date=item.presented_date,
            process_date=item.process_date,
            status=item.status,
            risk_level=item.risk_level,
            priority=item.priority,
            requires_dual_control=item.requires_dual_control,
            has_ai_flags=item.has_ai_flags or len(ai_flags) > 0,
            sla_due_at=item.sla_due_at,
            sla_breached=item.sla_breached,
            assigned_reviewer_id=item.assigned_reviewer_id,
            assigned_approver_id=item.assigned_approver_id,
            queue_id=item.queue_id,
            policy_version_id=item.policy_version_id,
            images=images,
            account_context=account_context,
            ai_flags=ai_flags,
            created_at=item.created_at,
            updated_at=item.updated_at,
            # Fiserv Director compatibility fields
            batch_id=item.batch_id,
            captured_at=item.captured_at,
            source_status=item.source_status,
            item_type_code=item.item_type_code,
        )

    def _generate_ai_flags(self, item: CheckItem) -> list[AIFlagResponse]:
        """Generate AI/rule-based flags for a check item."""
        flags = []

        # Amount-based flags
        if item.avg_check_amount_30d and item.avg_check_amount_30d > 0:
            ratio = float(item.amount) / float(item.avg_check_amount_30d)

            if ratio >= 5:
                flags.append(
                    AIFlagResponse(
                        code="AMOUNT_5X_AVG",
                        description=f"Amount is {ratio:.1f}x the 30-day average",
                        category="amount",
                        severity="alert",
                        confidence=1.0,
                        explanation=f"This check for ${item.amount:,.2f} is significantly higher than "
                        f"the account's 30-day average of ${item.avg_check_amount_30d:,.2f}",
                    )
                )
            elif ratio >= 3:
                flags.append(
                    AIFlagResponse(
                        code="AMOUNT_3X_AVG",
                        description=f"Amount is {ratio:.1f}x the 30-day average",
                        category="amount",
                        severity="warning",
                        confidence=1.0,
                        explanation=f"This check is moderately higher than typical for this account",
                    )
                )

        # Max amount flag
        if item.max_check_amount_90d and item.amount > item.max_check_amount_90d:
            flags.append(
                AIFlagResponse(
                    code="EXCEEDS_90D_MAX",
                    description="Amount exceeds 90-day maximum",
                    category="amount",
                    severity="warning",
                    confidence=1.0,
                    explanation=f"This is the largest check from this account in the past 90 days. "
                    f"Previous maximum was ${item.max_check_amount_90d:,.2f}",
                )
            )

        # Account tenure flag
        if item.account_tenure_days and item.account_tenure_days < 30:
            flags.append(
                AIFlagResponse(
                    code="NEW_ACCOUNT",
                    description="Account is less than 30 days old",
                    category="behavior",
                    severity="warning",
                    confidence=1.0,
                    explanation=f"This account was opened {item.account_tenure_days} days ago",
                )
            )

        # Return history flag
        if item.returned_item_count_90d and item.returned_item_count_90d > 0:
            severity = "alert" if item.returned_item_count_90d > 2 else "warning"
            flags.append(
                AIFlagResponse(
                    code="PRIOR_RETURNS",
                    description=f"{item.returned_item_count_90d} returned items in past 90 days",
                    category="behavior",
                    severity=severity,
                    confidence=1.0,
                    explanation=f"This account has had {item.returned_item_count_90d} items returned "
                    f"in the past 90 days",
                )
            )

        # Parse upstream flags
        if item.upstream_flags:
            try:
                upstream = json.loads(item.upstream_flags)
                for flag in upstream:
                    flags.append(
                        AIFlagResponse(
                            code=flag,
                            description=f"Upstream flag: {flag}",
                            category="system",
                            severity="info",
                            confidence=None,
                            explanation="Flag from source system",
                        )
                    )
            except json.JSONDecodeError:
                pass

        # Parse risk_flags (demo/AI-generated flags stored as JSON)
        if item.risk_flags:
            # Flag definitions - ONLY flags with REAL detection capabilities
            # All flags here can be calculated from account context data
            flag_definitions = {
                # === DATE-BASED FLAGS (calculated from check_date) ===
                "STALE_DATED": {
                    "description": "Check is stale-dated",
                    "category": "compliance",
                    "severity": "warning",
                    "explanation": "The check date is more than 180 days old",
                },
                "POST_DATED": {
                    "description": "Check is post-dated",
                    "category": "compliance",
                    "severity": "warning",
                    "explanation": "The check date is in the future",
                },
                # === DUPLICATE DETECTION (database lookup) ===
                "DUPLICATE_CHECK_NUMBER": {
                    "description": "Duplicate check number detected",
                    "category": "fraud",
                    "severity": "alert",
                    "explanation": "This check number has been used previously on this account",
                },
                # === AMOUNT-BASED FLAGS (calculated from avg_check_amount_30d) ===
                "AMOUNT_5X_AVG": {
                    "description": "Amount is 5x+ the 30-day average",
                    "category": "amount",
                    "severity": "alert",
                    "explanation": "This check amount significantly exceeds the account's typical pattern",
                },
                "AMOUNT_3X_AVG": {
                    "description": "Amount is 3x+ the 30-day average",
                    "category": "amount",
                    "severity": "warning",
                    "explanation": "This check is moderately higher than typical for this account",
                },
                "EXCEEDS_MAX_90D": {
                    "description": "Amount exceeds 90-day maximum",
                    "category": "amount",
                    "severity": "warning",
                    "explanation": "This is the largest check from this account in the past 90 days",
                },
                "EXCEEDS_CURRENT_BALANCE": {
                    "description": "Amount exceeds current balance",
                    "category": "amount",
                    "severity": "alert",
                    "explanation": "The check amount is greater than the current account balance",
                },
                # === ACCOUNT TENURE FLAGS (calculated from account_tenure_days) ===
                "NEW_ACCOUNT_30D": {
                    "description": "Account less than 30 days old",
                    "category": "behavior",
                    "severity": "warning",
                    "explanation": "This is a new account with limited transaction history",
                },
                "NEW_ACCOUNT_90D": {
                    "description": "Account less than 90 days old",
                    "category": "behavior",
                    "severity": "info",
                    "explanation": "Account has less than 90 days of history for pattern analysis",
                },
                # === VELOCITY FLAGS (calculated from check_count_7d/14d) ===
                "VELOCITY_7D_HIGH": {
                    "description": "High check volume in past 7 days",
                    "category": "behavior",
                    "severity": "warning",
                    "explanation": "Transaction frequency is elevated compared to normal patterns",
                },
                "TOTAL_AMOUNT_14D_HIGH": {
                    "description": "High total amount in past 14 days",
                    "category": "behavior",
                    "severity": "warning",
                    "explanation": "Total check amount this period exceeds normal patterns",
                },
                # === HISTORY-BASED FLAGS (calculated from returned_item_count, overdraft_count) ===
                "RETURNED_ITEMS_90D": {
                    "description": "Recent returned items on account",
                    "category": "behavior",
                    "severity": "warning",
                    "explanation": "This account has had items returned in the past 90 days",
                },
                "OVERDRAFT_HISTORY": {
                    "description": "Recent overdraft history",
                    "category": "behavior",
                    "severity": "warning",
                    "explanation": "This account has experienced overdrafts recently",
                },
            }

            try:
                risk_flag_codes = json.loads(item.risk_flags)
                for flag_code in risk_flag_codes:
                    # Skip if we already have this flag from calculated rules
                    if any(f.code == flag_code for f in flags):
                        continue

                    flag_def = flag_definitions.get(flag_code, {})
                    flags.append(
                        AIFlagResponse(
                            code=flag_code,
                            description=flag_def.get("description", f"Risk flag: {flag_code}"),
                            category=flag_def.get("category", "risk"),
                            severity=flag_def.get("severity", "warning"),
                            confidence=item.ai_confidence if item.ai_confidence else None,
                            explanation=flag_def.get(
                                "explanation", f"AI-detected risk indicator: {flag_code}"
                            ),
                        )
                    )
            except json.JSONDecodeError:
                pass

        return flags

    async def search_items(
        self,
        search: CheckSearchRequest,
        user_id: str,
        tenant_id: str,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[CheckItemListResponse], int]:
        """Search check items with filters.

        Args:
            search: Search criteria
            user_id: The requesting user's ID (for user-bound signed URLs)
            tenant_id: Required for multi-tenant isolation
            page: Page number
            page_size: Items per page
        """
        query = select(CheckItem).options(selectinload(CheckItem.images))

        # Apply filters - always filter by tenant_id first (CRITICAL for security)
        conditions = [CheckItem.tenant_id == tenant_id]

        if search.account_number:
            conditions.append(CheckItem.account_number_masked.contains(search.account_number[-4:]))

        if search.item_id:
            conditions.append(
                or_(
                    CheckItem.id == search.item_id,
                    CheckItem.external_item_id == search.item_id,
                )
            )

        if search.amount_min is not None:
            conditions.append(CheckItem.amount >= search.amount_min)

        if search.amount_max is not None:
            conditions.append(CheckItem.amount <= search.amount_max)

        if search.date_from:
            conditions.append(CheckItem.presented_date >= search.date_from)

        if search.date_to:
            conditions.append(CheckItem.presented_date <= search.date_to)

        if search.status:
            conditions.append(CheckItem.status.in_(search.status))

        if search.risk_level:
            conditions.append(CheckItem.risk_level.in_(search.risk_level))

        if search.queue_id:
            conditions.append(CheckItem.queue_id == search.queue_id)

        if search.assigned_to:
            conditions.append(
                or_(
                    CheckItem.assigned_reviewer_id == search.assigned_to,
                    CheckItem.assigned_approver_id == search.assigned_to,
                )
            )

        if search.has_ai_flags is not None:
            conditions.append(CheckItem.has_ai_flags == search.has_ai_flags)

        if search.sla_breached is not None:
            conditions.append(CheckItem.sla_breached == search.sla_breached)

        # Always apply conditions (tenant_id is always included)
        query = query.where(and_(*conditions))

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar()

        # Apply pagination and ordering
        query = query.order_by(
            CheckItem.priority.desc(),
            CheckItem.presented_date.desc(),
        )
        query = query.offset((page - 1) * page_size).limit(page_size)

        result = await self.db.execute(query)
        items = result.scalars().all()

        # Build response
        responses = []
        for item in items:
            # Get thumbnail URL for first front image (user-bound)
            thumbnail_url = None
            for img in item.images:
                if img.image_type == "front":
                    from app.core.security import generate_signed_url

                    # generate_signed_url returns (url, jti) tuple
                    thumbnail_url, _ = generate_signed_url(
                        f"thumb_{img.external_image_id or img.id}",
                        user_id,
                        tenant_id=item.tenant_id,
                    )
                    break

            responses.append(
                CheckItemListResponse(
                    id=item.id,
                    external_item_id=item.external_item_id,
                    account_number_masked=item.account_number_masked,
                    account_type=item.account_type,
                    item_type=item.item_type,
                    amount=item.amount,
                    check_number=item.check_number,
                    payee_name=item.payee_name,
                    presented_date=item.presented_date,
                    status=item.status,
                    risk_level=item.risk_level,
                    priority=item.priority,
                    requires_dual_control=item.requires_dual_control,
                    has_ai_flags=item.has_ai_flags or False,
                    sla_due_at=item.sla_due_at,
                    sla_breached=item.sla_breached,
                    assigned_reviewer_id=item.assigned_reviewer_id,
                    thumbnail_url=thumbnail_url,
                )
            )

        return responses, total

    async def get_check_history(
        self,
        account_id: str,
        user_id: str,
        limit: int = 10,
    ) -> list[CheckHistoryResponse]:
        """Get check history for an account.

        Args:
            account_id: The account ID
            user_id: The requesting user's ID (for user-bound signed URLs)
            limit: Maximum number of history items
        """
        from sqlalchemy import select

        from app.core.security import generate_signed_url
        from app.models.check import CheckHistory

        # Query database directly for historical checks
        result = await self.db.execute(
            select(CheckHistory)
            .where(CheckHistory.account_id == account_id)
            .order_by(CheckHistory.check_date.desc())
            .limit(limit)
        )
        history_records = result.scalars().all()

        # Build history responses - generate_signed_url returns (url, jti) tuple
        history_responses = []
        for h in history_records:
            front_url = None
            back_url = None
            if h.front_image_ref:
                front_url, _ = generate_signed_url(h.front_image_ref, user_id)
            if h.back_image_ref:
                back_url, _ = generate_signed_url(h.back_image_ref, user_id)

            history_responses.append(
                CheckHistoryResponse(
                    id=h.external_item_id or h.id,
                    account_id=h.account_id,
                    check_number=h.check_number,
                    amount=h.amount,
                    check_date=h.check_date,
                    payee_name=h.payee_name,
                    status=h.status,
                    return_reason=h.return_reason,
                    front_image_url=front_url,
                    back_image_url=back_url,
                )
            )
        return history_responses

    async def get_adjacent_items(
        self,
        item_id: str,
        user_id: str,
        tenant_id: str,
        status: list[CheckStatus] | None = None,
        risk_level: list[RiskLevel] | None = None,
    ) -> dict:
        """Get IDs of adjacent items in queue for navigation.

        Returns previous and next item IDs based on priority/date ordering,
        allowing reviewers to navigate directly between items.

        Args:
            item_id: Current item ID
            user_id: The requesting user's ID
            tenant_id: Required for multi-tenant isolation
            status: Filter by statuses (default: reviewable statuses)
            risk_level: Filter by risk levels (optional)
        """
        # Get the current item first
        result = await self.db.execute(
            select(CheckItem).where(
                CheckItem.id == item_id,
                CheckItem.tenant_id == tenant_id,
            )
        )
        current_item = result.scalar_one_or_none()

        if not current_item:
            return {"previous_id": None, "next_id": None, "position": 0, "total": 0}

        # Build base conditions
        conditions = [CheckItem.tenant_id == tenant_id]

        if status:
            conditions.append(CheckItem.status.in_(status))

        if risk_level:
            conditions.append(CheckItem.risk_level.in_(risk_level))

        # Get total count
        count_query = select(func.count()).where(and_(*conditions))
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        # Find items with higher priority (previous in the queue)
        # Items are ordered by priority DESC, presented_date DESC
        # "Previous" = higher priority or same priority with later date
        prev_conditions = conditions + [
            or_(
                CheckItem.priority > current_item.priority,
                and_(
                    CheckItem.priority == current_item.priority,
                    CheckItem.presented_date > current_item.presented_date,
                ),
                and_(
                    CheckItem.priority == current_item.priority,
                    CheckItem.presented_date == current_item.presented_date,
                    CheckItem.id < current_item.id,  # Tie-breaker
                ),
            )
        ]
        prev_query = (
            select(CheckItem.id)
            .where(and_(*prev_conditions))
            .order_by(CheckItem.priority.asc(), CheckItem.presented_date.asc())
            .limit(1)
        )
        prev_result = await self.db.execute(prev_query)
        prev_id = prev_result.scalar_one_or_none()

        # Find items with lower priority (next in the queue)
        # "Next" = lower priority or same priority with earlier date
        next_conditions = conditions + [
            or_(
                CheckItem.priority < current_item.priority,
                and_(
                    CheckItem.priority == current_item.priority,
                    CheckItem.presented_date < current_item.presented_date,
                ),
                and_(
                    CheckItem.priority == current_item.priority,
                    CheckItem.presented_date == current_item.presented_date,
                    CheckItem.id > current_item.id,  # Tie-breaker
                ),
            )
        ]
        next_query = (
            select(CheckItem.id)
            .where(and_(*next_conditions))
            .order_by(CheckItem.priority.desc(), CheckItem.presented_date.desc())
            .limit(1)
        )
        next_result = await self.db.execute(next_query)
        next_id = next_result.scalar_one_or_none()

        # Calculate position (1-indexed)
        position_conditions = conditions + [
            or_(
                CheckItem.priority > current_item.priority,
                and_(
                    CheckItem.priority == current_item.priority,
                    CheckItem.presented_date > current_item.presented_date,
                ),
                and_(
                    CheckItem.priority == current_item.priority,
                    CheckItem.presented_date == current_item.presented_date,
                    CheckItem.id <= current_item.id,
                ),
            )
        ]
        position_query = select(func.count()).where(and_(*position_conditions))
        position_result = await self.db.execute(position_query)
        position = position_result.scalar() or 1

        return {
            "previous_id": prev_id,
            "next_id": next_id,
            "position": position,
            "total": total,
        }

    async def update_status(
        self,
        item_id: str,
        status: CheckStatus,
        user_id: str,
        tenant_id: str,
    ) -> CheckItem | None:
        """Update check item status.

        Args:
            item_id: The check item ID
            status: The new status
            user_id: The user making the change
            tenant_id: Required for multi-tenant isolation
        """
        result = await self.db.execute(
            select(CheckItem).where(
                CheckItem.id == item_id,
                CheckItem.tenant_id == tenant_id,
            )
        )
        item = result.scalar_one_or_none()

        if not item:
            return None

        item.status = status
        item.updated_at = datetime.now(timezone.utc)

        await self.db.commit()
        return item
