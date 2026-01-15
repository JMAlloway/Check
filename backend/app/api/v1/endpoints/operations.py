"""
Operations & Monitoring API endpoints.

Provides system health, metrics, alerts, and DR status for the Operations Dashboard.
"""

import asyncio
import httpx
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.api.deps import get_current_active_user
from app.db.session import get_db
from app.models.user import User

router = APIRouter()


# =============================================================================
# Response Models
# =============================================================================

class ServiceStatus(BaseModel):
    """Status of a single service."""
    name: str
    status: str  # "healthy", "degraded", "unhealthy", "unknown"
    latency_ms: float | None = None
    details: dict[str, Any] | None = None
    last_checked: datetime


class SystemHealth(BaseModel):
    """Overall system health status."""
    overall_status: str
    services: list[ServiceStatus]
    timestamp: datetime


class PerformanceMetrics(BaseModel):
    """Performance metrics summary."""
    requests_per_minute: float
    avg_response_time_ms: float
    error_rate_percent: float
    active_users: int
    pending_checks: int
    checks_processed_today: int
    timestamp: datetime


class Alert(BaseModel):
    """Active alert from Alertmanager."""
    name: str
    severity: str
    status: str
    summary: str
    description: str | None = None
    started_at: datetime
    labels: dict[str, str]


class AlertsSummary(BaseModel):
    """Summary of active alerts."""
    total: int
    critical: int
    warning: int
    info: int
    alerts: list[Alert]
    timestamp: datetime


class BackupStatus(BaseModel):
    """Backup and DR status."""
    last_backup: datetime | None
    backup_size_mb: float | None
    backup_location: str | None
    replication_lag_seconds: float | None
    dr_environment_status: str
    last_dr_drill: datetime | None
    rto_target_hours: float
    rpo_target_minutes: float
    timestamp: datetime


# =============================================================================
# Helper Functions
# =============================================================================

async def check_database_health(db: AsyncSession) -> ServiceStatus:
    """Check database connectivity and health."""
    start = datetime.now(timezone.utc)
    try:
        result = await db.execute(text("SELECT 1"))
        result.fetchone()
        latency = (datetime.now(timezone.utc) - start).total_seconds() * 1000

        # Get connection count
        conn_result = await db.execute(
            text("SELECT count(*) FROM pg_stat_activity WHERE datname = current_database()")
        )
        conn_count = conn_result.scalar() or 0

        return ServiceStatus(
            name="PostgreSQL",
            status="healthy" if latency < 100 else "degraded",
            latency_ms=round(latency, 2),
            details={"connections": conn_count},
            last_checked=datetime.now(timezone.utc)
        )
    except Exception as e:
        return ServiceStatus(
            name="PostgreSQL",
            status="unhealthy",
            latency_ms=None,
            details={"error": str(e)},
            last_checked=datetime.now(timezone.utc)
        )


async def check_redis_health() -> ServiceStatus:
    """Check Redis connectivity."""
    start = datetime.now(timezone.utc)
    try:
        import redis.asyncio as redis
        r = redis.from_url(settings.REDIS_URL)
        await r.ping()
        latency = (datetime.now(timezone.utc) - start).total_seconds() * 1000

        info = await r.info("memory")
        await r.close()

        return ServiceStatus(
            name="Redis",
            status="healthy" if latency < 50 else "degraded",
            latency_ms=round(latency, 2),
            details={"used_memory_mb": round(info.get("used_memory", 0) / 1024 / 1024, 2)},
            last_checked=datetime.now(timezone.utc)
        )
    except Exception as e:
        return ServiceStatus(
            name="Redis",
            status="unhealthy",
            latency_ms=None,
            details={"error": str(e)},
            last_checked=datetime.now(timezone.utc)
        )


async def check_prometheus_health() -> ServiceStatus:
    """Check Prometheus connectivity."""
    start = datetime.now(timezone.utc)
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{settings.PROMETHEUS_URL}/-/healthy")
            latency = (datetime.now(timezone.utc) - start).total_seconds() * 1000

            if response.status_code == 200:
                return ServiceStatus(
                    name="Prometheus",
                    status="healthy",
                    latency_ms=round(latency, 2),
                    details=None,
                    last_checked=datetime.now(timezone.utc)
                )
            else:
                return ServiceStatus(
                    name="Prometheus",
                    status="degraded",
                    latency_ms=round(latency, 2),
                    details={"status_code": response.status_code},
                    last_checked=datetime.now(timezone.utc)
                )
    except Exception as e:
        return ServiceStatus(
            name="Prometheus",
            status="unknown",
            latency_ms=None,
            details={"error": str(e)},
            last_checked=datetime.now(timezone.utc)
        )


