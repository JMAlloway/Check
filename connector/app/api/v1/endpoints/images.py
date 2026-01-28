"""
Image endpoints.

Provides authenticated access to check images via:
- /v1/images/by-handle: Direct access by UNC path
- /v1/images/by-item: Access by trace number and date
"""
import time
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response

from ....adapters import ImageSide
from ....audit import get_audit_logger
from ....core.security import JWTClaims, get_path_validator
from ....models import ErrorResponse, ImageSideParam
from ....services import get_image_service
from ....services.image_service import (
    ImageDecodeFailedError,
    ImageNotFoundError,
    NoBackImageError,
    PathNotAllowedError,
    UnsupportedImageFormatError,
    UpstreamIOError,
)
from ...deps import get_correlation_id, get_request_start_time, validate_jwt, validate_path

router = APIRouter()

# Secure headers for image responses
SECURE_HEADERS = {
    "Cache-Control": "private, no-store, no-cache, must-revalidate, max-age=0",
    "Pragma": "no-cache",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "SAMEORIGIN",
    "X-XSS-Protection": "1; mode=block",
}


@router.get(
    "/by-handle",
    summary="Get Image by Handle (UNC Path)",
    description="Retrieve a check image using its UNC storage path.",
    responses={
        200: {
            "description": "Image retrieved successfully",
            "content": {"image/png": {}}
        },
        401: {"model": ErrorResponse, "description": "Authentication failed"},
        403: {"model": ErrorResponse, "description": "Forbidden or path not allowed"},
        404: {"model": ErrorResponse, "description": "Image not found"},
        415: {"model": ErrorResponse, "description": "Unsupported image format"},
        422: {"model": ErrorResponse, "description": "Image decode failed"},
        502: {"model": ErrorResponse, "description": "Upstream storage error"}
    }
)
async def get_image_by_handle(
    path: str = Query(..., description="UNC path to the image file"),
    side: ImageSideParam = Query(ImageSideParam.FRONT, description="Image side (front or back)"),
    claims: JWTClaims = Depends(validate_jwt),
    correlation_id: str = Depends(get_correlation_id),
    start_time: float = Depends(get_request_start_time)
) -> Response:
    """
    Get a check image by its UNC storage path.

    Requires JWT authentication with appropriate roles.
    Path must be within allowed share roots.

    Returns PNG image data with secure headers.
    """
    audit_logger = get_audit_logger()
    image_service = get_image_service()

    # Validate path against allowed roots
    validate_path(path, correlation_id, claims)

    # Log the request
    await audit_logger.log_image_request(
        endpoint="/v1/images/by-handle",
        correlation_id=correlation_id,
        org_id=claims.org_id,
        user_id=claims.sub,
        path=path,
        side=side.value
    )

    try:
        # Convert side enum
        image_side = ImageSide.FRONT if side == ImageSideParam.FRONT else ImageSide.BACK

        # Get the image
        result = await image_service.get_by_handle(path, image_side)

        # Calculate latency
        latency_ms = int((time.time() - start_time) * 1000)

        # Log success
        await audit_logger.log_image_served(
            endpoint="/v1/images/by-handle",
            correlation_id=correlation_id,
            org_id=claims.org_id,
            user_id=claims.sub,
            path=path,
            side=side.value,
            bytes_sent=len(result.data),
            latency_ms=latency_ms
        )

        # Return image with secure headers
        headers = {
            **SECURE_HEADERS,
            "X-Correlation-ID": correlation_id,
            "X-From-Cache": "true" if result.from_cache else "false",
            "X-Image-Width": str(result.width),
            "X-Image-Height": str(result.height),
        }

        return Response(
            content=result.data,
            media_type="image/png",
            headers=headers
        )

    except ImageNotFoundError:
        latency_ms = int((time.time() - start_time) * 1000)
        await audit_logger.log_denied(
            endpoint="/v1/images/by-handle",
            correlation_id=correlation_id,
            error_code="NOT_FOUND",
            error_message="Image not found",
            org_id=claims.org_id,
            user_id=claims.sub,
            path=path,
            latency_ms=latency_ms
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error_code": "NOT_FOUND",
                "message": "Image not found at the specified path",
                "correlation_id": correlation_id
            }
        )

    except NoBackImageError:
        latency_ms = int((time.time() - start_time) * 1000)
        await audit_logger.log_denied(
            endpoint="/v1/images/by-handle",
            correlation_id=correlation_id,
            error_code="NO_BACK_IMAGE",
            error_message="No back image available",
            org_id=claims.org_id,
            user_id=claims.sub,
            path=path,
            latency_ms=latency_ms
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error_code": "NO_BACK_IMAGE",
                "message": "No back image available for this check",
                "correlation_id": correlation_id
            }
        )

    except UnsupportedImageFormatError as e:
        latency_ms = int((time.time() - start_time) * 1000)
        await audit_logger.log_denied(
            endpoint="/v1/images/by-handle",
            correlation_id=correlation_id,
            error_code="UNSUPPORTED_FORMAT",
            error_message=str(e),
            org_id=claims.org_id,
            user_id=claims.sub,
            path=path,
            latency_ms=latency_ms
        )
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail={
                "error_code": "UNSUPPORTED_FORMAT",
                "message": str(e),
                "correlation_id": correlation_id
            }
        )

    except ImageDecodeFailedError as e:
        latency_ms = int((time.time() - start_time) * 1000)
        await audit_logger.log_denied(
            endpoint="/v1/images/by-handle",
            correlation_id=correlation_id,
            error_code="IMAGE_DECODE_FAILED",
            error_message=str(e),
            org_id=claims.org_id,
            user_id=claims.sub,
            path=path,
            latency_ms=latency_ms
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error_code": "IMAGE_DECODE_FAILED",
                "message": "Failed to decode image file",
                "correlation_id": correlation_id
            }
        )

    except UpstreamIOError as e:
        latency_ms = int((time.time() - start_time) * 1000)
        await audit_logger.log_denied(
            endpoint="/v1/images/by-handle",
            correlation_id=correlation_id,
            error_code="UPSTREAM_IO_ERROR",
            error_message=str(e),
            org_id=claims.org_id,
            user_id=claims.sub,
            path=path,
            latency_ms=latency_ms
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "error_code": "UPSTREAM_IO_ERROR",
                "message": "Failed to access upstream storage",
                "correlation_id": correlation_id
            }
        )


