"""
Fraud Intelligence Sharing Service.

This module provides the core business logic for:
- Creating and managing fraud events
- Generating shared artifacts for network sharing
- Matching checks against network fraud indicators
- Computing network trends and statistics
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import uuid4

from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.models.check import CheckItem
from app.models.fraud import (
    FraudEvent,
    FraudSharedArtifact,
    NetworkMatchAlert,
    TenantFraudConfig,
    FraudType,
    FraudChannel,
    AmountBucket,
    SharingLevel,
    FraudEventStatus,
    MatchSeverity,
    get_amount_bucket,
)
from app.schemas.fraud import (
    FraudEventCreate,
    FraudEventUpdate,
    FraudEventResponse,
    NetworkAlertResponse,
    NetworkAlertSummary,
    MatchReasonDetail,
    PIIDetectionResult,
)
from app.services.fraud_hashing import get_hashing_service
from app.services.pii_detection import get_pii_detection_service


class FraudService:
    """Service for fraud intelligence operations."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.hashing = get_hashing_service()
        self.pii_detector = get_pii_detection_service()

    # ========================================================================
    # Tenant Configuration
    # ========================================================================

    async def get_tenant_config(self, tenant_id: str) -> TenantFraudConfig:
        """Get or create tenant fraud configuration."""
        result = await self.db.execute(
            select(TenantFraudConfig).where(TenantFraudConfig.tenant_id == tenant_id)
        )
        config = result.scalar_one_or_none()

        if not config:
            # Create default config
            config = TenantFraudConfig(
                id=str(uuid4()),
                tenant_id=tenant_id,
                default_sharing_level=SharingLevel.PRIVATE,
                allow_narrative_sharing=False,
                allow_account_indicator_sharing=False,
                shared_artifact_retention_months=24,
                receive_network_alerts=True,
                minimum_alert_severity=MatchSeverity.LOW,
            )
            self.db.add(config)
            await self.db.flush()

        return config

    async def update_tenant_config(
        self,
        tenant_id: str,
        updates: dict[str, Any],
        modified_by_user_id: str,
    ) -> TenantFraudConfig:
        """Update tenant fraud configuration."""
        config = await self.get_tenant_config(tenant_id)

        for key, value in updates.items():
            if hasattr(config, key) and value is not None:
                setattr(config, key, value)

        config.last_modified_by_user_id = modified_by_user_id
        await self.db.flush()
        return config

    # ========================================================================
    # Fraud Event CRUD
    # ========================================================================

    async def create_fraud_event(
        self,
        tenant_id: str,
        user_id: str,
        data: FraudEventCreate,
    ) -> FraudEvent:
        """Create a new fraud event (draft status)."""
        # Get tenant config for defaults
        config = await self.get_tenant_config(tenant_id)

        # Compute amount bucket
        amount_bucket = get_amount_bucket(data.amount)

        # Use default sharing level if not specified
        sharing_level = data.sharing_level
        if sharing_level == SharingLevel.PRIVATE:
            sharing_level = config.default_sharing_level

        event = FraudEvent(
            id=str(uuid4()),
            tenant_id=tenant_id,
            check_item_id=data.check_item_id,
            case_id=data.case_id,
            event_date=data.event_date,
            amount=data.amount,
            amount_bucket=amount_bucket,
            fraud_type=data.fraud_type,
            channel=data.channel,
            confidence=data.confidence,
            narrative_private=data.narrative_private,
            narrative_shareable=data.narrative_shareable if config.allow_narrative_sharing else None,
            sharing_level=sharing_level,
            status=FraudEventStatus.DRAFT,
            created_by_user_id=user_id,
        )

        self.db.add(event)
        await self.db.flush()
        return event

    async def get_fraud_event(
        self,
        event_id: str,
        tenant_id: str,
    ) -> FraudEvent | None:
        """Get a fraud event by ID (tenant-scoped)."""
        result = await self.db.execute(
            select(FraudEvent)
            .options(selectinload(FraudEvent.shared_artifact))
            .where(
                FraudEvent.id == event_id,
                FraudEvent.tenant_id == tenant_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_fraud_events(
        self,
        tenant_id: str,
        status: FraudEventStatus | None = None,
        fraud_type: FraudType | None = None,
        check_item_id: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[FraudEvent], int]:
        """List fraud events for a tenant."""
        query = select(FraudEvent).where(FraudEvent.tenant_id == tenant_id)

        if status:
            query = query.where(FraudEvent.status == status)
        if fraud_type:
            query = query.where(FraudEvent.fraud_type == fraud_type)
        if check_item_id:
            query = query.where(FraudEvent.check_item_id == check_item_id)

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_query)).scalar() or 0

        # Get paginated results
        query = query.order_by(FraudEvent.created_at.desc())
        query = query.offset((page - 1) * page_size).limit(page_size)

        result = await self.db.execute(query)
        events = list(result.scalars().all())

        return events, total

    async def update_fraud_event(
        self,
        event_id: str,
        tenant_id: str,
        data: FraudEventUpdate,
    ) -> FraudEvent | None:
        """Update a fraud event (draft only)."""
        event = await self.get_fraud_event(event_id, tenant_id)
        if not event:
            return None

        if event.status != FraudEventStatus.DRAFT:
            raise ValueError("Can only update draft events")

        for key, value in data.model_dump(exclude_unset=True).items():
            if value is not None:
                setattr(event, key, value)

        # Recompute amount bucket if amount changed
        if data.amount is not None:
            event.amount_bucket = get_amount_bucket(data.amount)

        await self.db.flush()
        return event

    async def submit_fraud_event(
        self,
        event_id: str,
        tenant_id: str,
        user_id: str,
        sharing_level: SharingLevel | None = None,
        confirm_no_pii: bool = False,
    ) -> FraudEvent:
        """Submit a fraud event for sharing."""
        event = await self.get_fraud_event(event_id, tenant_id)
        if not event:
            raise ValueError("Event not found")

        if event.status != FraudEventStatus.DRAFT:
            raise ValueError("Event is not in draft status")

        # Override sharing level if specified
        if sharing_level is not None:
            event.sharing_level = sharing_level

        # Check for PII in shareable narrative
        if event.sharing_level != SharingLevel.PRIVATE and event.narrative_shareable:
            pii_result = self.pii_detector.analyze(event.narrative_shareable)
            if pii_result["has_potential_pii"] and not confirm_no_pii:
                raise ValueError(
                    f"Potential PII detected in shareable narrative: "
                    f"{', '.join(pii_result['warnings'])}. "
                    f"Remove PII or set confirm_no_pii=True to override."
                )

        # Update event status
        event.status = FraudEventStatus.SUBMITTED
        event.submitted_at = datetime.now(timezone.utc)
        event.submitted_by_user_id = user_id

        # Create shared artifact if sharing is enabled
        if event.sharing_level != SharingLevel.PRIVATE:
            await self._create_shared_artifact(event)

        await self.db.flush()
        return event

    async def withdraw_fraud_event(
        self,
        event_id: str,
        tenant_id: str,
        user_id: str,
        reason: str,
    ) -> FraudEvent:
        """Withdraw a submitted fraud event."""
        event = await self.get_fraud_event(event_id, tenant_id)
        if not event:
            raise ValueError("Event not found")

        if event.status != FraudEventStatus.SUBMITTED:
            raise ValueError("Can only withdraw submitted events")

        event.status = FraudEventStatus.WITHDRAWN
        event.withdrawn_at = datetime.now(timezone.utc)
        event.withdrawn_by_user_id = user_id
        event.withdrawn_reason = reason

        # Deactivate shared artifact
        if event.shared_artifact:
            event.shared_artifact.is_active = False

        await self.db.flush()
        return event

    # ========================================================================
    # Shared Artifact Management
    # ========================================================================

    async def _create_shared_artifact(self, event: FraudEvent) -> FraudSharedArtifact:
        """Create a shared artifact from a fraud event."""
        # Get check item for indicator extraction
        check_item = None
        if event.check_item_id:
            result = await self.db.execute(
                select(CheckItem).where(CheckItem.id == event.check_item_id)
            )
            check_item = result.scalar_one_or_none()

        # Generate indicators if network matching is enabled
        indicators = None
        if event.sharing_level == SharingLevel.NETWORK_MATCH and check_item:
            config = await self.get_tenant_config(event.tenant_id)

            indicators = self.hashing.generate_indicators(
                routing_number=check_item.routing_number or check_item.micr_routing,
                payee_name=check_item.payee_name,
                check_number=check_item.check_number,
                amount_bucket=event.amount_bucket.value,
                date_bucket=event.event_date.strftime("%Y-%m"),
                account_number=check_item.micr_account if config.allow_account_indicator_sharing else None,
                include_account=config.allow_account_indicator_sharing,
            )

        artifact = FraudSharedArtifact(
            id=str(uuid4()),
            tenant_id=event.tenant_id,
            fraud_event_id=event.id,
            sharing_level=event.sharing_level,
            occurred_at=event.event_date,
            occurred_month=event.event_date.strftime("%Y-%m"),
            fraud_type=event.fraud_type,
            channel=event.channel,
            amount_bucket=event.amount_bucket,
            indicators_json=indicators,
            is_active=True,
        )

        self.db.add(artifact)
        await self.db.flush()
        return artifact

    # ========================================================================
    # Network Matching
    # ========================================================================

    async def check_network_matches(
        self,
        tenant_id: str,
        check_item_id: str,
    ) -> NetworkAlertSummary:
        """Check for network matches for a check item."""
        # Get check item
        result = await self.db.execute(
            select(CheckItem).where(CheckItem.id == check_item_id)
        )
        check_item = result.scalar_one_or_none()
        if not check_item:
            return NetworkAlertSummary(
                has_alerts=False,
                total_alerts=0,
                highest_severity=None,
                alerts=[],
            )

        # Get tenant config
        config = await self.get_tenant_config(tenant_id)
        if not config.receive_network_alerts:
            return NetworkAlertSummary(
                has_alerts=False,
                total_alerts=0,
                highest_severity=None,
                alerts=[],
            )

        # Generate indicators for this check
        indicators = self.hashing.generate_indicators(
            routing_number=check_item.routing_number or check_item.micr_routing,
            payee_name=check_item.payee_name,
            check_number=check_item.check_number,
            amount_bucket=get_amount_bucket(check_item.amount).value,
            date_bucket=check_item.presented_date.strftime("%Y-%m") if check_item.presented_date else None,
        )

        if not indicators:
            return NetworkAlertSummary(
                has_alerts=False,
                total_alerts=0,
                highest_severity=None,
                alerts=[],
            )

        # Find matching artifacts (excluding same tenant)
        matching_artifacts = await self._find_matching_artifacts(
            tenant_id=tenant_id,
            indicators=indicators,
        )

        if not matching_artifacts:
            return NetworkAlertSummary(
                has_alerts=False,
                total_alerts=0,
                highest_severity=None,
                alerts=[],
            )

        # Create or update network alert
        alert = await self._create_or_update_alert(
            tenant_id=tenant_id,
            check_item_id=check_item_id,
            matching_artifacts=matching_artifacts,
            indicators=indicators,
        )

        # Check if alert meets minimum severity
        if self._severity_rank(alert.severity) < self._severity_rank(config.minimum_alert_severity):
            return NetworkAlertSummary(
                has_alerts=False,
                total_alerts=0,
                highest_severity=None,
                alerts=[],
            )

        # Build response
        alert_response = await self._build_alert_response(alert)

        return NetworkAlertSummary(
            has_alerts=True,
            total_alerts=1,
            highest_severity=alert.severity,
            alerts=[alert_response],
        )

    async def _find_matching_artifacts(
        self,
        tenant_id: str,
        indicators: dict[str, str],
    ) -> list[FraudSharedArtifact]:
        """Find shared artifacts matching the given indicators."""
        # Build OR conditions for each indicator
        conditions = []

        if "routing_hash" in indicators:
            conditions.append(
                FraudSharedArtifact.indicators_json["routing_hash"].astext == indicators["routing_hash"]
            )
        if "payee_hash" in indicators:
            conditions.append(
                FraudSharedArtifact.indicators_json["payee_hash"].astext == indicators["payee_hash"]
            )
        if "check_fingerprint" in indicators:
            conditions.append(
                FraudSharedArtifact.indicators_json["check_fingerprint"].astext == indicators["check_fingerprint"]
            )

        if not conditions:
            return []

        # Query for matching artifacts
        query = select(FraudSharedArtifact).where(
            FraudSharedArtifact.is_active == True,
            FraudSharedArtifact.sharing_level == SharingLevel.NETWORK_MATCH,
            FraudSharedArtifact.tenant_id != tenant_id,  # Exclude same tenant
            or_(*conditions),
        )

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def _create_or_update_alert(
        self,
        tenant_id: str,
        check_item_id: str,
        matching_artifacts: list[FraudSharedArtifact],
        indicators: dict[str, str],
    ) -> NetworkMatchAlert:
        """Create or update a network match alert."""
        # Check for existing alert
        result = await self.db.execute(
            select(NetworkMatchAlert).where(
                NetworkMatchAlert.tenant_id == tenant_id,
                NetworkMatchAlert.check_item_id == check_item_id,
                NetworkMatchAlert.dismissed_at.is_(None),
            )
        )
        alert = result.scalar_one_or_none()

        # Compute match reasons
        match_reasons = self._compute_match_reasons(matching_artifacts, indicators)

        # Compute severity
        severity = self._compute_severity(matching_artifacts, match_reasons)

        # Count distinct institutions
        distinct_tenants = len(set(a.tenant_id for a in matching_artifacts))

        # Get date range
        dates = [a.occurred_at for a in matching_artifacts if a.occurred_at]
        earliest = min(dates) if dates else None
        latest = max(dates) if dates else None

        now = datetime.now(timezone.utc)

        if alert:
            # Update existing alert
            alert.matched_artifact_ids = [a.id for a in matching_artifacts]
            alert.match_reasons = match_reasons
            alert.severity = severity
            alert.total_matches = len(matching_artifacts)
            alert.distinct_institutions = distinct_tenants
            alert.earliest_match_date = earliest
            alert.latest_match_date = latest
            alert.last_checked_at = now
        else:
            # Create new alert
            alert = NetworkMatchAlert(
                id=str(uuid4()),
                tenant_id=tenant_id,
                check_item_id=check_item_id,
                matched_artifact_ids=[a.id for a in matching_artifacts],
                match_reasons=match_reasons,
                severity=severity,
                total_matches=len(matching_artifacts),
                distinct_institutions=distinct_tenants,
                earliest_match_date=earliest,
                latest_match_date=latest,
                last_checked_at=now,
            )
            self.db.add(alert)

        await self.db.flush()
        return alert

    def _compute_match_reasons(
        self,
        artifacts: list[FraudSharedArtifact],
        indicators: dict[str, str],
    ) -> dict[str, Any]:
        """Compute aggregated match reasons."""
        reasons = {}

        indicator_types = ["routing_hash", "payee_hash", "check_fingerprint"]

        for ind_type in indicator_types:
            if ind_type not in indicators:
                continue

            matching = [
                a for a in artifacts
                if a.indicators_json and a.indicators_json.get(ind_type) == indicators[ind_type]
            ]

            if not matching:
                continue

            dates = [a.occurred_at for a in matching if a.occurred_at]
            fraud_types = list(set(a.fraud_type.value for a in matching))
            channels = list(set(a.channel.value for a in matching))

            reasons[ind_type] = {
                "count": len(matching),
                "first_seen": min(dates).strftime("%Y-%m") if dates else None,
                "last_seen": max(dates).strftime("%Y-%m") if dates else None,
                "fraud_types": fraud_types,
                "channels": channels,
            }

        return reasons

    def _compute_severity(
        self,
        artifacts: list[FraudSharedArtifact],
        match_reasons: dict[str, Any],
    ) -> MatchSeverity:
        """Compute alert severity based on matches."""
        total_matches = len(artifacts)
        indicator_types_matched = len(match_reasons)

        # High: 2+ distinct indicator types OR 3+ artifacts
        if indicator_types_matched >= 2 or total_matches >= 3:
            return MatchSeverity.HIGH

        # Medium: 2 artifacts on 1 indicator type
        if total_matches >= 2:
            return MatchSeverity.MEDIUM

        # Low: 1 artifact matched
        return MatchSeverity.LOW

    def _severity_rank(self, severity: MatchSeverity) -> int:
        """Get numeric rank for severity comparison."""
        return {
            MatchSeverity.LOW: 1,
            MatchSeverity.MEDIUM: 2,
            MatchSeverity.HIGH: 3,
        }.get(severity, 0)

    async def _build_alert_response(self, alert: NetworkMatchAlert) -> NetworkAlertResponse:
        """Build alert response with match reason details."""
        match_reasons = []
        for ind_type, data in alert.match_reasons.items():
            match_reasons.append(MatchReasonDetail(
                indicator_type=ind_type,
                match_count=data["count"],
                first_seen=data.get("first_seen", ""),
                last_seen=data.get("last_seen", ""),
                fraud_types=data.get("fraud_types", []),
                channels=data.get("channels", []),
            ))

        return NetworkAlertResponse(
            id=alert.id,
            check_item_id=alert.check_item_id,
            case_id=alert.case_id,
            severity=alert.severity,
            total_matches=alert.total_matches,
            distinct_institutions=alert.distinct_institutions,
            earliest_match_date=alert.earliest_match_date,
            latest_match_date=alert.latest_match_date,
            match_reasons=match_reasons,
            created_at=alert.created_at,
            last_checked_at=alert.last_checked_at,
            is_dismissed=alert.dismissed_at is not None,
            dismissed_at=alert.dismissed_at,
            dismissed_reason=alert.dismissed_reason,
        )

    async def dismiss_alert(
        self,
        alert_id: str,
        tenant_id: str,
        user_id: str,
        reason: str | None = None,
    ) -> NetworkMatchAlert:
        """Dismiss a network match alert."""
        result = await self.db.execute(
            select(NetworkMatchAlert).where(
                NetworkMatchAlert.id == alert_id,
                NetworkMatchAlert.tenant_id == tenant_id,
            )
        )
        alert = result.scalar_one_or_none()

        if not alert:
            raise ValueError("Alert not found")

        alert.dismissed_at = datetime.now(timezone.utc)
        alert.dismissed_by_user_id = user_id
        alert.dismissed_reason = reason

        await self.db.flush()
        return alert

    # ========================================================================
    # PII Detection
    # ========================================================================

    def check_pii(self, text: str, strict: bool = False) -> PIIDetectionResult:
        """Check text for potential PII."""
        detector = get_pii_detection_service(strict=strict)
        result = detector.analyze(text)

        return PIIDetectionResult(
            has_potential_pii=result["has_potential_pii"],
            warnings=result["warnings"],
            detected_patterns=result["detected_patterns"],
        )

    # ========================================================================
    # Network Trends
    # ========================================================================

    async def get_network_trends(
        self,
        tenant_id: str,
        range_months: int = 6,
        granularity: str = "month",
    ) -> dict[str, Any]:
        """Get network fraud trends (aggregate data only)."""
        config = await self.get_tenant_config(tenant_id)

        # Tenant must have sharing level >= 1 to see network trends
        if config.default_sharing_level == SharingLevel.PRIVATE:
            raise ValueError("Network trends require sharing level >= 1")

        privacy_threshold = settings.FRAUD_PRIVACY_THRESHOLD

        # Calculate date range
        end_date = datetime.now(timezone.utc)
        from dateutil.relativedelta import relativedelta
        start_date = end_date - relativedelta(months=range_months)

        # Get your bank's data
        your_bank_query = select(
            FraudSharedArtifact.fraud_type,
            FraudSharedArtifact.channel,
            FraudSharedArtifact.amount_bucket,
            FraudSharedArtifact.occurred_month,
            func.count().label("count"),
        ).where(
            FraudSharedArtifact.tenant_id == tenant_id,
            FraudSharedArtifact.is_active == True,
            FraudSharedArtifact.occurred_at >= start_date,
        ).group_by(
            FraudSharedArtifact.fraud_type,
            FraudSharedArtifact.channel,
            FraudSharedArtifact.amount_bucket,
            FraudSharedArtifact.occurred_month,
        )

        # Get network data (excluding your bank)
        network_query = select(
            FraudSharedArtifact.fraud_type,
            FraudSharedArtifact.channel,
            FraudSharedArtifact.amount_bucket,
            FraudSharedArtifact.occurred_month,
            func.count().label("count"),
        ).where(
            FraudSharedArtifact.tenant_id != tenant_id,
            FraudSharedArtifact.is_active == True,
            FraudSharedArtifact.sharing_level >= SharingLevel.AGGREGATE,
            FraudSharedArtifact.occurred_at >= start_date,
        ).group_by(
            FraudSharedArtifact.fraud_type,
            FraudSharedArtifact.channel,
            FraudSharedArtifact.amount_bucket,
            FraudSharedArtifact.occurred_month,
        )

        your_bank_result = await self.db.execute(your_bank_query)
        network_result = await self.db.execute(network_query)

        your_bank_data = list(your_bank_result.all())
        network_data = list(network_result.all())

        # Process and aggregate the data
        # Apply privacy thresholding
        def apply_threshold(count: int) -> tuple[int, str]:
            if count < privacy_threshold:
                return count, f"<{privacy_threshold}"
            return count, str(count)

        # Build response structure
        return {
            "period_start": start_date.isoformat(),
            "period_end": end_date.isoformat(),
            "your_bank_total": sum(r.count for r in your_bank_data),
            "network_total": sum(r.count for r in network_data),
            "privacy_threshold": privacy_threshold,
            "by_type": self._aggregate_by_field(your_bank_data, network_data, "fraud_type", privacy_threshold),
            "by_channel": self._aggregate_by_field(your_bank_data, network_data, "channel", privacy_threshold),
            "by_amount": self._aggregate_by_field(your_bank_data, network_data, "amount_bucket", privacy_threshold),
        }

    def _aggregate_by_field(
        self,
        your_data: list,
        network_data: list,
        field: str,
        threshold: int,
    ) -> list[dict]:
        """Aggregate data by a specific field."""
        # Group by field value
        your_grouped = {}
        network_grouped = {}

        for row in your_data:
            key = getattr(row, field)
            your_grouped[key] = your_grouped.get(key, 0) + row.count

        for row in network_data:
            key = getattr(row, field)
            network_grouped[key] = network_grouped.get(key, 0) + row.count

        # Combine all keys
        all_keys = set(your_grouped.keys()) | set(network_grouped.keys())

        result = []
        for key in sorted(all_keys, key=lambda x: x.value if hasattr(x, "value") else str(x)):
            your_count = your_grouped.get(key, 0)
            network_count = network_grouped.get(key, 0)

            result.append({
                field: key.value if hasattr(key, "value") else str(key),
                "your_bank_count": your_count,
                "your_bank_display": f"<{threshold}" if your_count < threshold else str(your_count),
                "network_count": network_count,
                "network_display": f"<{threshold}" if network_count < threshold else str(network_count),
            })

        return result
