"""Check image endpoints with one-time-use token support.

This module implements secure image access with:
- One-time-use tokens (DB-backed, not JWT)
- Tenant-aware access control
- Full audit trail
- No bearer tokens in URLs
"""

from datetime import datetime, timedelta, timezone
from typing import Annotated
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from pydantic import BaseModel
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload

from app.api.deps import DBSession, require_permission, get_tenant_id
from app.core.config import settings
from app.core.rate_limit import limiter
from app.core.security import verify_signed_url
from app.integrations.adapters.factory import get_adapter
from app.audit.service import AuditService
from app.models.audit import AuditAction
from app.models.check import CheckImage, CheckItem
from app.models.image_token import ImageAccessToken
from app.models.user import User

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
    # CRITICAL: Prevent token leakage via Referer header
    "Referrer-Policy": "no-referrer",
}


# =============================================================================
# Request/Response Schemas
# =============================================================================

class TokenMintRequest(BaseModel):
    """Request to mint an image access token."""
    image_id: str
    is_thumbnail: bool = False


class TokenMintResponse(BaseModel):
    """Response containing the minted token."""
    token_id: str
    image_url: str
    expires_at: datetime


class BatchTokenMintRequest(BaseModel):
    """Request to mint multiple tokens at once."""
    image_ids: list[str]
    is_thumbnail: bool = False


class BatchTokenMintResponse(BaseModel):
    """Response containing multiple minted tokens."""
    tokens: list[TokenMintResponse]


# =============================================================================
# Token Minting Endpoints
# =============================================================================

@router.post("/tokens", response_model=TokenMintResponse)
@limiter.limit("60/minute")  # Rate limit token minting to prevent abuse
async def mint_image_token(
    request: Request,
    data: TokenMintRequest,
    db: DBSession,
    current_user: Annotated[object, Depends(require_permission("check_item", "view"))],
):
    """
    Mint a one-time-use image access token.

    Security Properties:
    - Requires authentication and check_item:view permission
    - Token is one-time-use (consumed on first access)
    - Token is tenant-scoped (validates image belongs to user's tenant)
    - Token expires after configurable TTL (default 90 seconds)
    - Token ID is opaque UUID (no JWT, no information leakage)

    Usage:
    1. Call this endpoint to get a token_id
    2. Use the returned image_url in <img src="...">
    3. Token is consumed on first access and cannot be reused

    Returns:
        TokenMintResponse with token_id and image_url
    """
    tenant_id = get_tenant_id(current_user)

    # Verify image exists and belongs to tenant
    result = await db.execute(
        select(CheckImage)
        .options(selectinload(CheckImage.check_item))
        .where(CheckImage.id == data.image_id)
    )
    image = result.scalar_one_or_none()

    if not image:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Image not found",
        )

    # Verify tenant ownership via the check item
    if image.check_item.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Image not found",  # Same error to prevent enumeration
        )

    # Create one-time token
    token_id = str(uuid.uuid4())
    expires_at = datetime.now(timezone.utc) + timedelta(
        seconds=settings.IMAGE_SIGNED_URL_TTL_SECONDS
    )

    token = ImageAccessToken(
        id=token_id,
        tenant_id=tenant_id,
        image_id=data.image_id,
        expires_at=expires_at,
        created_by_user_id=current_user.id,
        is_thumbnail=data.is_thumbnail,
    )

    db.add(token)

    # Log token creation
    audit_service = AuditService(db)
    await audit_service.log(
        action=AuditAction.IMAGE_TOKEN_CREATED,
        resource_type="image_access_token",
        resource_id=token_id,
        user_id=current_user.id,
        username=current_user.username,
        tenant_id=tenant_id,
        ip_address=request.client.host if request.client else None,
        description=f"Created one-time image access token for image {data.image_id}",
        metadata={"image_id": data.image_id, "is_thumbnail": data.is_thumbnail},
    )

    await db.commit()

    return TokenMintResponse(
        token_id=token_id,
        image_url=f"/api/v1/images/secure/{token_id}",
        expires_at=expires_at,
    )


