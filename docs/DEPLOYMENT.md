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
- [ ] Signed URL token redaction verified (see below)

## Signed Image URL Security (Bank Risk Compliance)

### Overview

Check images are served via signed URLs at `/api/v1/images/secure/{token}`. These URLs contain
short-lived JWT bearer tokens that grant temporary access to images for use in `<img>` tags.

**Security Model:**
- **Bearer Token**: Anyone with the URL can access the image (no session required)
- **Short TTL**: Tokens expire in 90 seconds (configurable via `IMAGE_SIGNED_URL_TTL_SECONDS`)
- **Audit Logging**: User ID embedded for audit trail (not access control)

### Risk Mitigation

Because tokens are bearer credentials, they must be protected from leakage:

| Leakage Vector | Mitigation | Implementation |
|----------------|------------|----------------|
| Application Logs | Token redaction filter | `app/core/middleware.py` - TokenRedactionFilter |
| Nginx Access Logs | Logging disabled for route | `docker/nginx.conf` - `access_log off` |
| Referrer Headers | `Referrer-Policy: no-referrer` | Set at nginx, middleware, and response level |
| Exception Traces | Exception arg redaction | `app/main.py` - global exception handler |
| Browser Cache | `Cache-Control: no-store` | Response headers in `images.py` |

### Token Redaction

All paths matching `/api/v1/images/secure/*` are automatically redacted to
`/api/v1/images/secure/[TOKEN_REDACTED]` in:
- FastAPI/uvicorn access logs
- Gunicorn access logs
- Security audit logs
- Exception messages and traces
- Error responses (in debug mode)

### Bank Vendor Risk Justification

For vendor risk assessments and security questionnaires:

1. **Token Confidentiality**: Bearer tokens are never logged in plain text
2. **Short Exposure Window**: 90-second TTL limits usefulness of leaked tokens
3. **No Referrer Leakage**: `Referrer-Policy: no-referrer` prevents cross-origin leakage
4. **Defense in Depth**: Protection at multiple layers (nginx, middleware, response headers)
5. **Audit Trail**: All image access is logged with user attribution
6. **No Caching**: Responses marked as non-cacheable in shared caches

### Manual Verification

To verify token redaction is working:

```bash
# Start the application and make a request
curl -v http://localhost:8000/api/v1/images/secure/test.token.value

# Check application logs - should see [TOKEN_REDACTED], not the actual token
docker logs check-backend 2>&1 | grep -i "images/secure"

# Verify no tokens in nginx logs
docker logs check-frontend 2>&1 | grep -i "images/secure"

# Test referrer policy header
curl -sI http://localhost:8000/api/v1/images/secure/test | grep -i referrer
# Should return: Referrer-Policy: no-referrer
```

### Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| `IMAGE_SIGNED_URL_TTL_SECONDS` | 90 | Token expiration time |
| Nginx `access_log` | off | Disabled for `/api/v1/images/secure/` |
| `Referrer-Policy` | no-referrer | Prevents token in referrer headers |

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
