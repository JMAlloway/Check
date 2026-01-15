"""Fraud Intelligence Sharing API endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import DBSession, CurrentUser, require_permission, require_role, get_tenant_id
from app.models.fraud import FraudType, FraudEventStatus, SharingLevel
from app.schemas.fraud import (
    FraudEventCreate,
    FraudEventUpdate,
    FraudEventSubmit,
    FraudEventWithdraw,
    FraudEventResponse,
    FraudEventListResponse,
    NetworkAlertResponse,
    NetworkAlertSummary,
    NetworkAlertDismiss,
    NetworkTrendsResponse,
    NetworkTrendsRequest,
    TenantFraudConfigResponse,
    TenantFraudConfigUpdate,
    PIICheckRequest,
    PIIDetectionResult,
)
from app.schemas.common import PaginatedResponse
from app.services.fraud_service import FraudService
from app.audit.service import AuditService
from app.models.audit import AuditAction

router = APIRouter()


# ============================================================================
# Fraud Event Endpoints
# ============================================================================
# NOTE: get_tenant_id is now imported from app.api.deps
# It validates that tenant_id exists and raises an error if missing
# This eliminates the dangerous DEFAULT_TENANT_ID fallback

@router.post("/fraud-events", response_model=FraudEventResponse, status_code=status.HTTP_201_CREATED)
async def create_fraud_event(
    data: FraudEventCreate,
    db: DBSession,
    current_user: Annotated[object, Depends(require_permission("fraud", "create"))],
):
    """
    Create a new fraud event.

    Creates a fraud event in DRAFT status. The event must be submitted
    separately to share it with the network.

    Required permission: fraud:create
    """
    tenant_id = get_tenant_id(current_user)
    fraud_service = FraudService(db)

    event = await fraud_service.create_fraud_event(
        tenant_id=tenant_id,
        user_id=str(current_user.id),
        data=data,
    )

    # Audit log
    audit_service = AuditService(db)
    await audit_service.log(
        action=AuditAction.FRAUD_EVENT_CREATED,
        resource_type="fraud_event",
        resource_id=event.id,
        user_id=current_user.id,
        username=current_user.username,
        description=f"Created fraud event for {data.fraud_type.value}",
    )

    return FraudEventResponse(
        **event.__dict__,
        has_shared_artifact=event.shared_artifact is not None,
    )


@router.get("/fraud-events", response_model=PaginatedResponse[FraudEventListResponse])
async def list_fraud_events(
    db: DBSession,
    current_user: Annotated[object, Depends(require_permission("fraud", "view"))],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: FraudEventStatus | None = None,
    fraud_type: FraudType | None = None,
    check_item_id: str | None = None,
):
    """
    List fraud events for the current tenant.

    Required permission: fraud:view
    """
    tenant_id = get_tenant_id(current_user)
    fraud_service = FraudService(db)

    events, total = await fraud_service.list_fraud_events(
        tenant_id=tenant_id,
        status=status,
        fraud_type=fraud_type,
        check_item_id=check_item_id,
        page=page,
        page_size=page_size,
    )

    total_pages = (total + page_size - 1) // page_size

    return PaginatedResponse(
        items=[FraudEventListResponse.model_validate(e) for e in events],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        has_next=page < total_pages,
        has_previous=page > 1,
    )


@router.get("/fraud-events/{event_id}", response_model=FraudEventResponse)
async def get_fraud_event(
    event_id: str,
    db: DBSession,
    current_user: Annotated[object, Depends(require_permission("fraud", "view"))],
):
    """
    Get a specific fraud event.

    Required permission: fraud:view
    """
    tenant_id = get_tenant_id(current_user)
    fraud_service = FraudService(db)

    event = await fraud_service.get_fraud_event(event_id, tenant_id)
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Fraud event not found",
        )

    return FraudEventResponse(
        **event.__dict__,
        has_shared_artifact=event.shared_artifact is not None,
    )


@router.patch("/fraud-events/{event_id}", response_model=FraudEventResponse)
async def update_fraud_event(
    event_id: str,
    data: FraudEventUpdate,
    db: DBSession,
    current_user: Annotated[object, Depends(require_permission("fraud", "create"))],
):
    """
    Update a fraud event (draft only).

    Can only update events in DRAFT status.

    Required permission: fraud:create
    """
    tenant_id = get_tenant_id(current_user)
    fraud_service = FraudService(db)

    try:
        event = await fraud_service.update_fraud_event(event_id, tenant_id, data)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Fraud event not found",
        )

    return FraudEventResponse(
        **event.__dict__,
        has_shared_artifact=event.shared_artifact is not None,
    )


@router.post("/fraud-events/{event_id}/submit", response_model=FraudEventResponse)
async def submit_fraud_event(
    event_id: str,
    data: FraudEventSubmit,
    db: DBSession,
    current_user: Annotated[object, Depends(require_permission("fraud", "submit"))],
):
    """
    Submit a fraud event for sharing.

    Changes status from DRAFT to SUBMITTED. If sharing level > 0,
    creates a shared artifact for network intelligence.

    Required permission: fraud:submit
    """
    tenant_id = get_tenant_id(current_user)
    fraud_service = FraudService(db)

    try:
        event = await fraud_service.submit_fraud_event(
            event_id=event_id,
            tenant_id=tenant_id,
            user_id=str(current_user.id),
            sharing_level=data.sharing_level,
            confirm_no_pii=data.confirm_no_pii,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    # Audit log
    audit_service = AuditService(db)
    await audit_service.log(
        action=AuditAction.FRAUD_EVENT_SUBMITTED,
        resource_type="fraud_event",
        resource_id=event.id,
        user_id=current_user.id,
        username=current_user.username,
        description=f"Submitted fraud event with sharing level {event.sharing_level}",
    )

    return FraudEventResponse(
        **event.__dict__,
        has_shared_artifact=event.shared_artifact is not None,
    )


@router.post("/fraud-events/{event_id}/withdraw", response_model=FraudEventResponse)
async def withdraw_fraud_event(
    event_id: str,
    data: FraudEventWithdraw,
    db: DBSession,
    current_user: Annotated[object, Depends(require_permission("fraud", "withdraw"))],
):
    """
    Withdraw a submitted fraud event.

    Deactivates the shared artifact so it no longer contributes to
    network matching.

    Required permission: fraud:withdraw
    """
    tenant_id = get_tenant_id(current_user)
    fraud_service = FraudService(db)

    try:
        event = await fraud_service.withdraw_fraud_event(
            event_id=event_id,
            tenant_id=tenant_id,
            user_id=str(current_user.id),
            reason=data.reason,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    # Audit log
    audit_service = AuditService(db)
    await audit_service.log(
        action=AuditAction.FRAUD_EVENT_WITHDRAWN,
        resource_type="fraud_event",
        resource_id=event.id,
        user_id=current_user.id,
        username=current_user.username,
        description=f"Withdrew fraud event: {data.reason[:100]}",
    )

    return FraudEventResponse(
        **event.__dict__,
        has_shared_artifact=event.shared_artifact is not None,
    )


# ============================================================================
# Network Alert Endpoints
# ============================================================================

@router.get("/network-alerts", response_model=NetworkAlertSummary)
async def get_network_alerts(
    db: DBSession,
    current_user: Annotated[object, Depends(require_permission("fraud", "view"))],
    check_item_id: str | None = None,
    case_id: str | None = None,
):
    """
    Get network match alerts for a check item or case.

    Returns alerts showing matches against network fraud indicators
    without revealing other institutions' identities.

    Required permission: fraud:view
    """
    if not check_item_id and not case_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Must provide check_item_id or case_id",
        )

    tenant_id = get_tenant_id(current_user)
    fraud_service = FraudService(db)

    if check_item_id:
        summary = await fraud_service.check_network_matches(
            tenant_id=tenant_id,
            check_item_id=check_item_id,
        )
        return summary

    # Case-based alerts would be implemented similarly
    return NetworkAlertSummary(
        has_alerts=False,
        total_alerts=0,
        highest_severity=None,
        alerts=[],
    )


@router.post("/network-alerts/{alert_id}/dismiss", response_model=NetworkAlertResponse)
async def dismiss_network_alert(
    alert_id: str,
    data: NetworkAlertDismiss,
    db: DBSession,
    current_user: Annotated[object, Depends(require_permission("fraud", "view"))],
):
    """
    Dismiss a network match alert.

    Required permission: fraud:view
    """
    tenant_id = get_tenant_id(current_user)
    fraud_service = FraudService(db)

    try:
        alert = await fraud_service.dismiss_alert(
            alert_id=alert_id,
            tenant_id=tenant_id,
            user_id=str(current_user.id),
            reason=data.reason,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )

    return await fraud_service._build_alert_response(alert)


# ============================================================================
# Network Trends Endpoints
# ============================================================================

@router.get("/network-trends")
async def get_network_trends(
    db: DBSession,
    current_user: Annotated[object, Depends(require_permission("fraud", "view"))],
    range: str = Query("6m", pattern=r"^(1m|3m|6m|12m|24m)$"),
    granularity: str = Query("month", pattern=r"^(week|month)$"),
):
    """
    Get aggregated network fraud trends.

    Returns anonymized statistics comparing your bank's fraud events
    with network-wide trends. Privacy thresholds are applied to prevent
    identification of small populations.

    Required permission: fraud:view
    Requires: Sharing level >= 1 (Aggregate)
    """
    tenant_id = get_tenant_id(current_user)
    fraud_service = FraudService(db)

    # Parse range
    range_months = {
        "1m": 1,
        "3m": 3,
        "6m": 6,
        "12m": 12,
        "24m": 24,
    }.get(range, 6)

    try:
        trends = await fraud_service.get_network_trends(
            tenant_id=tenant_id,
            range_months=range_months,
            granularity=granularity,
        )
        return trends
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )


# ============================================================================
# Tenant Configuration Endpoints
# ============================================================================

@router.get("/config", response_model=TenantFraudConfigResponse)
async def get_tenant_fraud_config(
    db: DBSession,
    current_user: Annotated[object, Depends(require_role("admin"))],
):
    """
    Get tenant fraud sharing configuration.

    Required role: admin
    """
    tenant_id = get_tenant_id(current_user)
    fraud_service = FraudService(db)

    config = await fraud_service.get_tenant_config(tenant_id)
    return TenantFraudConfigResponse.model_validate(config)


@router.patch("/config", response_model=TenantFraudConfigResponse)
async def update_tenant_fraud_config(
    data: TenantFraudConfigUpdate,
    db: DBSession,
    current_user: Annotated[object, Depends(require_role("admin"))],
):
    """
    Update tenant fraud sharing configuration.

    Required role: admin
    """
    tenant_id = get_tenant_id(current_user)
    fraud_service = FraudService(db)

    config = await fraud_service.update_tenant_config(
        tenant_id=tenant_id,
        updates=data.model_dump(exclude_unset=True),
        modified_by_user_id=str(current_user.id),
    )

    # Audit log
    audit_service = AuditService(db)
    await audit_service.log(
        action=AuditAction.FRAUD_CONFIG_UPDATED,
        resource_type="tenant_fraud_config",
        resource_id=tenant_id,
        user_id=current_user.id,
        username=current_user.username,
        description="Updated fraud sharing configuration",
        after_value=data.model_dump(exclude_unset=True),
    )

    return TenantFraudConfigResponse.model_validate(config)


# ============================================================================
# PII Detection Endpoint
# ============================================================================

@router.post("/check-pii", response_model=PIIDetectionResult)
async def check_pii(
    data: PIICheckRequest,
    current_user: Annotated[object, Depends(require_permission("fraud", "create"))],
):
    """
    Check text for potential PII.

    Analyzes text for patterns that might indicate personally
    identifiable information. Use this before submitting shareable
    narratives.

    Required permission: fraud:create
    """
    from app.services.pii_detection import get_pii_detection_service

    detector = get_pii_detection_service(strict=data.strict)
    result = detector.analyze(data.text)

    return PIIDetectionResult(
        has_potential_pii=result["has_potential_pii"],
        warnings=result["warnings"],
        detected_patterns=result["detected_patterns"],
    )
