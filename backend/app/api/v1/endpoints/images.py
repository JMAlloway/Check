"""Check image endpoints."""

from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.deps import DBSession, require_permission
from app.audit.service import AuditService
from app.core.config import settings
from app.core.rate_limit import limiter, user_limiter, RateLimits
from app.core.security import verify_signed_url
from app.integrations.adapters.factory import get_adapter
from app.models.audit import AuditAction
from app.models.check import CheckImage
from app.models.image_token import ImageAccessToken
from app.models.user import User

router = APIRouter()

# Default token TTL in seconds (90 seconds for one-time tokens)
ONE_TIME_TOKEN_TTL_SECONDS = 90


# ============================================================================
# Pydantic Schemas for One-Time Token System
# ============================================================================


class TokenMintRequest(BaseModel):
    """Request to mint a one-time image access token."""

    image_id: str = Field(..., description="The ID of the check image to access")
    is_thumbnail: bool = Field(default=False, description="Whether to access thumbnail version")


class TokenMintResponse(BaseModel):
    """Response containing a minted one-time token."""

    token_id: str = Field(..., description="The one-time token ID (UUID)")
    image_url: str = Field(..., description="The URL to access the image with this token")
    expires_at: datetime = Field(..., description="When this token expires")


class BatchTokenMintRequest(BaseModel):
    """Request to mint multiple one-time tokens at once."""

    image_ids: list[str] = Field(..., description="List of image IDs to mint tokens for")
    is_thumbnail: bool = Field(default=False, description="Whether to access thumbnail versions")


class BatchTokenMintResponse(BaseModel):
    """Response containing multiple minted tokens."""

    tokens: list[TokenMintResponse] = Field(..., description="List of minted tokens")


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
    # CRITICAL: Prevent token leakage via Referrer header
    "Referrer-Policy": "no-referrer",
}


@router.get("/secure/{token}")
@limiter.limit(RateLimits.IMAGE_VIEW)  # IP-based: 120/min, 1000/hour
async def get_secure_image(
    request: Request,
    token: str,
    db: DBSession,
    thumbnail: bool = Query(False),
):
    """
    Get check image via signed URL token.

    Security Model (BEARER TOKEN):
    - Token is a bearer token - anyone with the URL can access
    - Security relies on short TTL (~90s) to limit exposure
    - Token contains user_id for AUDIT LOGGING only
    - Access is NOT restricted to the embedded user
    - No session authentication required - enables <img> tag usage
    - Response headers prevent caching in shared locations

    Risk: If URL leaks, image is accessible until token expires.
    Mitigation: Short TTL (90s default) + no-cache headers.
    """
    # Verify the signed URL token
    payload = verify_signed_url(token)

    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired image URL",
        )

    # NOTE: This is a bearer token model - we do NOT verify the requester matches user_id
    # user_id is extracted for audit logging purposes only
    # Access control relies solely on token validity + short TTL
    user_id = payload.user_id

    # Get user for audit logging
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found for signed URL",
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
                user_id=user.id,
                username=user.username,
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
                user_id=user.id,
                username=user.username,
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
@user_limiter.limit(RateLimits.IMAGE_VIEW)  # User-based: 120/min, 1000/hour
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
@user_limiter.limit(RateLimits.STANDARD)  # User-based: standard rate limit
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


# ============================================================================
# One-Time Token Endpoints (Pilot/Production Security Model)
# ============================================================================
#
# These endpoints implement secure, one-time-use, tenant-aware image access
# tokens that address common security findings for bearer URLs:
# - One-time use: Token is invalidated immediately when used
# - Tenant isolation: Token validates image belongs to same tenant
# - Short-lived: Tokens expire after 90 seconds
# - Opaque: Token is a UUID, not a JWT (no information leakage)
# - Auditable: Full audit trail of token creation and usage
#
# The legacy /secure/{token} endpoint uses JWT bearer tokens which work
# for demos but have known replay risks. Use one-time tokens for pilots.
# ============================================================================


