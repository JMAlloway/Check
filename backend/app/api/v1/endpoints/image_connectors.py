"""
Image Connector Management Endpoints.

Admin endpoints for managing bank-side image connectors.
"""
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import (
    get_db,
    get_current_active_user,
    require_permission,
)
from app.models.user import User
from app.models.image_connector import ImageConnector, ConnectorStatus
from app.services.image_connector_service import (
    ImageConnectorService,
    ConnectorNotFoundError,
    generate_key_pair,
)

router = APIRouter()


# =============================================================================
# Request/Response Schemas
# =============================================================================

class ConnectorCreate(BaseModel):
    """Request to create a new connector."""
    connector_id: str = Field(..., min_length=1, max_length=100)
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    base_url: str = Field(..., min_length=1, max_length=500)
    public_key_pem: str = Field(..., min_length=100)
    token_expiry_seconds: int = Field(default=120, ge=60, le=300)

    class Config:
        json_schema_extra = {
            "example": {
                "connector_id": "connector-prod-001",
                "name": "Primary DC Connector",
                "description": "Production connector in primary data center",
                "base_url": "https://connector.bank.local:8443",
                "public_key_pem": "-----BEGIN PUBLIC KEY-----\n...\n-----END PUBLIC KEY-----",
                "token_expiry_seconds": 120
            }
        }


