# Pilot Deployment Runbook

This runbook provides step-by-step instructions for deploying the Check Review Console
in a bank pilot environment. Follow these instructions carefully to ensure a secure,
production-like deployment.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Initial Setup](#initial-setup)
3. [Configuration](#configuration)
4. [TLS Certificates](#tls-certificates)
5. [Deployment](#deployment)
6. [Verification](#verification)
7. [Operations](#operations)
8. [Backup & Restore](#backup--restore)
9. [Secret Rotation](#secret-rotation)
10. [Troubleshooting](#troubleshooting)
11. [Security Posture](#security-posture)

---

## Prerequisites

### System Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| CPU | 2 cores | 4 cores |
| RAM | 4 GB | 8 GB |
| Storage | 20 GB | 50 GB SSD |
| OS | Linux (Ubuntu 22.04+, RHEL 8+) | Ubuntu 22.04 LTS |

### Required Software

```bash
# Docker Engine 24.0+
docker --version

# Docker Compose v2.20+
docker compose version

# OpenSSL (for certificate generation)
openssl version

# Python 3.8+ (for secret generation and smoke tests)
python3 --version
```

### Network Requirements

- Ports 80 and 443 accessible (or custom ports via `HTTP_PORT`/`HTTPS_PORT`)
- Outbound access to Docker Hub (for image pulls) or internal registry
- DNS entry pointing to the deployment server

---

## Initial Setup

### 1. Clone the Repository

```bash
git clone https://github.com/your-org/check-review-console.git
cd check-review-console
```

### 2. Navigate to Docker Directory

```bash
cd docker
```

### 3. Create Environment File

```bash
cp .env.pilot.example .env.pilot
```

---

## Configuration

### Generate Secure Secrets

**CRITICAL**: Each secret must be uniquely generated. Never reuse secrets across environments.

```bash
# Generate all required secrets
echo "SECRET_KEY=$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
echo "CSRF_SECRET_KEY=$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
echo "NETWORK_PEPPER=$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
echo "POSTGRES_PASSWORD=$(python3 -c 'import secrets; print(secrets.token_urlsafe(24))')"
```

### Edit .env.pilot

```bash
# Edit the environment file with your generated secrets
nano .env.pilot
```

#### Required Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `POSTGRES_USER` | Database username | `check_pilot_user` |
| `POSTGRES_PASSWORD` | Database password (generated) | `abc123...` |
| `SECRET_KEY` | JWT signing key (generated) | `xyz789...` |
| `CSRF_SECRET_KEY` | CSRF protection key (generated) | `def456...` |
| `NETWORK_PEPPER` | Fraud network hashing pepper (generated) | `ghi012...` |
| `CORS_ORIGINS` | Allowed origins (JSON array) | `["https://pilot.bank.com"]` |

#### Optional Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `IMAGE_TAG` | `latest` | Docker image version |
| `HTTP_PORT` | `80` | HTTP port |
| `HTTPS_PORT` | `443` | HTTPS port |
| `DEMO_MODE` | `false` | Enable demo data (testing only) |
| `LOG_LEVEL` | `INFO` | Logging verbosity |

---

## TLS Certificates

### Option A: Use Existing Certificates

Place your certificates in the `docker/certs/` directory:

```bash
mkdir -p certs
cp /path/to/your/certificate.crt certs/server.crt
cp /path/to/your/private.key certs/server.key
chmod 600 certs/server.key
```

### Option B: Generate Self-Signed (Testing Only)

```bash
mkdir -p certs
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout certs/server.key \
  -out certs/server.crt \
  -subj "/C=US/ST=State/L=City/O=Organization/CN=pilot.yourbank.com"

chmod 600 certs/server.key
```

### Certificate Requirements

- Format: PEM
- Key size: RSA 2048-bit minimum (4096-bit recommended)
- Validity: Check expiration before deployment
- Chain: Include intermediate certificates in `server.crt` if needed

---

## Deployment

### Build Images

```bash
docker compose -f docker-compose.pilot.yml --env-file .env.pilot build
```

### Start Services

```bash
docker compose -f docker-compose.pilot.yml --env-file .env.pilot up -d
```

### Monitor Startup

```bash
# Watch all service logs
docker compose -f docker-compose.pilot.yml logs -f

# Check service status
docker compose -f docker-compose.pilot.yml ps
```

### Expected Startup Sequence

1. **db** - PostgreSQL starts first (30s)
2. **redis** - Redis cache starts (5s)
3. **migrations** - Runs Alembic migrations then exits
4. **backend** - API server starts after migrations complete (40s)
5. **frontend** - Static frontend server starts (10s)
6. **nginx** - Reverse proxy starts last (5s)

---

## Verification

### Health Check Endpoints

```bash
# Nginx health (HTTP)
curl -s http://localhost/health
# Expected: "healthy"

# Backend API health (via nginx)
curl -sk https://localhost/api/v1/health
# Expected: JSON with service status

# Backend direct (from within network)
docker exec check_pilot_backend curl -s http://localhost:8000/health
```

### Run Smoke Tests

```bash
# From the repository root
./scripts/smoke-test.sh

# Or with custom URL
./scripts/smoke-test.sh https://pilot.yourbank.com
```

### Verify Security Headers

```bash
curl -sI https://localhost | grep -E "(Strict-Transport|X-Frame|X-Content|Referrer)"
```

Expected headers:
```
Strict-Transport-Security: max-age=31536000; includeSubDomains
X-Frame-Options: SAMEORIGIN
X-Content-Type-Options: nosniff
Referrer-Policy: strict-origin-when-cross-origin
```

---

## Operations

### View Logs

```bash
# All services
docker compose -f docker-compose.pilot.yml logs -f

# Specific service
docker compose -f docker-compose.pilot.yml logs -f backend

# Last 100 lines
docker compose -f docker-compose.pilot.yml logs --tail=100 backend
```

### Stop Services

```bash
docker compose -f docker-compose.pilot.yml down
```

### Restart a Service

```bash
docker compose -f docker-compose.pilot.yml restart backend
```

### Update Deployment

```bash
# Pull latest code
git pull origin main

# Rebuild and restart
docker compose -f docker-compose.pilot.yml --env-file .env.pilot build
docker compose -f docker-compose.pilot.yml --env-file .env.pilot up -d
```

### Run Migrations Manually

```bash
docker compose -f docker-compose.pilot.yml run --rm migrations
```

### Access Database Shell

```bash
docker exec -it check_pilot_db psql -U $POSTGRES_USER -d check_review
```

### Access Backend Shell

```bash
docker exec -it check_pilot_backend /bin/bash
```

---

## Backup & Restore

### Database Backup

```bash
# Create backup directory
mkdir -p backups

# Full database backup
docker exec check_pilot_db pg_dump -U $POSTGRES_USER -d check_review \
  --format=custom --file=/tmp/backup.dump

# Copy to host
docker cp check_pilot_db:/tmp/backup.dump backups/backup_$(date +%Y%m%d_%H%M%S).dump

# Cleanup
docker exec check_pilot_db rm /tmp/backup.dump
```

### Automated Backup Script

```bash
#!/bin/bash
# backup.sh - Run via cron for automated backups

BACKUP_DIR="/path/to/backups"
RETENTION_DAYS=30
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Create backup
docker exec check_pilot_db pg_dump -U check_pilot_user -d check_review \
  --format=custom --file=/tmp/backup.dump

docker cp check_pilot_db:/tmp/backup.dump "$BACKUP_DIR/backup_$TIMESTAMP.dump"
docker exec check_pilot_db rm /tmp/backup.dump

# Cleanup old backups
find "$BACKUP_DIR" -name "backup_*.dump" -mtime +$RETENTION_DAYS -delete

echo "Backup completed: $BACKUP_DIR/backup_$TIMESTAMP.dump"
```

### Database Restore

```bash
# Stop backend to prevent connections
docker compose -f docker-compose.pilot.yml stop backend

# Restore from backup
docker cp backups/backup_YYYYMMDD_HHMMSS.dump check_pilot_db:/tmp/restore.dump

docker exec check_pilot_db pg_restore -U $POSTGRES_USER -d check_review \
  --clean --if-exists /tmp/restore.dump

docker exec check_pilot_db rm /tmp/restore.dump

# Start backend
docker compose -f docker-compose.pilot.yml start backend
```

### Redis Backup

```bash
# Redis data is persisted to volume automatically via AOF
# For manual backup:
docker exec check_pilot_redis redis-cli BGSAVE
docker cp check_pilot_redis:/data/dump.rdb backups/redis_$(date +%Y%m%d_%H%M%S).rdb
```

---

## Secret Rotation

### Rotate Application Secrets

**WARNING**: Rotating `SECRET_KEY` will invalidate all active sessions.

1. Generate new secrets:
   ```bash
   python3 -c "import secrets; print(secrets.token_urlsafe(32))"
   ```

2. Update `.env.pilot` with new values

3. Restart services:
   ```bash
   docker compose -f docker-compose.pilot.yml --env-file .env.pilot up -d
   ```

### Rotate Database Password

1. Generate new password:
   ```bash
   NEW_PASS=$(python3 -c "import secrets; print(secrets.token_urlsafe(24))")
   echo "New password: $NEW_PASS"
   ```

2. Update PostgreSQL:
   ```bash
   docker exec -it check_pilot_db psql -U postgres -c \
     "ALTER USER check_pilot_user WITH PASSWORD '$NEW_PASS';"
   ```

3. Update `.env.pilot` with new password

4. Restart services:
   ```bash
   docker compose -f docker-compose.pilot.yml --env-file .env.pilot up -d
   ```

### Rotate TLS Certificates

1. Obtain new certificates
2. Replace files in `docker/certs/`
3. Reload nginx:
   ```bash
   docker exec check_pilot_nginx nginx -s reload
   ```

---

## Troubleshooting

### Service Won't Start

```bash
# Check logs for errors
docker compose -f docker-compose.pilot.yml logs backend

# Check container status
docker ps -a | grep check_pilot

# Check resource usage
docker stats --no-stream
```

### Database Connection Issues

```bash
# Test database connectivity
docker exec check_pilot_backend python -c "
from sqlalchemy import create_engine
import os
engine = create_engine(os.environ['DATABASE_URL'].replace('+asyncpg', ''))
with engine.connect() as conn:
    print('Database connection successful')
"
```

### Migration Failures

```bash
# Check migration status
docker exec check_pilot_backend alembic current

# View migration history
docker exec check_pilot_backend alembic history

# Retry migrations
docker compose -f docker-compose.pilot.yml run --rm migrations
```

### Health Check Failures

```bash
# Test internal endpoints
docker exec check_pilot_backend curl -s http://localhost:8000/health

# Check nginx configuration
docker exec check_pilot_nginx nginx -t
```

### Out of Disk Space

```bash
# Check disk usage
df -h

# Clean up Docker
docker system prune -a --volumes

# Check log sizes
du -sh /var/lib/docker/containers/*/
```

---

## Security Posture

### Network Architecture

```
Internet → Nginx (TLS) → Backend API → PostgreSQL
                     ↘               ↘ Redis
                      Frontend (static)
```

- **Database**: Not exposed to host, internal network only
- **Redis**: Not exposed to host, internal network only
- **Backend**: Exposed only via nginx reverse proxy
- **TLS Termination**: At nginx layer

### Security Headers

| Header | Value | Purpose |
|--------|-------|---------|
| `Strict-Transport-Security` | `max-age=31536000` | Force HTTPS |
| `X-Frame-Options` | `SAMEORIGIN` | Prevent clickjacking |
| `X-Content-Type-Options` | `nosniff` | Prevent MIME sniffing |
| `X-XSS-Protection` | `1; mode=block` | XSS filter |
| `Referrer-Policy` | `strict-origin-when-cross-origin` | Control referrer |
| `Content-Security-Policy` | Restrictive CSP | Prevent XSS/injection |

### Bearer Token Protection

Signed image URLs contain bearer tokens that:
- Are NOT logged in nginx access logs (disabled for `/api/v1/images/secure/`)
- Are NOT logged in application logs (token redaction filter)
- Have short TTL (90 seconds default)
- Use `Referrer-Policy: no-referrer` to prevent leakage

### Rate Limiting

| Endpoint Type | Rate Limit |
|---------------|------------|
| Authentication | 5 req/sec |
| API General | 30 req/sec |
| Images | 50 req/sec burst |

### Least Privilege

- Backend runs as non-root user (`appuser`)
- Database user has minimum required permissions
- Containers have memory limits
- No bind mounts of source code

### Audit Logging

- All authentication events logged
- All authorization failures logged
- Structured JSON logging for SIEM integration
- Log rotation configured (50MB max, 5 files)

---

## Quick Reference

### Commands Cheat Sheet

```bash
# Start
docker compose -f docker-compose.pilot.yml --env-file .env.pilot up -d

# Stop
docker compose -f docker-compose.pilot.yml down

# Logs
docker compose -f docker-compose.pilot.yml logs -f

# Status
docker compose -f docker-compose.pilot.yml ps

# Rebuild
docker compose -f docker-compose.pilot.yml --env-file .env.pilot build
docker compose -f docker-compose.pilot.yml --env-file .env.pilot up -d

# Migrations
docker compose -f docker-compose.pilot.yml run --rm migrations

# Backup
docker exec check_pilot_db pg_dump -U check_pilot_user -d check_review -F c > backup.dump

# Shell access
docker exec -it check_pilot_backend /bin/bash
docker exec -it check_pilot_db psql -U check_pilot_user -d check_review
```

### Health Endpoints

| Endpoint | Purpose | Expected Response |
|----------|---------|-------------------|
| `http://localhost/health` | Nginx health | `healthy` |
| `https://localhost/api/v1/health` | API health | JSON status |
| `https://localhost/api/v1/auth/login` | Auth endpoint | 401 (no creds) |

### Support Contacts

- **Application Issues**: [your-team@bank.com]
- **Infrastructure**: [infra-team@bank.com]
- **Security Incidents**: [security@bank.com]

---

*Last Updated: January 2026*
*Version: 1.0*
