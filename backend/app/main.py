"""Main FastAPI application."""

import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from app.api.v1 import api_router
from app.core.config import settings
from app.core.logging_config import configure_logging
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

logger = logging.getLogger("app.startup")
from app.core.metrics import MetricsMiddleware, get_metrics
from app.core.middleware import (
    SecurityHeadersMiddleware,
    TokenRedactionMiddleware,
    install_token_redaction_logging,
)
from app.core.rate_limit import limiter, tenant_limiter, user_limiter
from app.db.session import Base, engine

# Import all models so they're registered with Base.metadata
from app.models import audit, check, connector, decision, fraud, policy, queue, user  # noqa: F401
from app.schemas.common import HealthResponse


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management."""
    # Startup - configure logging FIRST before any other startup logs
    configure_logging()
    install_token_redaction_logging()

    logger.info(
        "Starting application",
        extra={"app_name": settings.APP_NAME, "version": settings.APP_VERSION},
    )
    logger.info("Environment: %s", settings.ENVIRONMENT)

    # Log security-relevant endpoint exposure settings
    if settings.EXPOSE_DOCS:
        logger.info("API Docs: ENABLED at %s/docs", settings.API_V1_PREFIX)
    else:
        logger.info("API Docs: DISABLED (set EXPOSE_DOCS=true to enable)")

    if settings.EXPOSE_METRICS:
        if settings.METRICS_ALLOWED_IPS:
            logger.info("Metrics: ENABLED with IP allowlist: %s", settings.METRICS_ALLOWED_IPS)
        else:
            logger.warning(
                "Metrics: ENABLED (no IP restriction - consider setting METRICS_ALLOWED_IPS)"
            )
    else:
        logger.info("Metrics: DISABLED (set EXPOSE_METRICS=true to enable)")

    # CRITICAL SAFETY CHECK: Demo mode must NEVER run in production
    if settings.DEMO_MODE and settings.ENVIRONMENT == "production":
        raise RuntimeError(
            "FATAL: DEMO_MODE=true is not allowed in production environment! "
            "Demo mode contains synthetic data and should only be used for demonstrations. "
            "Set ENVIRONMENT to 'development' or 'local' to enable demo mode."
        )

    if settings.DEMO_MODE:
        logger.warning("DEMO MODE ENABLED - Using synthetic data only, no real PII")

    # IMPORTANT: Only auto-create tables in development/local environments
    # In production, use Alembic migrations: alembic upgrade head
    if settings.ENVIRONMENT in ("local", "development", "dev"):
        logger.warning(
            "Auto-creating database tables (development mode) - use 'alembic upgrade head' in production"
        )
        async with engine.begin() as conn:
            # Create PostgreSQL enum types before creating tables
            # These are required by the fraud models which use create_type=False
            from sqlalchemy import text

            enum_definitions = [
                (
                    "fraud_type",
                    [
                        "check_kiting",
                        "counterfeit_check",
                        "forged_signature",
                        "altered_check",
                        "account_takeover",
                        "identity_theft",
                        "first_party_fraud",
                        "synthetic_identity",
                        "duplicate_deposit",
                        "unauthorized_endorsement",
                        "payee_alteration",
                        "amount_alteration",
                        "fictitious_payee",
                        "other",
                    ],
                ),
                ("fraud_channel", ["branch", "atm", "mobile", "rdc", "mail", "online", "other"]),
                (
                    "amount_bucket",
                    [
                        "under_100",
                        "100_to_500",
                        "500_to_1000",
                        "1000_to_5000",
                        "5000_to_10000",
                        "10000_to_50000",
                        "over_50000",
                    ],
                ),
                ("fraud_event_status", ["draft", "submitted", "withdrawn"]),
                ("match_severity", ["low", "medium", "high"]),
            ]
            for enum_name, enum_values in enum_definitions:
                values_str = ", ".join(f"'{v}'" for v in enum_values)
                # Check if type exists, create if not
                check_sql = text("SELECT 1 FROM pg_type WHERE typname = :name")
                result = await conn.execute(check_sql, {"name": enum_name})
                if not result.fetchone():
                    create_sql = text(f"CREATE TYPE {enum_name} AS ENUM ({values_str})")
                    await conn.execute(create_sql)
                    logger.debug("Created enum type: %s", enum_name)

            await conn.run_sync(Base.metadata.create_all)

            # Fix column sizes that may be too small in existing databases
            # audit_logs.resource_id needs to be 255 to accommodate demo image IDs
            alter_sql = text("ALTER TABLE audit_logs ALTER COLUMN resource_id TYPE VARCHAR(255)")
            try:
                await conn.execute(alter_sql)
                logger.debug("Updated audit_logs.resource_id column size")
            except Exception:
                pass  # Column already correct size or table doesn't exist yet

        logger.info("Database tables created/verified")

        # Auto-seed demo data if DEMO_MODE is enabled
        if settings.DEMO_MODE:
            logger.info("Checking for demo data...")
            from app.demo.seed import seed_demo_data

            try:
                stats = await seed_demo_data(reset=False, count=settings.DEMO_DATA_COUNT)
                if stats["users"] > 0:
                    logger.info("Seeded demo data", extra={"stats": stats})
                else:
                    logger.info("Demo data already exists, skipping seed")
            except Exception as e:
                logger.warning("Failed to seed demo data: %s", e)
                # Don't fail startup - demo data seeding is not critical
    else:
        logger.info("Production mode: Skipping auto-create. Use Alembic migrations.")

    yield
    # Shutdown
    logger.info("Shutting down...")


# Conditionally expose API docs based on settings
# In production, docs are disabled by default for security
_docs_url = f"{settings.API_V1_PREFIX}/docs" if settings.EXPOSE_DOCS else None
_redoc_url = f"{settings.API_V1_PREFIX}/redoc" if settings.EXPOSE_DOCS else None
_openapi_url = f"{settings.API_V1_PREFIX}/openapi.json" if settings.EXPOSE_DOCS else None

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Bank-grade Check Review Console for community bank operations",
    openapi_url=_openapi_url,
    docs_url=_docs_url,
    redoc_url=_redoc_url,
    lifespan=lifespan,
)

# Rate limiting - register all limiters
# IP-based limiter (for unauthenticated endpoints)
app.state.limiter = limiter
# User-based limiter (for authenticated endpoints)
app.state.user_limiter = user_limiter
# Tenant-based limiter (for per-tenant quotas)
app.state.tenant_limiter = tenant_limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Prometheus metrics middleware
app.add_middleware(MetricsMiddleware)

# Security middleware - add after CORS so security headers are applied
# TokenRedactionMiddleware: Adds strict Referrer-Policy for secure image endpoints
app.add_middleware(TokenRedactionMiddleware)
# SecurityHeadersMiddleware: Adds standard security headers (X-Frame-Options, CSP, etc.)
app.add_middleware(SecurityHeadersMiddleware)


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


# Prometheus metrics endpoint with optional IP allowlisting
@app.get("/metrics", tags=["Metrics"], include_in_schema=settings.EXPOSE_METRICS)
async def metrics(request: Request):
    """
    Prometheus metrics endpoint for scraping.

    Security:
    - Disabled entirely when EXPOSE_METRICS=false (returns 404)
    - When enabled, optionally filtered by METRICS_ALLOWED_IPS
    - Banks should either disable this or set IP allowlist to internal/VPN ranges
    """
    # Check if metrics endpoint is enabled
    if not settings.EXPOSE_METRICS:
        return JSONResponse(
            status_code=404,
            content={"detail": "Not Found"},
        )

    # Check IP allowlist if configured
    if settings.METRICS_ALLOWED_IPS:
        import ipaddress

        client_ip = request.client.host if request.client else None
        if not client_ip:
            return JSONResponse(
                status_code=403,
                content={"detail": "Unable to determine client IP"},
            )

        # Parse allowed IPs/networks
        allowed_networks = []
        for ip_or_network in settings.METRICS_ALLOWED_IPS.split(","):
            ip_or_network = ip_or_network.strip()
            if not ip_or_network:
                continue
            try:
                # Try parsing as network (e.g., 10.0.0.0/8)
                allowed_networks.append(ipaddress.ip_network(ip_or_network, strict=False))
            except ValueError:
                try:
                    # Try parsing as single IP
                    allowed_networks.append(
                        ipaddress.ip_network(f"{ip_or_network}/32", strict=False)
                    )
                except ValueError:
                    continue  # Skip invalid entries

        # Check if client IP is in any allowed network
        try:
            client_addr = ipaddress.ip_address(client_ip)
            allowed = any(client_addr in network for network in allowed_networks)
            if not allowed:
                return JSONResponse(
                    status_code=403,
                    content={"detail": "IP not in allowlist"},
                )
        except ValueError:
            return JSONResponse(
                status_code=403,
                content={"detail": "Invalid client IP format"},
            )

    return get_metrics()


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
    from app.db.session import AsyncSessionLocal
    from sqlalchemy import text

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
    response = {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
    }
    # Only show docs URL if docs are enabled
    if settings.EXPOSE_DOCS:
        response["docs"] = f"{settings.API_V1_PREFIX}/docs"
    return response
