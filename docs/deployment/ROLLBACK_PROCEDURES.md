# Rollback Procedures

This document outlines procedures for rolling back deployments, database changes, and configuration updates for the Check Review Console.

## Table of Contents
- [Overview](#overview)
- [Application Rollback](#application-rollback)
- [Database Rollback](#database-rollback)
- [Configuration Rollback](#configuration-rollback)
- [Emergency Procedures](#emergency-procedures)
- [Verification Steps](#verification-steps)

---

## Overview

### Rollback Decision Criteria

Initiate rollback when any of the following occurs:
- Error rate exceeds 5% for more than 5 minutes
- Response time P95 exceeds 2 seconds for more than 10 minutes
- Critical functionality is broken (authentication, decisions, audit logging)
- Data integrity issues are detected
- Security vulnerability discovered in new release

### Communication Protocol

1. **Notify** - Alert the team via Slack/PagerDuty
2. **Assess** - Determine scope and impact
3. **Decide** - Rollback vs hotfix decision
4. **Execute** - Follow appropriate procedure
5. **Verify** - Confirm system health
6. **Document** - Create incident report

---

## Application Rollback

### Docker-Based Deployment

#### Quick Rollback (< 5 minutes)

```bash
# 1. Identify the previous working version
docker images check_review_backend --format "{{.Tag}} {{.CreatedAt}}"

# 2. Stop current containers
docker-compose stop backend

# 3. Update image tag to previous version
export BACKEND_VERSION=<previous-version>

# 4. Start with previous version
docker-compose up -d backend

# 5. Verify health
curl -f http://localhost:8000/health
```

#### Full Rollback with Database Restore

```bash
# 1. Stop all application containers
docker-compose stop backend frontend

# 2. Restore database (see Database Rollback section)

# 3. Deploy previous application version
git checkout <previous-tag>
docker-compose build backend frontend
docker-compose up -d

# 4. Verify all services
./scripts/health_check.sh
```

### Kubernetes Deployment

```bash
# 1. View deployment history
kubectl rollout history deployment/check-review-backend -n check-review

# 2. Rollback to previous revision
kubectl rollout undo deployment/check-review-backend -n check-review

# 3. Or rollback to specific revision
kubectl rollout undo deployment/check-review-backend -n check-review --to-revision=<N>

# 4. Monitor rollback progress
kubectl rollout status deployment/check-review-backend -n check-review

# 5. Verify pods are healthy
kubectl get pods -n check-review -l app=check-review-backend
```

### Git-Based Version Control

```bash
# 1. Identify last known good commit
git log --oneline -20

# 2. Create rollback branch
git checkout -b rollback/<date> <good-commit>

# 3. Or revert specific commits
git revert <bad-commit-1> <bad-commit-2>

# 4. Deploy rollback branch
./scripts/deploy.sh rollback/<date>
```

---

## Database Rollback

### Pre-Rollback Checklist

- [ ] Identify affected tables/rows
- [ ] Estimate rollback time
- [ ] Notify affected users
- [ ] Verify backup availability
- [ ] Prepare rollback script

### Point-in-Time Recovery (PITR)

```bash
# 1. Stop the application
docker-compose stop backend

# 2. Connect to PostgreSQL
docker exec -it check_review_db psql -U postgres

# 3. Create recovery point
SELECT pg_create_restore_point('pre_rollback_' || NOW()::date);

# 4. Restore from backup
pg_restore -h localhost -U postgres -d check_review_new /backups/check_review_<timestamp>.dump

# 5. Verify restored data
psql -U postgres -d check_review_new -c "SELECT count(*) FROM check_items;"

# 6. Swap databases
ALTER DATABASE check_review RENAME TO check_review_old;
ALTER DATABASE check_review_new RENAME TO check_review;

# 7. Restart application
docker-compose start backend
```

### Migration Rollback

```bash
# 1. List migrations
alembic history

# 2. Identify target revision
alembic current

# 3. Downgrade to specific revision
alembic downgrade <revision>

# 4. Or downgrade by steps
alembic downgrade -1  # One step back
alembic downgrade -3  # Three steps back

# 5. Verify schema
alembic current
```

### Specific Table Recovery

```sql
-- 1. Restore specific table from backup
CREATE TABLE check_items_restored AS
SELECT * FROM dblink(
  'dbname=check_review_backup',
  'SELECT * FROM check_items WHERE created_at > ''2024-01-01'''
) AS t(...);

-- 2. Verify data
SELECT count(*) FROM check_items_restored;

-- 3. Truncate and restore (DANGEROUS - backup first!)
BEGIN;
TRUNCATE check_items CASCADE;
INSERT INTO check_items SELECT * FROM check_items_restored;
COMMIT;

-- 4. Or merge changes
INSERT INTO check_items
SELECT * FROM check_items_restored r
WHERE NOT EXISTS (SELECT 1 FROM check_items c WHERE c.id = r.id);
```

### Audit Log Considerations

**IMPORTANT**: Audit logs are immutable and should NOT be rolled back except in extreme circumstances. If audit log rollback is required:

1. Document the reason thoroughly
2. Get approval from compliance officer
3. Preserve a backup of the audit logs being removed
4. Create a new audit entry documenting the rollback

---

## Configuration Rollback

### Environment Variables

```bash
# 1. View current configuration
docker-compose config

# 2. Backup current .env
cp .env .env.backup.$(date +%Y%m%d_%H%M%S)

# 3. Restore previous .env
cp .env.previous .env

# 4. Restart services
docker-compose up -d
```

### Nginx Configuration

```bash
# 1. Test new configuration before applying
nginx -t -c /path/to/nginx.conf

# 2. If test fails, restore backup
cp /etc/nginx/nginx.conf.backup /etc/nginx/nginx.conf
nginx -s reload

# 3. Verify nginx is serving correctly
curl -I http://localhost/health
```

### Prometheus/Alertmanager Rules

```bash
# 1. Validate rules syntax
promtool check rules prometheus/alerts/*.yml

# 2. If validation fails, restore
git checkout HEAD~1 -- prometheus/alerts/

# 3. Reload Prometheus
curl -X POST http://localhost:9090/-/reload
```

---

## Emergency Procedures

### Complete System Failure

```bash
#!/bin/bash
# emergency_rollback.sh

echo "=== EMERGENCY ROLLBACK INITIATED ==="
echo "Time: $(date -u +"%Y-%m-%d %H:%M:%S UTC")"

# 1. Stop all services
echo "Stopping all services..."
docker-compose down

# 2. Restore last known good database backup
echo "Restoring database..."
LATEST_BACKUP=$(ls -t /backups/check_review_*.dump | head -1)
docker-compose up -d db
sleep 10
docker exec -i check_review_db pg_restore -U postgres -d check_review < $LATEST_BACKUP

# 3. Deploy last known good version
echo "Deploying last stable version..."
git checkout $(cat /var/rollback/last_stable_tag)
docker-compose build
docker-compose up -d

# 4. Health check
echo "Running health checks..."
sleep 30
./scripts/health_check.sh

echo "=== EMERGENCY ROLLBACK COMPLETE ==="
```

### Partial Service Failure

```bash
# If only backend is failing
docker-compose stop backend
docker-compose up -d backend --scale backend=2  # Try multiple instances

# If database is failing
docker-compose restart db
docker exec check_review_db pg_isready -U postgres

# If Redis is failing
docker-compose restart redis
docker exec check_review_redis redis-cli ping
```

### Data Corruption Recovery

```bash
# 1. Immediately stop writes
docker-compose exec backend kill -SIGTERM 1

# 2. Create forensic copy
pg_dump -U postgres check_review > /forensics/check_review_$(date +%s).sql

# 3. Identify corruption scope
psql -U postgres -d check_review -c "
  SELECT relname, n_dead_tup, last_vacuum, last_autovacuum
  FROM pg_stat_user_tables
  ORDER BY n_dead_tup DESC;
"

# 4. Restore from backup or repair
# See Database Rollback section
```

---

## Verification Steps

### Post-Rollback Health Checks

```bash
#!/bin/bash
# health_check.sh

echo "=== POST-ROLLBACK VERIFICATION ==="

# 1. API Health
echo "Checking API health..."
curl -sf http://localhost:8000/health || exit 1

# 2. Database connectivity
echo "Checking database..."
docker exec check_review_db pg_isready -U postgres || exit 1

# 3. Redis connectivity
echo "Checking Redis..."
docker exec check_review_redis redis-cli ping || exit 1

# 4. Authentication endpoint
echo "Checking authentication..."
curl -sf http://localhost:8000/api/v1/auth/status || exit 1

# 5. Prometheus metrics
echo "Checking metrics..."
curl -sf http://localhost:8000/metrics | grep -q "http_requests_total" || exit 1

# 6. Error rate check
ERROR_RATE=$(curl -s "http://localhost:9090/api/v1/query?query=rate(http_requests_total{status=~'5..'}[5m])" | jq '.data.result[0].value[1]')
if (( $(echo "$ERROR_RATE > 0.05" | bc -l) )); then
  echo "ERROR: High error rate detected: $ERROR_RATE"
  exit 1
fi

echo "=== ALL CHECKS PASSED ==="
```

### Functional Verification

| Test | Command | Expected Result |
|------|---------|-----------------|
| Login | `curl -X POST /api/v1/auth/login` | 200 OK |
| List Checks | `curl /api/v1/checks` | 200 OK with data |
| Make Decision | `curl -X POST /api/v1/decisions` | 200/201 OK |
| View Audit | `curl /api/v1/audit` | 200 OK |

### Monitoring Verification

- [ ] Prometheus scraping all targets
- [ ] Grafana dashboards loading
- [ ] Alertmanager receiving alerts
- [ ] Error rate below 1%
- [ ] Response time P95 below 500ms

---

## Rollback Runbook Template

```markdown
## Rollback Runbook: [Issue Description]

**Date**: YYYY-MM-DD
**Severity**: High/Critical
**Lead**: [Name]

### Issue Summary
[Brief description of the issue requiring rollback]

### Impact
- [ ] Authentication affected
- [ ] Check processing affected
- [ ] Audit logging affected
- [ ] Data integrity affected

### Rollback Steps
1. [ ] Stop affected services
2. [ ] Restore previous version/data
3. [ ] Verify restoration
4. [ ] Restart services
5. [ ] Verify functionality

### Verification Results
| Check | Result | Notes |
|-------|--------|-------|
| Health endpoint | | |
| Login | | |
| Check listing | | |
| Decision making | | |

### Timeline
- HH:MM - Issue detected
- HH:MM - Rollback initiated
- HH:MM - Rollback completed
- HH:MM - Verification completed

### Post-Mortem Actions
- [ ] Document root cause
- [ ] Update procedures if needed
- [ ] Schedule follow-up
```

---

## Contact Information

| Role | Contact | Escalation |
|------|---------|------------|
| On-Call Engineer | pager@example.com | 5 min |
| Database Admin | dba@example.com | 15 min |
| Security Team | security@example.com | Immediate |
| Management | management@example.com | 30 min |

---

*Last Updated: 2026-01-15*
*Document Version: 1.0*
