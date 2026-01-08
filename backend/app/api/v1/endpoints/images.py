"""Check image endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status

from app.api.deps import DBSession, require_permission
from app.core.security import verify_signed_url
from app.integrations.adapters.factory import get_adapter
from app.audit.service import AuditService
from app.models.audit import AuditAction

router = APIRouter()

# Security headers for bank-grade image handling
SECURE_IMAGE_HEADERS = {
    # Prevent caching in shared caches (CDNs, proxies)
    "Cache-Control": "private, no-store, no-cache, must-revalidate, max-age=0",
    "Pragma": "no-cache",
    "Expires": "0",
    # Prevent content sniffing
    "X-Content-Type-Options": "nosniff",
    # Prevent embedding in iframes on other sites
    "X-Frame-Options": "SAMEORIGIN",
    # Basic XSS protection
    "X-XSS-Protection": "1; mode=block",
    # Prevent download managers from caching
    "Content-Disposition": "inline",
}


@router.get("/secure/{token}")
async def get_secure_image(
    request: Request,
    token: str,
    db: DBSession,
    current_user: Annotated[object, Depends(require_permission("check_image", "view"))],
    thumbnail: bool = Query(False),
):
    """
    Get check image via signed URL token.

    Security:
    - Token must be valid and not expired
    - Token must be bound to the requesting user (prevents URL sharing)
    - Access is logged for audit trail
    - Response headers prevent caching in shared locations
    """
    # Verify the signed URL token
    payload = verify_signed_url(token)

    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired image URL",
        )

    # CRITICAL: Validate the token was issued to this user
    if payload.user_id != current_user.id:
        # Log attempted access with wrong user
        audit_service = AuditService(db)
        await audit_service.log(
            action=AuditAction.UNAUTHORIZED_ACCESS,
            resource_type="check_image",
            resource_id=payload.resource_id,
            user_id=current_user.id,
            username=current_user.username,
            ip_address=request.client.host if request.client else None,
            description=f"Attempted to access image with URL issued to different user",
            metadata={"token_user_id": payload.user_id},
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This image URL was not issued to you",
        )

    resource_id = payload.resource_id

    # Handle thumbnail prefix
    is_thumbnail = resource_id.startswith("thumb_")
    if is_thumbnail:
        resource_id = resource_id[6:]  # Remove "thumb_" prefix

    adapter = get_adapter()
    audit_service = AuditService(db)

    if is_thumbnail or thumbnail:
        image_data = await adapter.get_thumbnail(resource_id)
        if image_data:
            # Log thumbnail access (less detailed than full image)
            await audit_service.log(
                action=AuditAction.IMAGE_VIEWED,
                resource_type="check_image_thumbnail",
                resource_id=resource_id,
                user_id=current_user.id,
                username=current_user.username,
                ip_address=request.client.host if request.client else None,
                description="User viewed check thumbnail via signed URL",
            )
            return Response(
                content=image_data,
                media_type="image/png",
                headers=SECURE_IMAGE_HEADERS,
            )
    else:
        image = await adapter.get_image(resource_id)
        if image:
            # Log full image access
            await audit_service.log(
                action=AuditAction.IMAGE_VIEWED,
                resource_type="check_image",
                resource_id=resource_id,
                user_id=current_user.id,
                username=current_user.username,
                ip_address=request.client.host if request.client else None,
                description="User viewed full check image via signed URL",
            )
            return Response(
                content=image.content,
                media_type=image.content_type,
                headers=SECURE_IMAGE_HEADERS,
            )

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Image not found",
    )


@router.get("/{image_id}")
async def get_image_direct(
    request: Request,
    image_id: str,
    db: DBSession,
    current_user: Annotated[object, Depends(require_permission("check_image", "view"))],
    thumbnail: bool = Query(False),
):
    """
    Get check image directly (requires authentication).

    This endpoint provides direct access to check images for authenticated users
    with appropriate permissions.
    """
    adapter = get_adapter()
    audit_service = AuditService(db)

    if thumbnail:
        image_data = await adapter.get_thumbnail(image_id)
        if image_data:
            return Response(
                content=image_data,
                media_type="image/png",
                headers=SECURE_IMAGE_HEADERS,
            )
    else:
        image = await adapter.get_image(image_id)
        if image:
            # Log image view
            await audit_service.log(
                action=AuditAction.IMAGE_VIEWED,
                resource_type="check_image",
                resource_id=image_id,
                user_id=current_user.id,
                username=current_user.username,
                ip_address=request.client.host if request.client else None,
                description="User viewed check image directly",
            )

            return Response(
                content=image.content,
                media_type=image.content_type,
                headers=SECURE_IMAGE_HEADERS,
            )

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Image not found",
    )


@router.post("/{image_id}/zoom")
async def log_image_zoom(
    request: Request,
    image_id: str,
    db: DBSession,
    current_user: Annotated[object, Depends(require_permission("check_image", "view"))],
    view_id: str | None = None,
    zoom_level: int = Query(..., ge=50, le=800),
):
    """Log that user used zoom on an image (for audit trail)."""
    audit_service = AuditService(db)

    await audit_service.log(
        action=AuditAction.IMAGE_ZOOMED,
        resource_type="check_image",
        resource_id=image_id,
        user_id=current_user.id,
        username=current_user.username,
        ip_address=request.client.host if request.client else None,
        description=f"User zoomed image to {zoom_level}%",
        metadata={"zoom_level": zoom_level, "view_id": view_id},
    )

    # Update item view tracking if view_id provided
    if view_id:
        await audit_service.update_item_view(view_id, zoom_used=True)

    return {"status": "logged"}