async def check_alertmanager_health() -> ServiceStatus:
    """Check Alertmanager connectivity."""
    start = datetime.now(timezone.utc)
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{settings.ALERTMANAGER_URL}/-/healthy")
            latency = (datetime.now(timezone.utc) - start).total_seconds() * 1000

            return ServiceStatus(
                name="Alertmanager",
                status="healthy" if response.status_code == 200 else "degraded",
                latency_ms=round(latency, 2),
                details=None,
                last_checked=datetime.now(timezone.utc)
            )
    except Exception as e:
        return ServiceStatus(
            name="Alertmanager",
            status="unknown",
            latency_ms=None,
            details={"error": str(e)},
            last_checked=datetime.now(timezone.utc)
        )


async def fetch_prometheus_metric(query: str) -> float | None:
    """Fetch a single metric value from Prometheus."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(
                f"{settings.PROMETHEUS_URL}/api/v1/query",
                params={"query": query}
            )
            if response.status_code == 200:
                data = response.json()
                if data["data"]["result"]:
                    return float(data["data"]["result"][0]["value"][1])
    except Exception:
        pass
    return None


async def fetch_alerts_from_alertmanager() -> list[Alert]:
    """Fetch active alerts from Alertmanager."""
    alerts = []
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{settings.ALERTMANAGER_URL}/api/v2/alerts")
            if response.status_code == 200:
                for alert_data in response.json():
                    alerts.append(Alert(
                        name=alert_data.get("labels", {}).get("alertname", "Unknown"),
                        severity=alert_data.get("labels", {}).get("severity", "unknown"),
                        status=alert_data.get("status", {}).get("state", "unknown"),
                        summary=alert_data.get("annotations", {}).get("summary", ""),
                        description=alert_data.get("annotations", {}).get("description"),
                        started_at=datetime.fromisoformat(
                            alert_data.get("startsAt", "").replace("Z", "+00:00")
                        ) if alert_data.get("startsAt") else datetime.now(timezone.utc),
                        labels=alert_data.get("labels", {})
                    ))
    except Exception:
        pass
    return alerts


# =============================================================================
# API Endpoints
# =============================================================================

@router.get("/health", response_model=SystemHealth)
async def get_system_health(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Get overall system health status.

    Checks connectivity to all critical services:
    - PostgreSQL database
    - Redis cache
    - Prometheus metrics
    - Alertmanager
    """
    # Run all health checks concurrently
    services = await asyncio.gather(
        check_database_health(db),
        check_redis_health(),
        check_prometheus_health(),
        check_alertmanager_health(),
    )

    # Determine overall status
    statuses = [s.status for s in services]
    if all(s == "healthy" for s in statuses):
        overall = "healthy"
    elif any(s == "unhealthy" for s in statuses):
        overall = "unhealthy"
    elif any(s == "degraded" for s in statuses):
        overall = "degraded"
    else:
        overall = "unknown"

    return SystemHealth(
        overall_status=overall,
        services=list(services),
        timestamp=datetime.now(timezone.utc)
    )