@router.get(
    "/by-item",
    summary="Get Image by Item",
    description="Retrieve a check image using trace number and date.",
    responses={
        200: {
            "description": "Image retrieved successfully",
            "content": {"image/png": {}}
        },
        401: {"model": ErrorResponse, "description": "Authentication failed"},
        403: {"model": ErrorResponse, "description": "Forbidden"},
        404: {"model": ErrorResponse, "description": "Item or image not found"},
        415: {"model": ErrorResponse, "description": "Unsupported image format"},
        422: {"model": ErrorResponse, "description": "Image decode failed"},
        502: {"model": ErrorResponse, "description": "Upstream storage error"}
    }
)
async def get_image_by_item(
    trace: str = Query(..., description="Check trace number"),
    date: date = Query(..., description="Check date (YYYY-MM-DD)"),
    side: ImageSideParam = Query(ImageSideParam.FRONT, description="Image side (front or back)"),
    claims: JWTClaims = Depends(validate_jwt),
    correlation_id: str = Depends(get_correlation_id),
    start_time: float = Depends(get_request_start_time)
) -> Response:
    """
    Get a check image by trace number and date.

    Resolves the item to find its storage location, then returns the image.
    Requires JWT authentication with appropriate roles.

    Returns PNG image data with secure headers.
    """
    audit_logger = get_audit_logger()
    image_service = get_image_service()

    # Log the request
    await audit_logger.log_image_request(
        endpoint="/v1/images/by-item",
        correlation_id=correlation_id,
        org_id=claims.org_id,
        user_id=claims.sub,
        trace_number=trace,
        check_date=date.isoformat(),
        side=side.value
    )

    try:
        # Convert side enum
        image_side = ImageSide.FRONT if side == ImageSideParam.FRONT else ImageSide.BACK

        # Get the image
        result = await image_service.get_by_item(trace, date, image_side)

        # Calculate latency
        latency_ms = int((time.time() - start_time) * 1000)

        # Log success
        await audit_logger.log_image_served(
            endpoint="/v1/images/by-item",
            correlation_id=correlation_id,
            org_id=claims.org_id,
            user_id=claims.sub,
            trace_number=trace,
            check_date=date.isoformat(),
            side=side.value,
            bytes_sent=len(result.data),
            latency_ms=latency_ms
        )

        # Return image with secure headers
        headers = {
            **SECURE_HEADERS,
            "X-Correlation-ID": correlation_id,
            "X-From-Cache": "true" if result.from_cache else "false",
            "X-Image-Width": str(result.width),
            "X-Image-Height": str(result.height),
        }

        return Response(
            content=result.data,
            media_type="image/png",
            headers=headers
        )

    except ImageNotFoundError:
        latency_ms = int((time.time() - start_time) * 1000)
        await audit_logger.log_denied(
            endpoint="/v1/images/by-item",
            correlation_id=correlation_id,
            error_code="NOT_FOUND",
            error_message="Item not found",
            org_id=claims.org_id,
            user_id=claims.sub,
            latency_ms=latency_ms
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error_code": "NOT_FOUND",
                "message": f"Item not found: trace={trace}, date={date}",
                "correlation_id": correlation_id
            }
        )

    except NoBackImageError:
        latency_ms = int((time.time() - start_time) * 1000)
        await audit_logger.log_denied(
            endpoint="/v1/images/by-item",
            correlation_id=correlation_id,
            error_code="NO_BACK_IMAGE",
            error_message="No back image available",
            org_id=claims.org_id,
            user_id=claims.sub,
            latency_ms=latency_ms
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error_code": "NO_BACK_IMAGE",
                "message": "No back image available for this check",
                "correlation_id": correlation_id
            }
        )

    except UnsupportedImageFormatError as e:
        latency_ms = int((time.time() - start_time) * 1000)
        await audit_logger.log_denied(
            endpoint="/v1/images/by-item",
            correlation_id=correlation_id,
            error_code="UNSUPPORTED_FORMAT",
            error_message=str(e),
            org_id=claims.org_id,
            user_id=claims.sub,
            latency_ms=latency_ms
        )
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail={
                "error_code": "UNSUPPORTED_FORMAT",
                "message": str(e),
                "correlation_id": correlation_id
            }
        )

    except ImageDecodeFailedError as e:
        latency_ms = int((time.time() - start_time) * 1000)
        await audit_logger.log_denied(
            endpoint="/v1/images/by-item",
            correlation_id=correlation_id,
            error_code="IMAGE_DECODE_FAILED",
            error_message=str(e),
            org_id=claims.org_id,
            user_id=claims.sub,
            latency_ms=latency_ms
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error_code": "IMAGE_DECODE_FAILED",
                "message": "Failed to decode image file",
                "correlation_id": correlation_id
            }
        )

    except UpstreamIOError as e:
        latency_ms = int((time.time() - start_time) * 1000)
        await audit_logger.log_denied(
            endpoint="/v1/images/by-item",
            correlation_id=correlation_id,
            error_code="UPSTREAM_IO_ERROR",
            error_message=str(e),
            org_id=claims.org_id,
            user_id=claims.sub,
            latency_ms=latency_ms
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "error_code": "UPSTREAM_IO_ERROR",
                "message": "Failed to access upstream storage",
                "correlation_id": correlation_id
            }
        )