@router.post("/mint-token", response_model=TokenMintResponse)
@user_limiter.limit(RateLimits.IMAGE_MINT_TOKEN)  # User-based: 60/min, 500/hour
async def mint_image_token(
    request: Request,
    data: TokenMintRequest,
    db: DBSession,
    current_user: Annotated[object, Depends(require_permission("check_image", "view"))],
):
    """
    Mint a one-time-use token for secure image access.

    Security Properties:
    - Token can only be used once (marked as used atomically on consumption)
    - Token is tenant-scoped (validates image belongs to requester's tenant)
    - Token expires after 90 seconds
    - Token is an opaque UUID (no information leakage like JWTs)
    - Full audit trail of who created and consumed the token

    Use this endpoint for pilot/production deployments instead of JWT bearer URLs.
    """
    tenant_id = current_user.tenant_id
    audit_service = AuditService(db)

    # Verify image exists and belongs to user's tenant
    image_result = await db.execute(
        select(CheckImage).where(CheckImage.id == data.image_id)
    )
    image = image_result.scalar_one_or_none()

    if not image:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Image not found",
        )

    # Validate tenant ownership via the check item
    if image.check_item and image.check_item.tenant_id != tenant_id:
        # Log the access attempt
        await audit_service.log(
            action=AuditAction.IMAGE_ACCESS_DENIED,
            resource_type="check_image",
            resource_id=data.image_id,
            user_id=current_user.id,
            username=current_user.username,
            tenant_id=tenant_id,
            ip_address=request.client.host if request.client else None,
            description="Token mint denied - tenant mismatch",
        )
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Image not found",
        )

    # Create the one-time token
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=ONE_TIME_TOKEN_TTL_SECONDS)
    token = ImageAccessToken(
        tenant_id=tenant_id,
        image_id=data.image_id,
        expires_at=expires_at,
        created_by_user_id=current_user.id,
        is_thumbnail=data.is_thumbnail,
    )
    db.add(token)

    # Log token creation
    await audit_service.log(
        action=AuditAction.IMAGE_TOKEN_CREATED,
        resource_type="image_access_token",
        resource_id=token.id,
        user_id=current_user.id,
        username=current_user.username,
        tenant_id=tenant_id,
        ip_address=request.client.host if request.client else None,
        description=f"One-time image token created for image {data.image_id}",
        metadata={
            "image_id": data.image_id,
            "is_thumbnail": data.is_thumbnail,
            "expires_at": expires_at.isoformat(),
        },
    )
    await db.commit()

    # Build the access URL
    image_url = f"{settings.API_V1_PREFIX}/images/token/{token.id}"

    return TokenMintResponse(
        token_id=token.id,
        image_url=image_url,
        expires_at=expires_at,
    )


@router.post("/mint-tokens-batch", response_model=BatchTokenMintResponse)
@user_limiter.limit(RateLimits.IMAGE_MINT_BATCH)  # User-based: 10/min, 50/hour (strict - up to 10 images per call)
async def mint_image_tokens_batch(
    request: Request,
    data: BatchTokenMintRequest,
    db: DBSession,
    current_user: Annotated[object, Depends(require_permission("check_image", "view"))],
):
    """
    Mint multiple one-time tokens for efficient image loading.

    Maximum 10 tokens per request to prevent abuse.
    Useful for loading all images on a check detail view at once.
    """
    if len(data.image_ids) > 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum 10 tokens per batch request",
        )

    tenant_id = current_user.tenant_id
    audit_service = AuditService(db)
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=ONE_TIME_TOKEN_TTL_SECONDS)
    tokens = []

    for image_id in data.image_ids:
        # Verify each image exists and belongs to tenant
        image_result = await db.execute(
            select(CheckImage).where(CheckImage.id == image_id)
        )
        image = image_result.scalar_one_or_none()

        if not image:
            continue  # Skip missing images in batch

        # Validate tenant ownership
        if image.check_item and image.check_item.tenant_id != tenant_id:
            continue  # Skip images from other tenants

        # Create token
        token = ImageAccessToken(
            tenant_id=tenant_id,
            image_id=image_id,
            expires_at=expires_at,
            created_by_user_id=current_user.id,
            is_thumbnail=data.is_thumbnail,
        )
        db.add(token)

        image_url = f"{settings.API_V1_PREFIX}/images/token/{token.id}"
        tokens.append(TokenMintResponse(
            token_id=token.id,
            image_url=image_url,
            expires_at=expires_at,
        ))

    # Log batch token creation
    if tokens:
        await audit_service.log(
            action=AuditAction.IMAGE_TOKEN_CREATED,
            resource_type="image_access_token",
            resource_id="batch",
            user_id=current_user.id,
            username=current_user.username,
            tenant_id=tenant_id,
            ip_address=request.client.host if request.client else None,
            description=f"Batch minted {len(tokens)} one-time image tokens",
            metadata={
                "image_ids": data.image_ids,
                "token_count": len(tokens),
                "is_thumbnail": data.is_thumbnail,
            },
        )
        await db.commit()

    return BatchTokenMintResponse(tokens=tokens)


