"""
Pydantic schemas for API requests and responses.
"""
from datetime import date
from enum import Enum
from typing import Optional, Dict, Any, List

from pydantic import BaseModel, Field


class ImageSideParam(str, Enum):
    """Query parameter for image side."""
    FRONT = "front"
    BACK = "back"


class ErrorCode(str, Enum):
    """Standard error codes."""
    AUTH_FAILED = "AUTH_FAILED"
    FORBIDDEN = "FORBIDDEN"
    PATH_NOT_ALLOWED = "PATH_NOT_ALLOWED"
    NOT_FOUND = "NOT_FOUND"
    NO_BACK_IMAGE = "NO_BACK_IMAGE"
    UNSUPPORTED_FORMAT = "UNSUPPORTED_FORMAT"
    IMAGE_DECODE_FAILED = "IMAGE_DECODE_FAILED"
    UPSTREAM_IO_ERROR = "UPSTREAM_IO_ERROR"
    RATE_LIMITED = "RATE_LIMITED"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class ErrorResponse(BaseModel):
    """Standard error response."""
    error_code: str = Field(..., description="Machine-readable error code")
    message: str = Field(..., description="Human-readable error message")
    correlation_id: str = Field(..., description="Request correlation ID for tracing")

    class Config:
        json_schema_extra = {
            "example": {
                "error_code": "NOT_FOUND",
                "message": "Image not found at the specified path",
                "correlation_id": "550e8400-e29b-41d4-a716-446655440000"
            }
        }


class ComponentHealth(BaseModel):
    """Health status of a single component."""
    healthy: bool = Field(..., description="Whether the component is healthy")
    message: str = Field(..., description="Status message")


class CacheStats(BaseModel):
    """Cache statistics."""
    items: int = Field(..., description="Number of cached items")
    bytes: int = Field(..., description="Total bytes cached")
    max_items: int = Field(..., description="Maximum items allowed")
    max_bytes: int = Field(..., description="Maximum bytes allowed")
    ttl_seconds: int = Field(..., description="Cache TTL in seconds")
    cache_hits: int = Field(..., description="Total cache hits")
    cache_misses: int = Field(..., description="Total cache misses")
    hit_rate: float = Field(..., description="Cache hit rate (0-1)")


class HealthResponse(BaseModel):
    """Health check response."""
    status: str = Field(..., description="Overall status: 'healthy' or 'degraded'")
    mode: str = Field(..., description="Connector mode: 'DEMO' or 'BANK'")
    version: str = Field(..., description="Connector version")
    connector_id: str = Field(..., description="Unique connector identifier")
    components: Dict[str, ComponentHealth] = Field(
        ..., description="Health status of individual components"
    )
    cache: CacheStats = Field(..., description="Cache statistics")
    allowed_roots: List[str] = Field(
        ..., description="Allowed UNC share roots"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "status": "healthy",
                "mode": "DEMO",
                "version": "1.0.0",
                "connector_id": "connector-demo-001",
                "components": {
                    "resolver": {"healthy": True, "message": "Demo resolver ready with 5 items"},
                    "storage": {"healthy": True, "message": "Demo storage accessible"},
                    "decoder": {"healthy": True, "message": "Image decoder operational"}
                },
                "cache": {
                    "items": 0,
                    "bytes": 0,
                    "max_items": 100,
                    "max_bytes": 104857600,
                    "ttl_seconds": 60,
                    "cache_hits": 0,
                    "cache_misses": 0,
                    "hit_rate": 0.0
                },
                "allowed_roots": [
                    "\\\\tn-director-pro\\Checks\\Transit\\",
                    "\\\\tn-director-pro\\Checks\\OnUs\\"
                ]
            }
        }


class ItemLookupResponse(BaseModel):
    """Item lookup response with masked data."""
    trace_number: str = Field(..., description="Check trace number")
    check_date: str = Field(..., description="Check date (YYYY-MM-DD)")
    amount_cents: int = Field(..., description="Check amount in cents")
    check_number: Optional[str] = Field(None, description="Check number")
    account_last4: str = Field(..., description="Last 4 digits of account number")
    is_onus: bool = Field(..., description="True if ONUS, False if Transit")
    has_back_image: bool = Field(..., description="Whether back image exists")

    class Config:
        json_schema_extra = {
            "example": {
                "trace_number": "12374628",
                "check_date": "2024-01-15",
                "amount_cents": 125000,
                "check_number": "1234",
                "account_last4": "5678",
                "is_onus": False,
                "has_back_image": True
            }
        }
