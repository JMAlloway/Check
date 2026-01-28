"""
Item lookup endpoint.

Provides authenticated access to check item metadata.
"""
import time
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ....audit import AuditAction, AuditEvent, get_audit_logger
from ....core.security import JWTClaims
from ....models import ErrorResponse, ItemLookupResponse
from ....services import get_image_service
from ...deps import get_correlation_id, get_request_start_time, validate_jwt

router = APIRouter()


@router.get(
    "/lookup",
    response_model=ItemLookupResponse,
    summary="Lookup Item Metadata",
    description="Look up check item metadata by trace number and date.",
    responses={
        200: {"description": "Item found"},
        401: {"model": ErrorResponse, "description": "Authentication failed"},
        403: {"model": ErrorResponse, "description": "Forbidden"},
        404: {"model": ErrorResponse, "description": "Item not found"}
    }
)
async def lookup_item(
    trace: str = Query(..., description="Check trace number"),
    date: date = Query(..., description="Check date (YYYY-MM-DD)"),
    claims: JWTClaims = Depends(validate_jwt),
    correlation_id: str = Depends(get_correlation_id),
    start_time: float = Depends(get_request_start_time)
) -> ItemLookupResponse:
    """
    Look up check item metadata.

    Returns minimal metadata with masked account number (last 4 digits only).
    Requires JWT authentication with appropriate roles.
    """
    audit_logger = get_audit_logger()
    image_service = get_image_service()

    # Log the lookup
    event = AuditEvent.create(
        action=AuditAction.ITEM_LOOKUP,
        endpoint="/v1/items/lookup",
        allow=True,
        correlation_id=correlation_id,
        org_id=claims.org_id,
        user_id=claims.sub,
        trace_number=trace,
        check_date=date.isoformat()
    )
    await audit_logger.log(event)

    # Look up the item
    result = await image_service.lookup_item(trace, date)

    if not result:
        latency_ms = int((time.time() - start_time) * 1000)

        # Log not found
        event = AuditEvent.create(
            action=AuditAction.ITEM_LOOKUP,
            endpoint="/v1/items/lookup",
            allow=False,
            correlation_id=correlation_id,
            org_id=claims.org_id,
            user_id=claims.sub,
            trace_number=trace,
            check_date=date.isoformat(),
            error_code="NOT_FOUND",
            error_message="Item not found",
            latency_ms=latency_ms
        )
        await audit_logger.log(event)

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error_code": "NOT_FOUND",
                "message": f"Item not found: trace={trace}, date={date}",
                "correlation_id": correlation_id
            }
        )

    return ItemLookupResponse(**result)