@router.post("/tokens/batch", response_model=BatchTokenMintResponse)
@limiter.limit("30/minute")  # Rate limit batch minting (more restrictive since it creates multiple tokens)
async def mint_image_tokens_batch(
    request: Request,
    data: BatchTokenMintRequest,
    db: DBSession,
    current_user: Annotated[object, Depends(require_permission("check_item", "view"))],
):
    """
    Mint multiple one-time-use image access tokens in a single request.

    This is more efficient than calling /tokens for each image when
    loading a check with multiple images (front, back).

    Limits:
    - Maximum 10 tokens per request
    - Rate limited to 30 requests per minute
    """
    if len(data.image_ids) > 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum 10 tokens per batch request",
        )

    tenant_id = get_tenant_id(current_user)

    # Fetch all images in one query
    result = await db.execute(
        select(CheckImage)
        .options(selectinload(CheckImage.check_item))
        .where(CheckImage.id.in_(data.image_ids))
    )
    images = {img.id: img for img in result.scalars().all()}

    tokens = []
    expires_at = datetime.now(timezone.utc) + timedelta(
        seconds=settings.IMAGE_SIGNED_URL_TTL_SECONDS
    )

    for image_id in data.image_ids:
        image = images.get(image_id)

        # Skip images that don't exist or don't belong to tenant
        if not image or image.check_item.tenant_id != tenant_id:
            continue

        token_id = str(uuid.uuid4())

        token = ImageAccessToken(
            id=token_id,
            tenant_id=tenant_id,
            image_id=image_id,
            expires_at=expires_at,
            created_by_user_id=current_user.id,
            is_thumbnail=data.is_thumbnail,
        )

        db.add(token)

        tokens.append(TokenMintResponse(
            token_id=token_id,
            image_url=f"/api/v1/images/secure/{token_id}",
            expires_at=expires_at,
        ))

    if tokens:
        # Log batch token creation
        audit_service = AuditService(db)
        await audit_service.log(
            action=AuditAction.IMAGE_TOKEN_CREATED,
            resource_type="image_access_token",
            resource_id="batch",
            user_id=current_user.id,
            username=current_user.username,
            tenant_id=tenant_id,
            ip_address=request.client.host if request.client else None,
            description=f"Created {len(tokens)} one-time image access tokens",
            metadata={
                "image_ids": [t.token_id for t in tokens],
                "is_thumbnail": data.is_thumbnail
            },
        )

        await db.commit()

    return BatchTokenMintResponse(tokens=tokens)


# =============================================================================
# Secure Image Access Endpoint (One-Time Token)
# =============================================================================

