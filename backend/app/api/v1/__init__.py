"""API v1 routes."""

from fastapi import APIRouter

from app.api.v1.endpoints import (
    auth,
    checks,
    connector,
    decisions,
    images,
    image_connectors,
    monitoring,
    operations,
    policies,
    queues,
    users,
    audit,
    reports,
    fraud,
    security,
    system,
)

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(users.router, prefix="/users", tags=["Users"])
api_router.include_router(checks.router, prefix="/checks", tags=["Check Items"])
api_router.include_router(images.router, prefix="/images", tags=["Check Images"])
api_router.include_router(decisions.router, prefix="/decisions", tags=["Decisions"])
api_router.include_router(queues.router, prefix="/queues", tags=["Queues"])
api_router.include_router(policies.router, prefix="/policies", tags=["Policies"])
api_router.include_router(audit.router, prefix="/audit", tags=["Audit"])
api_router.include_router(reports.router, prefix="/reports", tags=["Reports"])
api_router.include_router(fraud.router, prefix="/fraud", tags=["Fraud Intelligence"])
api_router.include_router(connector.router, prefix="/connector", tags=["Connector B - Batch Commit"])
api_router.include_router(image_connectors.router, prefix="/image-connectors", tags=["Connector A - Image Connectors"])
api_router.include_router(system.router, prefix="/system", tags=["System"])
api_router.include_router(monitoring.router, prefix="/monitoring", tags=["Monitoring"])
api_router.include_router(security.router, prefix="/security", tags=["Security Incidents"])
api_router.include_router(operations.router, prefix="/operations", tags=["Operations"])
