"""API v1 module."""
from fastapi import APIRouter

from .endpoints import health, images, items

router = APIRouter()

# Include all endpoint routers
router.include_router(health.router, tags=["Health"])
router.include_router(images.router, prefix="/images", tags=["Images"])
router.include_router(items.router, prefix="/items", tags=["Items"])
