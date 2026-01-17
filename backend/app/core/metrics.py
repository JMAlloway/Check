"""Prometheus metrics for SOC2 compliance monitoring.

This module provides application metrics for:
- Request latency and throughput
- Error rates
- Security events
- Business metrics (SLA, queue depths)

Metrics are exposed at /metrics endpoint for Prometheus scraping.
"""

from prometheus_client import Counter, Histogram, Gauge, Info, generate_latest, CONTENT_TYPE_LATEST
from fastapi import Response
from functools import wraps
import time

# Application info
app_info = Info('check_review_console', 'Check Review Console application info')
app_info.info({
    'version': '1.0.0',
    'environment': 'pilot',
})

# HTTP request metrics
http_requests_total = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status']
)

http_request_duration_seconds = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration in seconds',
    ['method', 'endpoint'],
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
)

# Security event metrics
security_events_total = Counter(
    'security_events_total',
    'Total security events',
    ['event_type', 'severity']
)

# Authentication metrics
auth_attempts_total = Counter(
    'auth_attempts_total',
    'Total authentication attempts',
    ['result']  # success, failure, mfa_required
)

active_sessions = Gauge(
    'active_sessions',
    'Number of active user sessions'
)

# Image token metrics
image_tokens_created_total = Counter(
    'image_tokens_created_total',
    'Total image access tokens created'
)

image_tokens_used_total = Counter(
    'image_tokens_used_total',
    'Total image access tokens consumed'
)

image_tokens_expired_total = Counter(
    'image_tokens_expired_total',
    'Total expired image token access attempts'
)

# Business metrics
check_items_total = Gauge(
    'check_items_total',
    'Total check items in system',
    ['status']
)

check_items_sla_breached_total = Gauge(
    'check_items_sla_breached_total',
    'Check items that have breached SLA'
)

queue_depth = Gauge(
    'queue_depth',
    'Number of items in each queue',
    ['queue_name']
)

decisions_total = Counter(
    'decisions_total',
    'Total decisions made',
    ['decision_type', 'action']
)

# Database metrics
db_query_duration_seconds = Histogram(
    'db_query_duration_seconds',
    'Database query duration in seconds',
    ['query_type'],
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0]
)

db_connection_pool_size = Gauge(
    'db_connection_pool_size',
    'Database connection pool size'
)

db_connection_pool_used = Gauge(
    'db_connection_pool_used',
    'Database connections in use'
)

# Audit metrics
audit_log_entries_total = Counter(
    'audit_log_entries_total',
    'Total audit log entries written',
    ['action']
)

audit_log_write_failures_total = Counter(
    'audit_log_write_failures_total',
    'Failed audit log write attempts'
)


def get_metrics() -> Response:
    """Generate Prometheus metrics response."""
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )


def track_request_metrics(method: str, endpoint: str, status: int, duration: float):
    """Track HTTP request metrics.

    Args:
        method: HTTP method (GET, POST, etc.)
        endpoint: Request endpoint path
        status: HTTP response status code
        duration: Request duration in seconds
    """
    http_requests_total.labels(
        method=method,
        endpoint=endpoint,
        status=str(status)
    ).inc()

    http_request_duration_seconds.labels(
        method=method,
        endpoint=endpoint
    ).observe(duration)


def track_security_event(event_type: str, severity: str = "info"):
    """Track security event metrics.

    Args:
        event_type: Type of security event
        severity: Event severity (info, warning, error, critical)
    """
    security_events_total.labels(
        event_type=event_type,
        severity=severity
    ).inc()


def track_auth_attempt(result: str):
    """Track authentication attempt.

    Args:
        result: Result of auth attempt (success, failure, mfa_required)
    """
    auth_attempts_total.labels(result=result).inc()


def track_decision(decision_type: str, action: str):
    """Track decision metrics.

    Args:
        decision_type: Type of decision (review, approval, escalation)
        action: Decision action (approve, reject, hold, etc.)
    """
    decisions_total.labels(
        decision_type=decision_type,
        action=action
    ).inc()


def track_audit_log(action: str, success: bool = True):
    """Track audit log write.

    Args:
        action: Audit action type
        success: Whether write was successful
    """
    if success:
        audit_log_entries_total.labels(action=action).inc()
    else:
        audit_log_write_failures_total.inc()


class MetricsMiddleware:
    """ASGI middleware for tracking request metrics."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Skip metrics endpoint itself
        path = scope.get("path", "")
        if path == "/metrics":
            await self.app(scope, receive, send)
            return

        method = scope.get("method", "UNKNOWN")
        start_time = time.time()
        status_code = 500  # Default in case of error

        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            duration = time.time() - start_time
            # Normalize path to avoid cardinality explosion
            normalized_path = self._normalize_path(path)
            track_request_metrics(method, normalized_path, status_code, duration)

    def _normalize_path(self, path: str) -> str:
        """Normalize path to avoid high cardinality.

        Replaces UUIDs and numeric IDs with placeholders.
        """
        import re

        # Replace UUIDs
        path = re.sub(
            r'[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}',
            '{id}',
            path
        )

        # Replace numeric IDs
        path = re.sub(r'/\d+(?=/|$)', '/{id}', path)

        return path
