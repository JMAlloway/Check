"""API v1 routes."""

from fastapi import APIRouter

from app.api.v1.endpoints import (
    auth,
    checks,
    connector,
    decisions,
    images,
    policies,
    queues,
    users,
    audit,
    reports,
    fraud,
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