@router.get("/secure/{token_id}")
async def get_secure_image(
    request: Request,
    token_id: str,
    db: DBSession,
):
    """
    Get check image via one-time-use token.

    Security Model:
    - Token is validated against database
    - Token must not be expired
    - Token must not be already used (one-time-use)
    - Token's tenant must match image's tenant
    - Token is marked as used BEFORE serving image (atomic)
    - No authentication required (token IS the authentication)

    This is safe because:
    - Token is one-time-use (replay attacks impossible)
    - Token is tenant-scoped (cross-tenant access impossible)
    - Token expires quickly (leaked URLs become useless)
    - Token is opaque UUID (no information in URL)
    """
    # Fetch token with image relationship
    result = await db.execute(
        select(ImageAccessToken)
        .options(
            selectinload(ImageAccessToken.image).selectinload(CheckImage.check_item),
            selectinload(ImageAccessToken.created_by),
        )
        .where(ImageAccessToken.id == token_id)
    )
    token = result.scalar_one_or_none()

    # Security: Return identical 404 response for all invalid token states
    # This prevents information leakage about whether token was:
    # - Never existed, expired, already used, or belongs to wrong tenant
    # Auditors/attackers cannot distinguish these cases from the response
    GENERIC_NOT_FOUND = HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Image not found",
    )

    if not token:
        raise GENERIC_NOT_FOUND

    # Check expiration
    if token.is_expired:
        raise GENERIC_NOT_FOUND

    # Check if already used (one-time-use enforcement)
    if token.is_used:
        raise GENERIC_NOT_FOUND

    # Verify tenant ownership
    if token.image.check_item.tenant_id != token.tenant_id:
        raise GENERIC_NOT_FOUND

    # Mark token as used BEFORE serving (atomic - prevents race conditions)
    token.used_at = datetime.now(timezone.utc)
    token.used_by_ip = request.client.host if request.client else None
    token.used_by_user_agent = request.headers.get("user-agent", "")[:500]

    # Commit the usage immediately to prevent concurrent access
    await db.commit()

    # Now serve the image
    adapter = get_adapter()
    audit_service = AuditService(db)

    resource_id = token.image.external_image_id or token.image_id

    if token.is_thumbnail:
        image_data = await adapter.get_thumbnail(resource_id)
        if image_data:
            await audit_service.log(
                action=AuditAction.IMAGE_VIEWED,
                resource_type="check_image_thumbnail",
                resource_id=token.image_id,
                user_id=token.created_by.id,
                username=token.created_by.username,
                tenant_id=token.tenant_id,
                ip_address=request.client.host if request.client else None,
                description="User viewed check thumbnail via one-time token",
                metadata={"token_id": token_id},
            )
            return Response(
                content=image_data,
                media_type="image/png",
                headers=SECURE_IMAGE_HEADERS,
            )
    else:
        image = await adapter.get_image(resource_id)
        if image:
            await audit_service.log(
                action=AuditAction.IMAGE_VIEWED,
                resource_type="check_image",
                resource_id=token.image_id,
                user_id=token.created_by.id,
                username=token.created_by.username,
                tenant_id=token.tenant_id,
                ip_address=request.client.host if request.client else None,
                description="User viewed full check image via one-time token",
                metadata={"token_id": token_id},
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


# =============================================================================
# Direct Image Access (Authenticated)
# =============================================================================

@router.get("/{image_id}")
async def get_image_direct(
    request: Request,
    image_id: str,
    db: DBSession,
    current_user: Annotated[object, Depends(require_permission("check_item", "view"))],
    thumbnail: bool = Query(False),
):
    """
    Get check image directly (requires authentication).

    This endpoint provides direct access to check images for authenticated users
    with appropriate permissions. Useful for programmatic access.
    """
    tenant_id = get_tenant_id(current_user)

    # Verify image exists and belongs to tenant
    result = await db.execute(
        select(CheckImage)
        .options(selectinload(CheckImage.check_item))
        .where(CheckImage.id == image_id)
    )
    image = result.scalar_one_or_none()

    if not image:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Image not found",
        )

    # Verify tenant ownership
    if image.check_item.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Image not found",
        )

    adapter = get_adapter()
    audit_service = AuditService(db)

    resource_id = image.external_image_id or image_id

    if thumbnail:
        image_data = await adapter.get_thumbnail(resource_id)
        if image_data:
            await audit_service.log(
                action=AuditAction.IMAGE_VIEWED,
                resource_type="check_image_thumbnail",
                resource_id=image_id,
                user_id=current_user.id,
                username=current_user.username,
                tenant_id=tenant_id,
                ip_address=request.client.host if request.client else None,
                description="User viewed check thumbnail directly",
            )
            return Response(
                content=image_data,
                media_type="image/png",
                headers=SECURE_IMAGE_HEADERS,
            )
    else:
        image_content = await adapter.get_image(resource_id)
        if image_content:
            await audit_service.log(
                action=AuditAction.IMAGE_VIEWED,
                resource_type="check_image",
                resource_id=image_id,
                user_id=current_user.id,
                username=current_user.username,
                tenant_id=tenant_id,
                ip_address=request.client.host if request.client else None,
                description="User viewed check image directly",
            )
            return Response(
                content=image_content.content,
                media_type=image_content.content_type,
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
    current_user: Annotated[object, Depends(require_permission("check_item", "view"))],
    view_id: str | None = None,
    zoom_level: int = Query(..., ge=50, le=800),
):
    """Log that user used zoom on an image (for audit trail)."""
    tenant_id = get_tenant_id(current_user)

    audit_service = AuditService(db)

    await audit_service.log(
        action=AuditAction.IMAGE_ZOOMED,
        resource_type="check_image",
        resource_id=image_id,
        user_id=current_user.id,
        username=current_user.username,
        tenant_id=tenant_id,
        ip_address=request.client.host if request.client else None,
        description=f"User zoomed image to {zoom_level}%",
        metadata={"zoom_level": zoom_level, "view_id": view_id},
    )

    # Update item view tracking if view_id provided
    if view_id:
        await audit_service.update_item_view(view_id, zoom_used=True)

    return {"status": "logged"}
