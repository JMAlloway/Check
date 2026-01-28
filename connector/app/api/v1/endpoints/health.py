"""
Health check endpoint.

Returns connector status, mode, version, and component health.
No authentication required for health checks.
"""
from fastapi import APIRouter, Depends

from ....core.config import get_settings
from ....core.security import get_path_validator
from ....models import CacheStats, ComponentHealth, HealthResponse
from ....services import get_image_service
from ...deps import get_correlation_id

router = APIRouter()


@router.get(
    "/healthz",
    response_model=HealthResponse,
    summary="Health Check",
    description="Returns connector health status, mode, version, and component status.",
    responses={
        200: {"description": "Health check successful"},
        503: {"description": "Service unavailable (degraded health)"}
    }
)
async def health_check(
    correlation_id: str = Depends(get_correlation_id)
) -> HealthResponse:
    """
    Get connector health status.

    Returns:
    - Overall status (healthy/degraded)
    - Connector mode (DEMO/BANK)
    - Connector version
    - Connector ID
    - Component health (resolver, storage, decoder)
    - Cache statistics
    - Allowed share roots
    """
    settings = get_settings()
    image_service = get_image_service()
    path_validator = get_path_validator()

    # Get component health
    all_healthy, component_status = await image_service.health_check()

    # Build response
    components = {
        "resolver": ComponentHealth(
            healthy=component_status["resolver"]["healthy"],
            message=component_status["resolver"]["message"]
        ),
        "storage": ComponentHealth(
            healthy=component_status["storage"]["healthy"],
            message=component_status["storage"]["message"]
        ),
        "decoder": ComponentHealth(
            healthy=component_status["decoder"]["healthy"],
            message=component_status["decoder"]["message"]
        )
    }

    cache_data = component_status["cache"]
    cache_stats = CacheStats(
        items=cache_data["items"],
        bytes=cache_data["bytes"],
        max_items=cache_data["max_items"],
        max_bytes=cache_data["max_bytes"],
        ttl_seconds=cache_data["ttl_seconds"],
        cache_hits=cache_data["cache_hits"],
        cache_misses=cache_data["cache_misses"],
        hit_rate=cache_data["hit_rate"]
    )

    return HealthResponse(
        status="healthy" if all_healthy else "degraded",
        mode=settings.MODE.value,
        version=settings.CONNECTOR_VERSION,
        connector_id=settings.CONNECTOR_ID,
        components=components,
        cache=cache_stats,
        allowed_roots=path_validator.get_allowed_roots()
    )
