"""
System status and demo mode endpoints.

These endpoints provide system information and demo mode controls.
"""

import os
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, select

from app.api.deps import DBSession, get_current_active_superuser
from app.core.config import settings
from app.models.check import CheckItem
from app.models.user import User

router = APIRouter()


async def _run_reseed(count: int) -> None:
    """Recreate the schema and reseed. Runs as a background task so the
    triggering request's DB session is torn down first, freeing the locks that
    DROP SCHEMA needs."""
    from app.demo.seed import seed_demo_data as _seed

    await _seed(reset=True, count=count)


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
    # Actual number of check items currently in the database. Unlike
    # ``demo_data_count`` (the configured target), this reflects reality after a
    # reseed, so the Admin panel can show what was really generated.
    live_item_count: int | None = None
    features: dict[str, bool]
    notices: list[str]


class DemoSeedRequest(BaseModel):
    """Request to seed demo data."""

    count: int = 250
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
async def get_demo_mode_status(db: DBSession) -> DemoModeResponse:
    """
    Get detailed demo mode status.

    Returns whether demo mode is enabled and what features are available.
    This endpoint is public to allow the frontend to configure itself.
    """
    # Safety checks
    safety_passed = True
    notices = []

    # Live count of actual check items so the Admin panel reflects what a reseed
    # really produced (not just the configured target).
    live_item_count: int | None = None
    if settings.DEMO_MODE:
        try:
            count_result = await db.execute(select(func.count(CheckItem.id)))
            live_item_count = count_result.scalar() or 0
        except Exception:
            live_item_count = None

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
        live_item_count=live_item_count,
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
    background_tasks: BackgroundTasks,
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
        from app.demo.seed import seed_demo_data as _seed

        # A reset recreates the schema, which must run *after* this request's DB
        # session is released (DROP SCHEMA needs an exclusive lock). Schedule it
        # as a background task and return immediately.
        if request.reset_existing:
            background_tasks.add_task(_run_reseed, request.count)
            return DemoSeedResponse(
                success=True,
                message=(
                    "Reseed started: recreating the schema and regenerating demo data. "
                    "This takes ~15-20 seconds; the page will refresh when it is ready."
                ),
                items_created={},
                warnings=["Reseed runs in the background."],
            )

        # Non-reset seed is idempotent and fast; run inline.
        stats = await _seed(reset=False, count=request.count)
        return DemoSeedResponse(
            success=True,
            message=f"Seeded demo data ({stats.get('check_items', 0)} check items)",
            items_created={
                "users": stats.get("users", 0),
                "queues": stats.get("queues", 0),
                "check_items": stats.get("check_items", 0),
                "decisions": stats.get("decisions", 0),
                "audit_events": stats.get("audit_events", 0),
            },
            warnings=[],
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to seed demo data: {str(e)}",
        )


@router.post("/demo/reset")
async def reset_demo_data(
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_superuser),
) -> dict[str, Any]:
    """
    Reset the demo environment to a clean, freshly-seeded state.

    This endpoint is only available when DEMO_MODE is enabled and requires
    superuser authentication. It recreates the database schema and reseeds the
    default demo dataset (rather than leaving an empty database, which would
    lock everyone out).
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
        background_tasks.add_task(_run_reseed, settings.DEMO_DATA_COUNT)

        return {
            "success": True,
            "message": (
                "Reseed started: recreating the schema and regenerating demo data (~15-20s)."
            ),
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
    from app.demo import SECURE_ENVIRONMENTS

    # Defense in depth: this endpoint is unauthenticated (the login screen calls
    # it before sign-in), so it must refuse to serve credentials both when demo
    # mode is off AND whenever running in an environment that may hold real data
    # - even if DEMO_MODE was misconfigured to true there.
    if not settings.DEMO_MODE or settings.ENVIRONMENT.lower() in SECURE_ENVIRONMENTS:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Demo credentials are only available in a non-production demo environment",
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
