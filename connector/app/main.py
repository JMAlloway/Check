"""
Bank-Side Connector Service

A secure service that runs inside the bank network to serve check images
to the cloud SaaS (Check Review Console).

Features:
- JWT RS256 authentication with replay protection
- Path validation against allowed UNC share roots
- TIFF/IMG to PNG conversion
- In-memory caching with TTL
- Structured JSON audit logging
- DEMO and BANK modes
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .api.v1 import router as api_v1_router
from .core.config import get_settings, ConnectorMode


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("connector")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    settings = get_settings()

    logger.info(f"Starting Bank-Side Connector v{settings.CONNECTOR_VERSION}")
    logger.info(f"Mode: {settings.MODE.value}")
    logger.info(f"Connector ID: {settings.CONNECTOR_ID}")

    # Check if we fell back from BANK mode
    if getattr(settings, "_bank_mode_fallback", False):
        logger.warning(
            "Running in DEMO mode due to BANK mode fallback. "
            "Set CONNECTOR_MODE=DEMO explicitly to suppress warnings."
        )

    if settings.MODE == ConnectorMode.DEMO:
        logger.info(f"Demo repo root: {settings.DEMO_REPO_ROOT}")
        logger.info(f"Item index path: {settings.ITEM_INDEX_PATH}")

    logger.info(f"Allowed share roots: {settings.ALLOWED_SHARE_ROOTS}")

    yield

    logger.info("Shutting down Bank-Side Connector")


# Create FastAPI application
settings = get_settings()

app = FastAPI(
    title="Bank-Side Connector",
    description="""
Secure service for serving check images from bank storage to the Check Review Console.

## Features
- Secure JWT RS256 authentication
- Path validation against allowed UNC share roots
- TIFF/IMG to PNG conversion
- In-memory caching with TTL
- Comprehensive audit logging

## Modes
- **DEMO**: Uses local filesystem to simulate UNC shares
- **BANK**: Connects to real UNC paths (requires production implementation)

## Authentication
All image endpoints require a JWT token in the Authorization header:
```
Authorization: Bearer <token>
```

Tokens are issued by the SaaS and validated using RS256 with a pinned public key.
    """,
    version=settings.CONNECTOR_VERSION,
    lifespan=lifespan,
    docs_url="/docs" if settings.MODE == ConnectorMode.DEMO else None,
    redoc_url="/redoc" if settings.MODE == ConnectorMode.DEMO else None,
)


# Add CORS middleware (adjust for production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.MODE == ConnectorMode.DEMO else [],
    allow_credentials=True,
    allow_methods=["GET", "OPTIONS"],
    allow_headers=["*"],
)


# Include API router
app.include_router(api_v1_router, prefix="/v1")


# Root health check (alias)
@app.get("/healthz", include_in_schema=False)
async def root_health_check():
    """Root-level health check (redirects to /v1/healthz)."""
    from .api.v1.endpoints.health import health_check
    return await health_check()


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle unexpected exceptions."""
    import uuid
    correlation_id = request.headers.get("X-Correlation-ID", str(uuid.uuid4()))

    logger.error(f"Unhandled exception: {exc}", exc_info=True)

    return JSONResponse(
        status_code=500,
        content={
            "error_code": "INTERNAL_ERROR",
            "message": "An unexpected error occurred",
            "correlation_id": correlation_id
        }
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "connector.app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.MODE == ConnectorMode.DEMO,
        log_level="info"
    )