class ConnectorUpdate(BaseModel):
    """Request to update a connector."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    base_url: Optional[str] = Field(None, min_length=1, max_length=500)
    token_expiry_seconds: Optional[int] = Field(None, ge=60, le=300)
    timeout_seconds: Optional[int] = Field(None, ge=5, le=120)
    max_retries: Optional[int] = Field(None, ge=0, le=5)
    priority: Optional[int] = Field(None, ge=0, le=1000)


class KeyRotateRequest(BaseModel):
    """Request to rotate connector public key."""
    new_public_key_pem: str = Field(..., min_length=100)
    overlap_hours: int = Field(default=24, ge=1, le=168)


class ConnectorResponse(BaseModel):
    """Connector details response."""
    id: str
    connector_id: str
    name: str
    description: Optional[str]
    base_url: str
    status: str
    is_enabled: bool
    public_key_id: str
    public_key_expires_at: Optional[datetime]
    secondary_public_key_id: Optional[str]
    secondary_public_key_expires_at: Optional[datetime]
    token_expiry_seconds: int
    connector_version: Optional[str]
    connector_mode: Optional[str]
    allowed_roots: Optional[List[str]]
    last_health_check_at: Optional[datetime]
    last_health_check_status: Optional[str]
    last_health_check_latency_ms: Optional[int]
    health_check_failure_count: int
    last_successful_request_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class HealthCheckResponse(BaseModel):
    """Health check test response."""
    success: bool
    latency_ms: int
    error: Optional[str] = None
    data: Optional[dict] = None


class KeyPairResponse(BaseModel):
    """Generated key pair response."""
    private_key_pem: str
    public_key_pem: str


# =============================================================================
# Helper Functions
# =============================================================================

def _connector_to_response(connector: ImageConnector) -> ConnectorResponse:
    """Convert connector model to response."""
    return ConnectorResponse(
        id=connector.id,
        connector_id=connector.connector_id,
        name=connector.name,
        description=connector.description,
        base_url=connector.base_url,
        status=connector.status.value,
        is_enabled=connector.is_enabled,
        public_key_id=connector.public_key_id,
        public_key_expires_at=connector.public_key_expires_at,
        secondary_public_key_id=connector.secondary_public_key_id,
        secondary_public_key_expires_at=connector.secondary_public_key_expires_at,
        token_expiry_seconds=connector.token_expiry_seconds,
        connector_version=connector.connector_version,
        connector_mode=connector.connector_mode,
        allowed_roots=connector.allowed_roots,
        last_health_check_at=connector.last_health_check_at,
        last_health_check_status=connector.last_health_check_status,
        last_health_check_latency_ms=connector.last_health_check_latency_ms,
        health_check_failure_count=connector.health_check_failure_count,
        last_successful_request_at=connector.last_successful_request_at,
        created_at=connector.created_at,
        updated_at=connector.updated_at
    )


# =============================================================================
# Endpoints
# =============================================================================

@router.get(
    "/",
    response_model=List[ConnectorResponse],
    summary="List Image Connectors",
    description="List all image connectors for the current tenant.",
)
async def list_connectors(
    enabled_only: bool = Query(False, description="Only return enabled connectors"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("image_connector", "view")),
) -> List[ConnectorResponse]:
    """List all image connectors."""
    service = ImageConnectorService(db)
    connectors = await service.list_connectors(
        tenant_id=current_user.tenant_id,
        enabled_only=enabled_only
    )
    return [_connector_to_response(c) for c in connectors]


@router.post(
    "/",
    response_model=ConnectorResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Image Connector",
    description="Create a new bank-side image connector.",
)
async def create_connector(
    request: ConnectorCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("image_connector", "create")),
) -> ConnectorResponse:
    """Create a new image connector."""
    service = ImageConnectorService(db)

    # Check if connector ID already exists
    existing = await service.get_connector(
        tenant_id=current_user.tenant_id,
        connector_id=request.connector_id
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Connector with ID '{request.connector_id}' already exists"
        )

    connector = await service.create_connector(
        tenant_id=current_user.tenant_id,
        connector_id=request.connector_id,
        name=request.name,
        description=request.description,
        base_url=request.base_url,
        public_key_pem=request.public_key_pem,
        token_expiry_seconds=request.token_expiry_seconds,
        created_by_user_id=current_user.id,
    )

    await db.commit()
    return _connector_to_response(connector)


@router.get(
    "/{connector_id}",
    response_model=ConnectorResponse,
    summary="Get Image Connector",
    description="Get details of a specific image connector.",
)
async def get_connector(
    connector_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("image_connector", "view")),
) -> ConnectorResponse:
    """Get a specific image connector."""
    service = ImageConnectorService(db)
    connector = await service.get_connector(
        tenant_id=current_user.tenant_id,
        connector_id=connector_id
    )

    if not connector:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Connector '{connector_id}' not found"
        )

    return _connector_to_response(connector)


@router.patch(
    "/{connector_id}",
    response_model=ConnectorResponse,
    summary="Update Image Connector",
    description="Update an existing image connector.",
)
async def update_connector(
    connector_id: str,
    request: ConnectorUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("image_connector", "update")),
) -> ConnectorResponse:
    """Update an image connector."""
    service = ImageConnectorService(db)

    try:
        updates = request.model_dump(exclude_unset=True)
        connector = await service.update_connector(
            tenant_id=current_user.tenant_id,
            connector_id=connector_id,
            user_id=current_user.id,
            **updates
        )
        await db.commit()
        return _connector_to_response(connector)

    except ConnectorNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Connector '{connector_id}' not found"
        )


@router.post(
    "/{connector_id}/enable",
    response_model=ConnectorResponse,
    summary="Enable Image Connector",
    description="Enable an image connector to accept requests.",
)
async def enable_connector(
    connector_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("image_connector", "update")),
) -> ConnectorResponse:
    """Enable an image connector."""
    service = ImageConnectorService(db)

    try:
        connector = await service.enable_connector(
            tenant_id=current_user.tenant_id,
            connector_id=connector_id,
            user_id=current_user.id
        )
        await db.commit()
        return _connector_to_response(connector)

    except ConnectorNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Connector '{connector_id}' not found"
        )


@router.post(
    "/{connector_id}/disable",
    response_model=ConnectorResponse,
    summary="Disable Image Connector",
    description="Disable an image connector to stop accepting requests.",
)
async def disable_connector(
    connector_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("image_connector", "update")),
) -> ConnectorResponse:
    """Disable an image connector."""
    service = ImageConnectorService(db)

    try:
        connector = await service.disable_connector(
            tenant_id=current_user.tenant_id,
            connector_id=connector_id,
            user_id=current_user.id
        )
        await db.commit()
        return _connector_to_response(connector)

    except ConnectorNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Connector '{connector_id}' not found"
        )


@router.delete(
    "/{connector_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Image Connector",
    description="Delete an image connector.",
)
async def delete_connector(
    connector_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("image_connector", "delete")),
):
    """Delete an image connector."""
    service = ImageConnectorService(db)

    try:
        await service.delete_connector(
            tenant_id=current_user.tenant_id,
            connector_id=connector_id,
            user_id=current_user.id
        )
        await db.commit()

    except ConnectorNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Connector '{connector_id}' not found"
        )


@router.post(
    "/{connector_id}/test",
    response_model=HealthCheckResponse,
    summary="Test Connector Connection",
    description="Test connection to an image connector by calling its health endpoint.",
)
async def test_connector(
    connector_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("image_connector", "view")),
) -> HealthCheckResponse:
    """Test connection to an image connector."""
    service = ImageConnectorService(db)

    try:
        result = await service.test_connection(
            tenant_id=current_user.tenant_id,
            connector_id=connector_id,
            user_id=current_user.id
        )
        await db.commit()
        return HealthCheckResponse(**result)

    except ConnectorNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Connector '{connector_id}' not found"
        )


@router.post(
    "/{connector_id}/rotate-key",
    response_model=ConnectorResponse,
    summary="Rotate Public Key",
    description="Rotate the public key for an image connector with overlap period.",
)
async def rotate_key(
    connector_id: str,
    request: KeyRotateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("image_connector", "update")),
) -> ConnectorResponse:
    """Rotate the public key for a connector."""
    service = ImageConnectorService(db)

    try:
        connector = await service.rotate_public_key(
            tenant_id=current_user.tenant_id,
            connector_id=connector_id,
            new_public_key_pem=request.new_public_key_pem,
            user_id=current_user.id,
            overlap_hours=request.overlap_hours
        )
        await db.commit()
        return _connector_to_response(connector)

    except ConnectorNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Connector '{connector_id}' not found"
        )


@router.post(
    "/generate-keypair",
    response_model=KeyPairResponse,
    summary="Generate Key Pair",
    description="Generate a new RSA key pair for connector authentication.",
)
async def generate_keypair(
    current_user: User = Depends(require_permission("image_connector", "create")),
) -> KeyPairResponse:
    """
    Generate a new RSA key pair.

    Returns both private and public keys. The private key should be
    securely stored and configured on the connector. The public key
    is used when creating or updating the connector in the SaaS.
    """
    private_key, public_key = generate_key_pair()
    return KeyPairResponse(
        private_key_pem=private_key,
        public_key_pem=public_key
    )