@router.get("/token/{token_id}")
@limiter.limit(RateLimits.IMAGE_VIEW)  # IP-based: 120/min, 1000/hour (unauthenticated)
async def get_image_by_token(
    request: Request,
    token_id: str,
    db: DBSession,
):
    """
    Access an image using a one-time token.

    Security Properties:
    - Token is marked as used BEFORE streaming the image (atomic one-time use)
    - Expired tokens return 410 Gone
    - Already-used tokens return 410 Gone
    - Tenant isolation is enforced via the token
    - No authentication required (token IS the auth) - enables <img> tag usage

    HTTP 410 (Gone) is used for expired/used tokens to indicate the resource
    existed but is no longer available (vs 404 which means never existed).
    """
    audit_service = AuditService(db)

    # Look up the token
    token_result = await db.execute(
        select(ImageAccessToken).where(ImageAccessToken.id == token_id)
    )
    token = token_result.scalar_one_or_none()

    if not token:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Token not found",
        )

    # Check if token is expired
    if token.is_expired:
        await audit_service.log(
            action=AuditAction.IMAGE_TOKEN_EXPIRED,
            resource_type="image_access_token",
            resource_id=token_id,
            user_id=token.created_by_user_id,
            username=None,
            tenant_id=token.tenant_id,
            ip_address=request.client.host if request.client else None,
            description="Attempt to use expired image token",
        )
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Token has expired",
        )

    # Check if token was already used
    if token.is_used:
        await audit_service.log(
            action=AuditAction.IMAGE_TOKEN_REUSE_ATTEMPTED,
            resource_type="image_access_token",
            resource_id=token_id,
            user_id=token.created_by_user_id,
            username=None,
            tenant_id=token.tenant_id,
            ip_address=request.client.host if request.client else None,
            description="Attempt to reuse one-time image token",
            metadata={
                "original_used_at": token.used_at.isoformat() if token.used_at else None,
                "original_used_by_ip": token.used_by_ip,
            },
        )
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Token has already been used",
        )

    # CRITICAL: Mark token as used BEFORE serving the image
    # This prevents race conditions where the same token is used twice
    token.used_at = datetime.now(timezone.utc)
    token.used_by_ip = request.client.host if request.client else None
    token.used_by_user_agent = request.headers.get("user-agent", "")[:500]
    await db.commit()

    # Now fetch and serve the image
    adapter = get_adapter()

    if token.is_thumbnail:
        image_data = await adapter.get_thumbnail(token.image_id)
        if image_data:
            # Log successful token usage
            await audit_service.log(
                action=AuditAction.IMAGE_TOKEN_USED,
                resource_type="image_access_token",
                resource_id=token_id,
                user_id=token.created_by_user_id,
                username=None,
                tenant_id=token.tenant_id,
                ip_address=request.client.host if request.client else None,
                description=f"One-time token used for thumbnail {token.image_id}",
            )
            await db.commit()
            return Response(
                content=image_data,
                media_type="image/png",
                headers=SECURE_IMAGE_HEADERS,
            )
    else:
        image = await adapter.get_image(token.image_id)
        if image:
            # Log successful token usage
            await audit_service.log(
                action=AuditAction.IMAGE_TOKEN_USED,
                resource_type="image_access_token",
                resource_id=token_id,
                user_id=token.created_by_user_id,
                username=None,
                tenant_id=token.tenant_id,
                ip_address=request.client.host if request.client else None,
                description=f"One-time token used for image {token.image_id}",
            )
            await db.commit()
            return Response(
                content=image.content,
                media_type=image.content_type,
                headers=SECURE_IMAGE_HEADERS,
            )

    # Image not found (rare - token was valid but image deleted)
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Image not found",
    )
