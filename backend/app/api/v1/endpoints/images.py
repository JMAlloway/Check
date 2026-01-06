"""Check image endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status

from app.api.deps import DBSession, CurrentUser, require_permission
from app.core.security import verify_signed_url
from app.integrations.adapters.factory import get_adapter
from app.audit.service import AuditService
from app.models.audit import AuditAction

router = APIRouter()


@router.get("/secure/{token}")
async def get_secure_image(
    token: str,
    db: DBSession,
    thumbnail: bool = Query(False),
):
    """
    Get check image via signed URL token.

    This endpoint provides secure, time-limited access to check images.
    The token contains the image ID and expiration time.
    """
    # Verify the signed URL token
    resource_id = verify_signed_url(token)

    if not resource_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired image URL",
        )

    # Handle thumbnail prefix
    is_thumbnail = resource_id.startswith("thumb_")
    if is_thumbnail:
        resource_id = resource_id[6:]  # Remove "thumb_" prefix

    adapter = get_adapter()

    if is_thumbnail or thumbnail:
        image_data = await adapter.get_thumbnail(resource_id)
        if image_data:
            return Response(
                content=image_data,
                media_type="image/png",
                headers={
                    "Cache-Control": "private, max-age=300",
                    "Content-Disposition": "inline",
                },
            )
    else:
        image = await adapter.get_image(resource_id)
        if image:
            return Response(
                content=image.content,
                media_type=image.content_type,
                headers={
                    "Cache-Control": "private, max-age=60",
                    "Content-Disposition": "inline",
                },
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
                description=f"User viewed check image",
            )

            return Response(
                content=image.content,
                media_type=image.content_type,
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
    current_user: CurrentUser,
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
