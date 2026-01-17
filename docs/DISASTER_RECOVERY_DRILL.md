# Disaster Recovery Drill Guide

This document provides a comprehensive guide for conducting disaster recovery (DR) drills for the Check Review Console. Regular DR drills ensure the team is prepared for actual incidents and validate recovery procedures.

## Table of Contents
- [Overview](#overview)
- [Pre-Drill Checklist](#pre-drill-checklist)
- [Drill Scenarios](#drill-scenarios)
- [Execution Procedures](#execution-procedures)
- [Post-Drill Analysis](#post-drill-analysis)
- [Drill Schedule](#drill-schedule)

---

## Overview

### Purpose

Disaster recovery drills serve to:
- Validate backup and recovery procedures
- Train team members on emergency response
- Identify gaps in documentation and tooling
- Meet SOC2 compliance requirements for business continuity
- Measure Recovery Time Objective (RTO) and Recovery Point Objective (RPO)

### Recovery Objectives

| Metric | Target | Maximum |
|--------|--------|---------|
| RTO (Recovery Time Objective) | 1 hour | 4 hours |
| RPO (Recovery Point Objective) | 15 minutes | 1 hour |
| MTTR (Mean Time To Recovery) | 30 minutes | 2 hours |

### Drill Types

1. **Tabletop Exercise** - Discussion-based, no actual system changes
2. **Partial Drill** - Test specific components (e.g., database restore)
3. **Full Drill** - Complete failover to DR environment
4. **Unannounced Drill** - Surprise drill to test actual readiness

---

## Pre-Drill Checklist

### 1 Week Before

- [ ] Schedule drill with all participants
- [ ] Notify stakeholders of potential service impact
- [ ] Verify backup systems are current
- [ ] Review and update runbooks
- [ ] Prepare DR environment (if applicable)
- [ ] Confirm rollback procedures

### 1 Day Before

- [ ] Create fresh backup of production data
- [ ] Verify DR environment connectivity
- [ ] Confirm all team members are available
- [ ] Prepare monitoring dashboards
- [ ] Set up communication channels
- [ ] Brief the team on drill objectives

### Day of Drill

- [ ] Final backup verification
- [ ] Start screen recording (for training)
- [ ] Open incident communication channel
- [ ] Verify monitoring is active
- [ ] Begin timing when drill starts

---

## Drill Scenarios

### Scenario 1: Database Failure

**Objective**: Recover from complete database failure

**Simulated Failure**:
```bash
# DRILL ONLY - Stop database container
docker-compose stop db
```

**Recovery Steps**:
1. Detect failure via monitoring
2. Attempt database restart
3. If restart fails, restore from backup
4. Verify data integrity
5. Resume application

**Success Criteria**:
- [ ] Database restored within RTO
- [ ] No data loss beyond RPO
- [ ] All application functions operational

### Scenario 2: Application Crash

**Objective**: Recover from backend service failure

**Simulated Failure**:
```bash
# DRILL ONLY - Kill backend process
docker-compose stop backend
# Or simulate memory exhaustion
docker update --memory 100m check_review_backend
```

**Recovery Steps**:
1. Detect via health check failures
2. Attempt service restart
3. If restart fails, deploy from last known good image
4. Verify API endpoints
5. Monitor for stability

**Success Criteria**:
- [ ] Service restored within 15 minutes
- [ ] No data loss
- [ ] Error rate returns to normal

### Scenario 3: Data Center Failover

**Objective**: Complete failover to DR site

**Prerequisites**:
- DR environment pre-configured
- DNS TTL reduced to 60 seconds
- Replication lag monitored

**Recovery Steps**:
1. Declare disaster
2. Stop replication to DR
3. Promote DR database to primary
4. Update DNS/load balancer
5. Verify all services on DR site
6. Notify users of potential brief outage

**Success Criteria**:
- [ ] Full failover within 1 hour
- [ ] Data loss within RPO
- [ ] All functionality operational

### Scenario 4: Security Breach Response

**Objective**: Respond to simulated security incident

**Simulated Event**:
- Unauthorized access attempt detected
- Suspicious data export request
- Potential data exfiltration

**Response Steps**:
1. Detect anomaly via SIEM
2. Initiate incident response
3. Isolate affected systems
4. Preserve evidence
5. Assess scope of breach
6. Execute breach notification workflow

**Success Criteria**:
- [ ] Detection within 15 minutes
- [ ] Initial response within 30 minutes
- [ ] Containment within 1 hour

### Scenario 5: Ransomware Recovery

**Objective**: Recover from simulated ransomware attack

**Simulated Event**:
- Systems appear encrypted (simulated)
- Recovery from offline backups required

**Recovery Steps**:
1. Isolate infected systems
2. Assess backup integrity
3. Provision clean environment
4. Restore from air-gapped backup
5. Verify no persistence
6. Resume operations

**Success Criteria**:
- [ ] Clean recovery within 4 hours
- [ ] No data loss beyond daily backup
- [ ] No reinfection detected

---

## Execution Procedures

### Starting the Drill

```bash
#!/bin/bash
# start_dr_drill.sh

DRILL_ID="DR-$(date +%Y%m%d-%H%M%S)"
DRILL_LOG="/var/log/dr-drills/${DRILL_ID}.log"

echo "=== DISASTER RECOVERY DRILL STARTED ===" | tee $DRILL_LOG
echo "Drill ID: $DRILL_ID" | tee -a $DRILL_LOG
echo "Start Time: $(date -u +"%Y-%m-%d %H:%M:%S UTC")" | tee -a $DRILL_LOG
echo "Scenario: $1" | tee -a $DRILL_LOG
echo "==========================================" | tee -a $DRILL_LOG

# Record initial state
echo "Recording initial system state..." | tee -a $DRILL_LOG
docker-compose ps >> $DRILL_LOG 2>&1
curl -s http://localhost:8000/health >> $DRILL_LOG 2>&1

# Export drill ID for other scripts
export DRILL_ID
echo $DRILL_ID > /tmp/current_drill_id
```

### Database Recovery Drill

```bash
#!/bin/bash
# drill_database_recovery.sh

source /tmp/current_drill_id 2>/dev/null || DRILL_ID="manual"
LOG="/var/log/dr-drills/${DRILL_ID}-db.log"

echo "=== DATABASE RECOVERY DRILL ===" | tee $LOG
START_TIME=$(date +%s)

# Step 1: Simulate failure
echo "[$(date +%H:%M:%S)] Simulating database failure..." | tee -a $LOG
docker-compose stop db

# Step 2: Wait for detection
echo "[$(date +%H:%M:%S)] Waiting for monitoring detection..." | tee -a $LOG
sleep 30

# Step 3: Verify failure detected
ALERT_COUNT=$(curl -s "http://localhost:9093/api/v2/alerts" | jq 'length')
echo "[$(date +%H:%M:%S)] Alerts triggered: $ALERT_COUNT" | tee -a $LOG

# Step 4: Execute recovery
echo "[$(date +%H:%M:%S)] Starting database recovery..." | tee -a $LOG
docker-compose up -d db
sleep 10

# Step 5: Restore from backup if needed
if ! docker exec check_review_db pg_isready -U postgres; then
    echo "[$(date +%H:%M:%S)] Primary start failed, restoring from backup..." | tee -a $LOG
    LATEST_BACKUP=$(ls -t /backups/*.dump 2>/dev/null | head -1)
    if [ -n "$LATEST_BACKUP" ]; then
        docker-compose down db
        docker volume rm check_postgres_data
        docker-compose up -d db
        sleep 10
        docker exec -i check_review_db pg_restore -U postgres -d check_review < $LATEST_BACKUP
    fi
fi

# Step 6: Verify recovery
echo "[$(date +%H:%M:%S)] Verifying database recovery..." | tee -a $LOG
docker exec check_review_db psql -U postgres -d check_review -c "SELECT count(*) FROM check_items;" | tee -a $LOG

# Step 7: Restart application
echo "[$(date +%H:%M:%S)] Restarting application..." | tee -a $LOG
docker-compose restart backend

# Step 8: Final verification
sleep 10
if curl -sf http://localhost:8000/health; then
    echo "[$(date +%H:%M:%S)] DRILL SUCCESSFUL" | tee -a $LOG
else
    echo "[$(date +%H:%M:%S)] DRILL FAILED - Manual intervention required" | tee -a $LOG
fi

END_TIME=$(date +%s)
RECOVERY_TIME=$((END_TIME - START_TIME))
echo "[$(date +%H:%M:%S)] Total recovery time: ${RECOVERY_TIME} seconds" | tee -a $LOG
```

### Verification Script

```bash
#!/bin/bash
# verify_recovery.sh

echo "=== RECOVERY VERIFICATION ==="

# 1. Service Health
echo -n "Backend API: "
curl -sf http://localhost:8000/health && echo "OK" || echo "FAIL"

echo -n "Database: "
docker exec check_review_db pg_isready -U postgres && echo "OK" || echo "FAIL"

echo -n "Redis: "
docker exec check_review_redis redis-cli ping && echo "OK" || echo "FAIL"

# 2. Data Integrity
echo ""
echo "=== DATA INTEGRITY CHECKS ==="
echo -n "Check Items: "
docker exec check_review_db psql -U postgres -d check_review -t -c "SELECT count(*) FROM check_items;"

echo -n "Users: "
docker exec check_review_db psql -U postgres -d check_review -t -c "SELECT count(*) FROM users;"

echo -n "Audit Logs: "
docker exec check_review_db psql -U postgres -d check_review -t -c "SELECT count(*) FROM audit_logs;"

# 3. Functional Tests
echo ""
echo "=== FUNCTIONAL TESTS ==="
echo -n "Authentication: "
curl -sf -X POST http://localhost:8000/api/v1/auth/login \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -d "username=test&password=test" && echo "OK" || echo "FAIL (expected if no test user)"

echo -n "Check List: "
curl -sf http://localhost:8000/api/v1/checks -H "Authorization: Bearer test" && echo "OK" || echo "FAIL (expected without auth)"

# 4. Metrics
echo ""
echo "=== METRICS ==="
echo -n "Prometheus: "
curl -sf http://localhost:9090/-/healthy && echo "OK" || echo "FAIL"

echo -n "Backend Metrics: "
curl -sf http://localhost:8000/metrics | head -1 && echo "... OK" || echo "FAIL"
```

---

## Post-Drill Analysis

### Metrics to Capture

| Metric | Target | Actual | Status |
|--------|--------|--------|--------|
| Detection Time | < 5 min | | |
| Response Time | < 15 min | | |
| Recovery Time | < 60 min | | |
| Data Loss | < 15 min | | |
| Team Communication | Effective | | |

### Drill Report Template

```markdown
# DR Drill Report

**Drill ID**: DR-YYYYMMDD-HHMMSS
**Date**: YYYY-MM-DD
**Duration**: HH:MM
**Scenario**: [Scenario Name]
**Lead**: [Name]

## Executive Summary
[2-3 sentence summary of drill outcome]

## Timeline
| Time | Event |
|------|-------|
| HH:MM | Drill started |
| HH:MM | Failure simulated |
| HH:MM | Failure detected |
| HH:MM | Recovery initiated |
| HH:MM | Recovery completed |
| HH:MM | Verification completed |

## Results

### Objectives Met
- [ ] RTO achieved (target: 1 hour)
- [ ] RPO achieved (target: 15 min)
- [ ] All services restored
- [ ] No data corruption

### Issues Identified
1. [Issue 1]
2. [Issue 2]

### Lessons Learned
1. [Lesson 1]
2. [Lesson 2]

## Action Items
| Action | Owner | Due Date |
|--------|-------|----------|
| | | |

## Recommendations
1. [Recommendation]
```

---

## Drill Schedule

### Quarterly Drill Calendar

| Quarter | Drill Type | Scenario | Date |
|---------|------------|----------|------|
| Q1 | Full | Database Failure | January |
| Q2 | Partial | Application Crash | April |
| Q3 | Full | Data Center Failover | July |
| Q4 | Tabletop | Security Breach | October |

### Annual Requirements (SOC2)

- [ ] Minimum 4 DR drills per year
- [ ] At least 1 full failover drill
- [ ] All critical team members participate
- [ ] Document all drill results
- [ ] Review and update procedures after each drill

---

## Appendix: Quick Reference

### Emergency Contacts

| Role | Name | Phone | Email |
|------|------|-------|-------|
| DR Lead | | | |
| DBA | | | |
| Security | | | |
| Management | | | |

### Key Locations

| Resource | Location |
|----------|----------|
| Backups | /backups/ or S3://backup-bucket |
| DR Environment | dr.example.com |
| Runbooks | /docs/runbooks/ |
| Logs | /var/log/check-review/ |

### Recovery Commands Cheat Sheet

```bash
# Quick database restore
pg_restore -h localhost -U postgres -d check_review /backups/latest.dump

# Quick application rollback
git checkout $(cat /var/rollback/last_stable_tag) && docker-compose up -d

# Quick health check
curl http://localhost:8000/health && docker-compose ps
```

---

*Last Updated: 2024-01-15*
*Document Version: 1.0*
