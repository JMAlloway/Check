"""Main FastAPI application."""

from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1 import api_router
from app.core.config import settings
from app.db.session import engine, Base
from app.schemas.common import HealthResponse

# Import all models so they're registered with Base.metadata
from app.models import user, check, decision, policy, queue, audit, fraud, connector  # noqa: F401


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management."""
    # Startup
    print(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    print(f"Environment: {settings.ENVIRONMENT}")

    # CRITICAL SAFETY CHECK: Demo mode must NEVER run in production
    if settings.DEMO_MODE and settings.ENVIRONMENT == "production":
        raise RuntimeError(
            "FATAL: DEMO_MODE=true is not allowed in production environment! "
            "Demo mode contains synthetic data and should only be used for demonstrations. "
            "Set ENVIRONMENT to 'development' or 'local' to enable demo mode."
        )

    if settings.DEMO_MODE:
        print("=" * 60)
        print("⚠️  DEMO MODE ENABLED - Using synthetic data only")
        print("⚠️  No real PII or production data will be used")
        print("=" * 60)

    # IMPORTANT: Only auto-create tables in development/local environments
    # In production, use Alembic migrations: alembic upgrade head
    if settings.ENVIRONMENT in ("local", "development", "dev"):
        print("WARNING: Auto-creating database tables (development mode)")
        print("In production, use 'alembic upgrade head' instead")
        async with engine.begin() as conn:
            # Create PostgreSQL enum types before creating tables
            # These are required by the fraud models which use create_type=False
            from sqlalchemy import text
            enum_definitions = [
                ("fraud_type", [
                    'check_kiting', 'counterfeit_check', 'forged_signature', 'altered_check',
                    'account_takeover', 'identity_theft', 'first_party_fraud', 'synthetic_identity',
                    'duplicate_deposit', 'unauthorized_endorsement', 'payee_alteration',
                    'amount_alteration', 'fictitious_payee', 'other'
                ]),
                ("fraud_channel", ['branch', 'atm', 'mobile', 'rdc', 'mail', 'online', 'other']),
                ("amount_bucket", [
                    'under_100', '100_to_500', '500_to_1000', '1000_to_5000',
                    '5000_to_10000', '10000_to_50000', 'over_50000'
                ]),
                ("fraud_event_status", ['draft', 'submitted', 'withdrawn']),
                ("match_severity", ['low', 'medium', 'high']),
            ]
            for enum_name, enum_values in enum_definitions:
                values_str = ", ".join(f"'{v}'" for v in enum_values)
                # Check if type exists, create if not
                check_sql = text(
                    "SELECT 1 FROM pg_type WHERE typname = :name"
                )
                result = await conn.execute(check_sql, {"name": enum_name})
                if not result.fetchone():
                    create_sql = text(f"CREATE TYPE {enum_name} AS ENUM ({values_str})")
                    await conn.execute(create_sql)
                    print(f"Created enum type: {enum_name}")

            await conn.run_sync(Base.metadata.create_all)

            # Fix column sizes that may be too small in existing databases
            # audit_logs.resource_id needs to be 255 to accommodate demo image IDs
            alter_sql = text(
                "ALTER TABLE audit_logs ALTER COLUMN resource_id TYPE VARCHAR(255)"
            )
            try:
                await conn.execute(alter_sql)
                print("Updated audit_logs.resource_id column size")
            except Exception:
                pass  # Column already correct size or table doesn't exist yet

        print("Database tables created/verified")
    else:
        print("Production mode: Skipping auto-create. Use Alembic migrations.")

    yield
    # Shutdown
    print("Shutting down...")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Bank-grade Check Review Console for community bank operations",
    openapi_url=f"{settings.API_V1_PREFIX}/openapi.json",
    docs_url=f"{settings.API_V1_PREFIX}/docs",
    redoc_url=f"{settings.API_V1_PREFIX}/redoc",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle uncaught exceptions."""
    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_server_error",
            "message": "An unexpected error occurred",
            "details": str(exc) if settings.DEBUG else None,
        },
    )


# Health check endpoint
@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """
    Health check endpoint with real connectivity verification.

    Checks:
    - Database: Executes SELECT 1 to verify connection
    - Redis: Executes PING to verify connection (if configured)

    Returns 503 Service Unavailable if any critical dependency is down.
    """
    from sqlalchemy import text
    from app.db.session import AsyncSessionLocal

    db_status = "disconnected"
    redis_status = "not_configured"
    overall_status = "healthy"

    # Check database connection
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
            db_status = "connected"
    except Exception as e:
        db_status = f"error: {str(e)[:50]}"
        overall_status = "unhealthy"

    # Check Redis connection (if configured)
    if settings.REDIS_URL:
        try:
            import redis.asyncio as aioredis
            redis_client = aioredis.from_url(settings.REDIS_URL)
            pong = await redis_client.ping()
            redis_status = "connected" if pong else "no_response"
            await redis_client.close()
        except ImportError:
            redis_status = "redis_package_not_installed"
        except Exception as e:
            redis_status = f"error: {str(e)[:50]}"
            # Redis failure is non-critical if not required
            # Uncomment below to make Redis critical:
            # overall_status = "unhealthy"

    response = HealthResponse(
        status=overall_status,
        version=settings.APP_VERSION,
        database=db_status,
        redis=redis_status,
        timestamp=datetime.now(timezone.utc),
    )

    # Return 503 if unhealthy so load balancers can detect
    if overall_status == "unhealthy":
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=503,
            content=response.model_dump(mode="json"),
        )

    return response


# Include API router
app.include_router(api_router, prefix=settings.API_V1_PREFIX)


# Root endpoint
@app.get("/", tags=["Root"])
async def root():
    """Root endpoint."""
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": f"{settings.API_V1_PREFIX}/docs",
    }
