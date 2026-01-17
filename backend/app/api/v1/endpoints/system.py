"""
System status and demo mode endpoints.

These endpoints provide system information and demo mode controls.
"""

import os
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_superuser, get_db
from app.core.config import settings
from app.models.user import User


router = APIRouter()


class SystemStatusResponse(BaseModel):
    """System status response schema."""

    environment: str
    demo_mode_enabled: bool
    version: str
    build_commit: str | None
    database_type: str
    timestamp: datetime


class DemoModeResponse(BaseModel):
    """Demo mode status response schema."""

    enabled: bool
    environment: str
    safety_checks_passed: bool
    demo_data_count: int
    features: dict[str, bool]
    notices: list[str]


class DemoSeedRequest(BaseModel):
    """Request to seed demo data."""

    count: int = 60
    reset_existing: bool = False


class DemoSeedResponse(BaseModel):
    """Response after seeding demo data."""

    success: bool
    message: str
    items_created: dict[str, int]
    warnings: list[str]


@router.get("/status", response_model=SystemStatusResponse)
async def get_system_status() -> SystemStatusResponse:
    """
    Get system status information.

    Returns environment, demo mode status, version, and build information.
    This endpoint is public and does not require authentication.
    """
    # Try to get build commit from environment or git
    build_commit = os.environ.get("BUILD_COMMIT") or os.environ.get("GIT_COMMIT")

    return SystemStatusResponse(
        environment=settings.ENVIRONMENT,
        demo_mode_enabled=settings.DEMO_MODE,
        version=settings.APP_VERSION,
        build_commit=build_commit,
        database_type="postgresql",
        timestamp=datetime.now(timezone.utc),
    )


@router.get("/demo-mode", response_model=DemoModeResponse)
async def get_demo_mode_status() -> DemoModeResponse:
    """
    Get detailed demo mode status.

    Returns whether demo mode is enabled and what features are available.
    This endpoint is public to allow the frontend to configure itself.
    """
    # Safety checks
    safety_passed = True
    notices = []

    if settings.DEMO_MODE:
        if settings.ENVIRONMENT == "production":
            safety_passed = False
            notices.append("CRITICAL: Demo mode should NEVER be enabled in production!")
        else:
            notices.append("Demo mode is active - using synthetic data only")
            notices.append("No real PII or production data is being used")
            notices.append("All check images are watermarked as DEMO")
    else:
        notices.append("Demo mode is disabled - using real data sources")

    return DemoModeResponse(
        enabled=settings.DEMO_MODE,
        environment=settings.ENVIRONMENT,
        safety_checks_passed=safety_passed,
        demo_data_count=settings.DEMO_DATA_COUNT,
        features={
            "synthetic_checks": settings.DEMO_MODE,
            "mock_ai_analysis": settings.DEMO_MODE,
            "demo_images": settings.DEMO_MODE,
            "guided_tour": settings.DEMO_MODE,
            "sample_workflows": settings.DEMO_MODE,
        },
        notices=notices,
    )


@router.post("/demo/seed", response_model=DemoSeedResponse)
async def seed_demo_data(
    request: DemoSeedRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_superuser),
) -> DemoSeedResponse:
    """
    Seed the database with demo data.

    This endpoint is only available when DEMO_MODE is enabled and
    requires superuser authentication.

    - **count**: Number of check items to create (default: 60)
    - **reset_existing**: Whether to clear existing demo data first (default: false)
    """
    # Safety check: only allow in demo mode
    if not settings.DEMO_MODE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Demo data seeding is only available when DEMO_MODE is enabled",
        )

    # Safety check: never in production
    if settings.ENVIRONMENT == "production":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Demo data seeding is not allowed in production environment",
        )

    try:
        from app.demo.seed import DemoSeeder

        seeder = DemoSeeder(db)
        warnings = []

        # Reset if requested
        if request.reset_existing:
            await seeder.clear_demo_data()
            warnings.append("Existing demo data was cleared")

        # Seed data
        await seeder.seed_all(count=request.count)

        return DemoSeedResponse(
            success=True,
            message=f"Successfully seeded {request.count} demo check items",
            items_created={
                "users": 3,  # reviewer, approver, admin
                "queues": 4,
                "check_items": request.count,
                "decisions": request.count // 3,  # ~1/3 have decisions
                "audit_events": request.count * 2,  # ~2 per item
            },
            warnings=warnings,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to seed demo data: {str(e)}",
        )


@router.post("/demo/reset")
async def reset_demo_data(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_superuser),
) -> dict[str, Any]:
    """
    Clear all demo data from the database.

    This endpoint is only available when DEMO_MODE is enabled and
    requires superuser authentication. It removes all records marked
    with is_demo=True.
    """
    # Safety check: only allow in demo mode
    if not settings.DEMO_MODE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Demo data reset is only available when DEMO_MODE is enabled",
        )

    # Safety check: never in production
    if settings.ENVIRONMENT == "production":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Demo data reset is not allowed in production environment",
        )

    try:
        from app.demo.seed import DemoSeeder

        seeder = DemoSeeder(db)
        await seeder.clear_demo_data()

        return {
            "success": True,
            "message": "All demo data has been cleared",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to reset demo data: {str(e)}",
        )


@router.get("/demo/credentials")
async def get_demo_credentials() -> dict[str, Any]:
    """
    Get demo user credentials for testing.

    This endpoint only returns credentials when DEMO_MODE is enabled.
    These are synthetic credentials for demonstration purposes only.
    """
    if not settings.DEMO_MODE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Demo credentials are only available when DEMO_MODE is enabled",
        )

    from app.demo.scenarios import DEMO_CREDENTIALS

    return {
        "notice": "These are DEMO credentials for demonstration purposes only",
        "credentials": [
            {
                "username": cred["username"],
                "password": cred["password"],
                "role": cred["role"],
                "description": cred["description"],
            }
            for cred in DEMO_CREDENTIALS.values()
        ],
        "warning": "Do NOT use these credentials in any real environment",
    }