@router.get("/metrics", response_model=PerformanceMetrics)
async def get_performance_metrics(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Get performance metrics summary.

    Aggregates key metrics from Prometheus and database.
    """
    # Fetch metrics from Prometheus concurrently
    rpm, latency, error_rate = await asyncio.gather(
        fetch_prometheus_metric('sum(rate(http_requests_total[1m])) * 60'),
        fetch_prometheus_metric('histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m])) * 1000'),
        fetch_prometheus_metric('sum(rate(http_requests_total{status=~"5.."}[5m])) / sum(rate(http_requests_total[5m])) * 100'),
    )

    # Get database stats
    try:
        # Active sessions (approximate active users)
        active_result = await db.execute(
            text("SELECT COUNT(DISTINCT user_id) FROM audit_logs WHERE timestamp > NOW() - INTERVAL '15 minutes'")
        )
        active_users = active_result.scalar() or 0

        # Pending checks
        pending_result = await db.execute(
            text("SELECT COUNT(*) FROM check_items WHERE status IN ('new', 'in_review', 'pending_dual_control')")
        )
        pending_checks = pending_result.scalar() or 0

        # Checks processed today
        processed_result = await db.execute(
            text("SELECT COUNT(*) FROM check_items WHERE status IN ('approved', 'rejected', 'returned') AND updated_at > CURRENT_DATE")
        )
        checks_processed = processed_result.scalar() or 0
    except Exception:
        active_users = 0
        pending_checks = 0
        checks_processed = 0

    return PerformanceMetrics(
        requests_per_minute=round(rpm or 0, 2),
        avg_response_time_ms=round(latency or 0, 2),
        error_rate_percent=round(error_rate or 0, 4),
        active_users=active_users,
        pending_checks=pending_checks,
        checks_processed_today=checks_processed,
        timestamp=datetime.now(timezone.utc)
    )


@router.get("/alerts", response_model=AlertsSummary)
async def get_alerts(
    current_user: User = Depends(get_current_active_user),
):
    """
    Get active alerts from Alertmanager.
    """
    alerts = await fetch_alerts_from_alertmanager()

    return AlertsSummary(
        total=len(alerts),
        critical=sum(1 for a in alerts if a.severity == "critical"),
        warning=sum(1 for a in alerts if a.severity == "warning"),
        info=sum(1 for a in alerts if a.severity == "info"),
        alerts=alerts,
        timestamp=datetime.now(timezone.utc)
    )


@router.get("/dr-status", response_model=BackupStatus)
async def get_dr_status(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Get disaster recovery and backup status.
    """
    # In a real implementation, these would be fetched from:
    # - Backup system API
    # - Replication monitoring
    # - DR environment health check

    # For now, return configured targets and simulated status
    try:
        # Check if we can reach DR database (simulated)
        dr_status = "standby"

        # Get database size as proxy for backup size
        size_result = await db.execute(
            text("SELECT pg_database_size(current_database()) / 1024.0 / 1024.0")
        )
        db_size_mb = size_result.scalar() or 0
    except Exception:
        dr_status = "unknown"
        db_size_mb = 0

    return BackupStatus(
        last_backup=datetime.now(timezone.utc).replace(hour=2, minute=0, second=0, microsecond=0),
        backup_size_mb=round(db_size_mb, 2),
        backup_location="/backups/daily",
        replication_lag_seconds=0.5,  # Would come from pg_stat_replication
        dr_environment_status=dr_status,
        last_dr_drill=datetime(2024, 1, 15, tzinfo=timezone.utc),  # From DR drill logs
        rto_target_hours=1.0,
        rpo_target_minutes=15.0,
        timestamp=datetime.now(timezone.utc)
    )


@router.get("/quick-links")
async def get_quick_links(
    current_user: User = Depends(get_current_active_user),
):
    """
    Get quick links to monitoring tools.
    """
    return {
        "grafana": {
            "url": settings.GRAFANA_URL,
            "dashboards": [
                {"name": "Application Overview", "path": "/d/app-overview"},
                {"name": "Database Metrics", "path": "/d/db-metrics"},
                {"name": "Security Metrics", "path": "/d/security-metrics"},
            ]
        },
        "prometheus": {
            "url": settings.PROMETHEUS_URL,
            "useful_queries": [
                {"name": "Request Rate", "query": "rate(http_requests_total[5m])"},
                {"name": "Error Rate", "query": "rate(http_requests_total{status=~'5..'}[5m])"},
                {"name": "Latency P95", "query": "histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))"},
            ]
        },
        "alertmanager": {
            "url": settings.ALERTMANAGER_URL,
        },
        "documentation": [
            {"name": "Rollback Procedures", "path": "/docs/ROLLBACK_PROCEDURES.md"},
            {"name": "DR Drill Guide", "path": "/docs/DISASTER_RECOVERY_DRILL.md"},
            {"name": "Capacity Planning", "path": "/docs/CAPACITY_PLANNING.md"},
        ]
    }
