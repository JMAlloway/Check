# Deployment Guide

## Overview

This guide covers deploying the Check Review Console to production environments.

## Prerequisites

- Docker and Docker Compose
- PostgreSQL 15+
- Redis 7+
- Domain name and SSL certificates
- Access to a container registry

## Architecture

```
                    ┌─────────────────┐
                    │   Load Balancer │
                    │   (TLS/HTTPS)   │
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
      ┌───────▼───────┐ ┌────▼────┐ ┌───────▼───────┐
      │   Frontend    │ │   API   │ │   Backend     │
      │   (Nginx)     │ │  Proxy  │ │   Workers     │
      └───────────────┘ └─────────┘ └───────────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
      ┌───────▼───────┐ ┌────▼────┐ ┌───────▼───────┐
      │  PostgreSQL   │ │  Redis  │ │  Object Store │
      │  (Primary)    │ │ Cluster │ │  (Images)     │
      └───────────────┘ └─────────┘ └───────────────┘
```

## Environment Configuration

### Required Environment Variables

```bash
# Database
DATABASE_URL=postgresql+asyncpg://user:password@host:5432/check_review

# Security (CRITICAL - use strong random values)
SECRET_KEY=<64-character-random-string>

# Redis
REDIS_URL=redis://host:6379/0

# Application
ENVIRONMENT=production
DEBUG=false
API_V1_PREFIX=/api/v1

# CORS (adjust for your domain)
CORS_ORIGINS=["https://your-domain.com"]

# Session
SESSION_TIMEOUT_MINUTES=30
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

# Business Rules
DUAL_CONTROL_THRESHOLD=5000.0
HIGH_PRIORITY_THRESHOLD=10000.0
DEFAULT_SLA_HOURS=4

# AI (if enabled)
AI_ENABLED=false
AI_CONFIDENCE_THRESHOLD=0.7

# Rate Limiting
RATE_LIMIT_PER_MINUTE=100
```

## Kubernetes Deployment

### Backend Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: check-review-backend
spec:
  replicas: 3
  selector:
    matchLabels:
      app: check-review-backend
  template:
    metadata:
      labels:
        app: check-review-backend
    spec:
      containers:
      - name: backend
        image: ghcr.io/your-org/check-review-backend:latest
        ports:
        - containerPort: 8000
        envFrom:
        - secretRef:
            name: check-review-secrets
        resources:
          requests:
            memory: "512Mi"
            cpu: "250m"
          limits:
            memory: "1Gi"
            cpu: "1000m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
```

### Frontend Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: check-review-frontend
spec:
  replicas: 2
  selector:
    matchLabels:
      app: check-review-frontend
  template:
    metadata:
      labels:
        app: check-review-frontend
    spec:
      containers:
      - name: frontend
        image: ghcr.io/your-org/check-review-frontend:latest
        ports:
        - containerPort: 80
        resources:
          requests:
            memory: "128Mi"
            cpu: "100m"
          limits:
            memory: "256Mi"
            cpu: "500m"
```

## Database Setup

### Initial Migration

```bash
# Run migrations
alembic upgrade head

# Create default policy
python -c "from app.policy.engine import create_default_policy; import asyncio; asyncio.run(create_default_policy())"
```

### Backup Strategy

- Daily full backups
- Point-in-time recovery enabled
- Backup retention: 30 days minimum (7 years for audit data)

## Security Checklist

- [ ] TLS/HTTPS enabled on all endpoints
- [ ] Strong SECRET_KEY generated (64+ characters)
- [ ] Database credentials rotated
- [ ] Network segmentation configured
- [ ] WAF/DDoS protection enabled
- [ ] Security headers configured
- [ ] Rate limiting enabled
- [ ] Audit logging to secure storage
- [ ] Access logs retained for compliance

## Monitoring

### Health Endpoints

- `/health` - Application health check
- `/api/v1/health` - API health check

### Metrics to Monitor

- Request latency (p50, p95, p99)
- Error rates (4xx, 5xx)
- Queue depths
- SLA breach counts
- Active sessions
- Database connection pool
- Redis memory usage

### Alerts

Set up alerts for:
- Error rate > 1%
- Latency p95 > 2s
- SLA breaches > 5 per hour
- Database connections > 80%
- Redis memory > 80%

## Scaling Considerations

### Horizontal Scaling

- Backend: Scale based on CPU/request count
- Frontend: Scale based on request count
- Database: Read replicas for reporting

### Vertical Scaling

- Database: Size for concurrent connections and data volume
- Redis: Size for cache hit rate

## Disaster Recovery

### RTO/RPO Targets

- RTO (Recovery Time Objective): 4 hours
- RPO (Recovery Point Objective): 1 hour

### Recovery Procedures

1. Database restoration from backup
2. Redis cache rebuild (automatic)
3. Application redeployment
4. DNS failover (if applicable)

## Compliance

### Data Retention

- Audit logs: 7 years minimum
- Check images: Per regulatory requirements
- User sessions: 90 days

### Access Control

- MFA required for admin access
- IP allowlisting for sensitive operations
- Regular access reviews
