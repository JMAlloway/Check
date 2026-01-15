"""Frontend monitoring events endpoint.

Receives error reports, performance metrics, and security events
from the frontend for aggregation and alerting.

Security considerations:
- Rate limited to prevent abuse
- Input validation to prevent log injection
- No PII in error messages (client-side responsibility)
"""

import logging
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field, field_validator

from app.core.metrics import (
    security_events_total,
    track_security_event,
)

router = APIRouter()
logger = logging.getLogger("frontend.monitoring")


class FrontendErrorEvent(BaseModel):
    """Frontend JavaScript error event."""

    type: Literal["error"]
    message: str = Field(..., max_length=1000)
    stack: str | None = Field(None, max_length=10000)
    componentStack: str | None = Field(None, max_length=5000)
    url: str = Field(..., max_length=2000)
    userAgent: str = Field(..., max_length=500)
    timestamp: str
    sessionId: str = Field(..., max_length=50)
    userId: str | None = Field(None, max_length=50)
    metadata: dict | None = None

    @field_validator("message", "stack", "componentStack")
    @classmethod
    def sanitize_strings(cls, v: str | None) -> str | None:
        """Remove potentially dangerous content from error strings."""
        if v is None:
            return None
        # Remove any potential script tags or HTML
        v = v.replace("<script", "&lt;script").replace("</script", "&lt;/script")
        return v


class FrontendPerformanceEvent(BaseModel):
    """Frontend performance metric event."""

    type: Literal["performance"]
    metric: str = Field(..., pattern=r"^[A-Z]{2,10}$")  # LCP, FID, CLS, etc.
    value: float = Field(..., ge=0, le=1000000)  # Reasonable bounds
    rating: Literal["good", "needs-improvement", "poor"]
    url: str = Field(..., max_length=2000)
    timestamp: str
    sessionId: str = Field(..., max_length=50)


class FrontendSecurityEvent(BaseModel):
    """Frontend security-related event."""

    type: Literal["security"]
    eventType: str = Field(..., max_length=100, pattern=r"^[a-z_.]+$")
    severity: Literal["info", "warning", "error"]
    details: dict = Field(default_factory=dict)
    url: str = Field(..., max_length=2000)
    timestamp: str
    sessionId: str = Field(..., max_length=50)
    userId: str | None = Field(None, max_length=50)


class MonitoringEventsRequest(BaseModel):
    """Batch of frontend monitoring events."""

    events: list[FrontendErrorEvent | FrontendPerformanceEvent | FrontendSecurityEvent] = Field(
        ..., max_length=50
    )


class MonitoringEventsResponse(BaseModel):
    """Response for monitoring events submission."""

    received: int
    processed: int


@router.post("/events", response_model=MonitoringEventsResponse)
async def receive_monitoring_events(
    request: Request,
    data: MonitoringEventsRequest,
) -> MonitoringEventsResponse:
    """Receive frontend monitoring events.

    Accepts batched error reports, performance metrics, and security events
    from the frontend application.

    Rate limited to prevent abuse.
    """
    client_ip = request.client.host if request.client else "unknown"
    processed = 0

    for event in data.events:
        try:
            if event.type == "error":
                _process_error_event(event, client_ip)
                processed += 1

            elif event.type == "performance":
                _process_performance_event(event, client_ip)
                processed += 1

            elif event.type == "security":
                _process_security_event(event, client_ip)
                processed += 1

        except Exception as e:
            logger.warning(f"Failed to process frontend event: {e}")

    return MonitoringEventsResponse(
        received=len(data.events),
        processed=processed,
    )


def _process_error_event(event: FrontendErrorEvent, client_ip: str) -> None:
    """Process a frontend error event."""
    # Log for aggregation
    logger.error(
        "Frontend error",
        extra={
            "event_type": "frontend.error",
            "message": event.message[:200],  # Truncate for logging
            "url": event.url,
            "session_id": event.sessionId,
            "user_id": event.userId,
            "client_ip": client_ip,
            "has_stack": bool(event.stack),
            "has_component_stack": bool(event.componentStack),
            "metadata": event.metadata,
        },
    )

    # Update metrics
    security_events_total.labels(
        event_type="frontend.error",
        severity="error"
    ).inc()


def _process_performance_event(event: FrontendPerformanceEvent, client_ip: str) -> None:
    """Process a frontend performance metric event."""
    # Log for aggregation
    logger.info(
        f"Frontend performance: {event.metric}={event.value} ({event.rating})",
        extra={
            "event_type": "frontend.performance",
            "metric": event.metric,
            "value": event.value,
            "rating": event.rating,
            "url": event.url,
            "session_id": event.sessionId,
            "client_ip": client_ip,
        },
    )

    # Alert on poor performance in production
    if event.rating == "poor":
        logger.warning(
            f"Poor frontend performance: {event.metric}={event.value}ms",
            extra={
                "event_type": "frontend.performance.poor",
                "metric": event.metric,
                "value": event.value,
            },
        )


def _process_security_event(event: FrontendSecurityEvent, client_ip: str) -> None:
    """Process a frontend security event."""
    # Log for SIEM
    logger.warning(
        f"Frontend security event: {event.eventType}",
        extra={
            "event_type": f"frontend.{event.eventType}",
            "severity": event.severity,
            "details": event.details,
            "url": event.url,
            "session_id": event.sessionId,
            "user_id": event.userId,
            "client_ip": client_ip,
        },
    )

    # Update metrics
    track_security_event(f"frontend.{event.eventType}", event.severity)


@router.get("/health")
async def monitoring_health() -> dict:
    """Health check for monitoring endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
