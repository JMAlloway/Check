# Incident Response Runbook

## Check Review Console - Security Incident Procedures

**Document Version:** 1.0
**Last Updated:** 2026-01-15
**Classification:** Internal Use Only

---

## Quick Reference

| Severity | Response Time | Escalation |
|----------|---------------|------------|
| **SEV-1** (Breach/Outage) | 15 min | Immediate: Security Lead + Exec |
| **SEV-2** (Degraded) | 1 hour | Security Lead |
| **SEV-3** (Minor) | 4 hours | On-call Engineer |
| **SEV-4** (Low) | Next business day | Ticket queue |

**Emergency Contacts:**
- Security Lead: [PHONE]
- Engineering Manager: [PHONE]
- Executive Sponsor: [PHONE]
- Legal Counsel: [PHONE]

---

## 1. Incident Detection

### 1.1 Detection Sources

| Source | Alert Type | Response |
|--------|------------|----------|
| SIEM alerts | Cross-tenant access, auth anomalies | Immediate investigation |
| Monitoring | Error rate spike, latency | Check dashboards, logs |
| User reports | Unable to access, strange behavior | Verify and triage |
| Security scans | Vulnerability detected | Assess and patch |
| External report | Bug bounty, disclosure | Security lead review |

### 1.2 Initial Assessment Questions

1. **What is the scope?** Single user, tenant, or system-wide?
2. **Is data affected?** Any potential exposure of PII/financial data?
3. **Is it ongoing?** Active attack or historical incident?
4. **What systems?** Frontend, backend, database, infrastructure?
5. **Who reported?** Internal monitoring, user, or external?

---

## 2. Incident Classification

### SEV-1: Critical (Security Breach / Complete Outage)

**Indicators:**
- Confirmed unauthorized data access
- Credential compromise
- Complete system unavailability
- Active attack in progress
- Cross-tenant data exposure

**Response:** 15 minutes
**Team:** Full incident team + executives
**Communication:** Customer notification may be required

### SEV-2: High (Partial Outage / Security Degradation)

**Indicators:**
- Authentication system issues
- Single tenant affected
- High error rate (>5%)
- Security control bypass suspected
- Significant performance degradation

**Response:** 1 hour
**Team:** On-call + Security Lead
**Communication:** Internal stakeholders

### SEV-3: Moderate (Minor Issue / Workaround Available)

**Indicators:**
- Single feature broken
- Performance degradation (<5% error rate)
- Non-critical security finding
- Affecting small user subset

**Response:** 4 hours
**Team:** On-call engineer
**Communication:** Team channel

### SEV-4: Low (Minimal Impact)

**Indicators:**
- Cosmetic issues
- Documentation errors
- Minor bugs with easy workaround

**Response:** Next business day
**Team:** Standard ticket queue
**Communication:** None required

---

## 3. Response Procedures

### 3.1 SEV-1 Response Checklist

```
□ 1. Acknowledge alert (within 5 min)
□ 2. Create incident channel: #incident-YYYY-MM-DD-brief-desc
□ 3. Page Security Lead and Engineering Manager
□ 4. Assess: What, Who, When, How, Scope
□ 5. Containment decision (see 3.2)
□ 6. Document timeline in incident channel
□ 7. 15-min status updates until resolved
□ 8. Notify executive sponsor (within 30 min)
□ 9. Legal consultation if data breach confirmed
□ 10. Customer communication plan (if needed)
□ 11. Preserve evidence (logs, snapshots)
□ 12. Post-incident review scheduled
```

### 3.2 Containment Actions

**Immediate containment options:**

| Action | When to Use | Command/Procedure |
|--------|-------------|-------------------|
| Block IP | Active attack from specific IP | Update WAF rules |
| Disable user | Compromised account | `UPDATE users SET is_active=false WHERE id='...'` |
| Rotate secrets | Credential exposure | Redeploy with new secrets |
| Enable maintenance mode | System-wide issue | Set `MAINTENANCE_MODE=true` |
| Isolate tenant | Tenant-specific breach | Disable tenant in config |
| Database failover | Primary compromise | Promote replica, isolate primary |
| Full shutdown | Severe ongoing attack | `docker-compose down` |

### 3.3 Evidence Preservation

**Before making changes, capture:**

```bash
# Capture current state
docker-compose logs --timestamps > incident_logs_$(date +%Y%m%d_%H%M%S).txt

# Database snapshot
pg_dump -h localhost -U check_user check_db > db_snapshot_$(date +%Y%m%d_%H%M%S).sql

# Export security events
psql -c "COPY (SELECT * FROM audit_logs WHERE created_at > NOW() - INTERVAL '24 hours') TO STDOUT WITH CSV HEADER" > audit_export.csv

# System state
docker ps -a > docker_state.txt
netstat -tuln > network_state.txt
```

### 3.4 Communication Templates

**Internal Status Update:**
```
INCIDENT UPDATE - [SEV-X] [Brief Description]
Time: [UTC timestamp]
Status: [Investigating/Identified/Mitigating/Resolved]
Impact: [Description of user impact]
Next update: [Time]
Actions taken: [List]
Next steps: [List]
```

**Customer Notification (if required):**
```
Subject: Security Notice - [Company Name]

Dear Customer,

We are writing to inform you of a security incident that occurred on [date].

What happened: [Brief, factual description]

What information was involved: [Specific data types]

What we are doing: [Actions taken]

What you can do: [Recommended actions]

For questions: [Contact information]

We sincerely apologize for any inconvenience.
```

---

## 4. Specific Incident Playbooks

### 4.1 Suspected Credential Compromise

```
1. Identify affected account(s)
2. Disable affected account(s) immediately
3. Revoke all active sessions:
   DELETE FROM refresh_tokens WHERE user_id = '[user_id]';
4. Review audit logs for unauthorized actions:
   SELECT * FROM audit_logs WHERE user_id = '[user_id]'
   ORDER BY created_at DESC LIMIT 100;
5. Check for privilege escalation attempts
6. Force password reset on account restoration
7. Enable MFA if not already required
8. Review access logs for lateral movement
```

### 4.2 Cross-Tenant Data Access

```
1. CRITICAL: This is a SEV-1 by default
2. Immediately identify scope:
   - Which tenants affected?
   - What data was accessed?
   - How was isolation bypassed?
3. Capture evidence before any changes
4. Isolate affected systems if attack ongoing
5. Review code for isolation bypass
6. Audit all cross-tenant security events:
   grep "security.access.cross_tenant" /var/log/app/*.log
7. Prepare breach notification if PII accessed
8. Legal review required
```

### 4.3 Database Breach

```
1. Isolate database server (network level if needed)
2. Capture current connections:
   SELECT * FROM pg_stat_activity;
3. Revoke suspicious connections:
   SELECT pg_terminate_backend(pid) FROM pg_stat_activity
   WHERE ... ;
4. Rotate all database credentials
5. Review pg_audit logs for queries
6. Check for data exfiltration
7. Restore from known-good backup if needed
8. Forensic analysis of compromised system
```

### 4.4 Image Token Replay Attack

```
1. Check if tokens are being reused:
   SELECT * FROM image_access_tokens
   WHERE used_at IS NOT NULL
   ORDER BY used_at DESC LIMIT 100;
2. Look for rapid token creation/use patterns
3. If one-time enforcement failed:
   - Check for race condition in code
   - Review database transaction isolation
4. Temporarily disable image token endpoint if active attack
5. Review middleware for proper atomic operations
```

### 4.5 DDoS/High Traffic Attack

```
1. Enable rate limiting at WAF level
2. Scale up infrastructure if legitimate traffic
3. Identify attack patterns:
   - Source IPs
   - Request patterns
   - Target endpoints
4. Block malicious IPs at network edge
5. Enable challenge pages (CAPTCHA) if available
6. Contact CDN/hosting provider for assistance
7. Monitor for application-layer attacks hiding in traffic
```

---

## 5. Recovery Procedures

### 5.1 Service Restoration Checklist

```
□ Incident contained (no ongoing attack)
□ Root cause identified
□ Fix deployed or workaround in place
□ All compromised credentials rotated
□ Affected data identified and secured
□ Monitoring enhanced for recurrence
□ Smoke tests passing
□ Customer communication sent (if applicable)
□ Incident channel archived
□ Post-incident review scheduled
```

### 5.2 Post-Incident Review (PIR)

**Schedule:** Within 72 hours of resolution

**Attendees:** All incident responders + relevant stakeholders

**Agenda:**
1. Timeline reconstruction (blameless)
2. What went well?
3. What could be improved?
4. Root cause analysis (5 Whys)
5. Action items with owners and deadlines
6. Update runbooks if needed
7. Training needs identified

**PIR Document Template:**

```markdown
# Post-Incident Review: [Incident Title]

**Date:** [Date]
**Duration:** [Start - End]
**Severity:** [SEV-X]
**Author:** [Name]

## Summary
[2-3 sentence summary]

## Timeline
| Time (UTC) | Event |
|------------|-------|
| HH:MM | ... |

## Impact
- Users affected: [number]
- Duration: [time]
- Data affected: [yes/no, details]

## Root Cause
[Description using 5 Whys analysis]

## What Went Well
- [Item]

## What Could Be Improved
- [Item]

## Action Items
| Action | Owner | Due Date | Status |
|--------|-------|----------|--------|
| ... | ... | ... | ... |

## Lessons Learned
[Key takeaways]
```

---

## 6. Regulatory Notifications

### 6.1 Breach Notification Requirements

| Regulation | Threshold | Timeline | Authority |
|------------|-----------|----------|-----------|
| State breach laws | PII of residents | 30-72 hours (varies) | State AG |
| GLBA | Customer financial data | ASAP | Banking regulator |
| GDPR (if applicable) | EU resident data | 72 hours | Data Protection Authority |

### 6.2 Notification Decision Tree

```
Data breach confirmed?
├── No → Document, continue monitoring
└── Yes → What data?
    ├── No PII → Internal report only
    └── PII involved?
        ├── Encrypted at rest → Risk assessment
        └── Unencrypted → Notification likely required
            └── Consult Legal within 24 hours
```

---

## 7. Training and Drills

### 7.1 Incident Response Drills

| Drill Type | Frequency | Participants |
|------------|-----------|--------------|
| Tabletop exercise | Quarterly | Full team |
| On-call handoff drill | Monthly | On-call rotation |
| Backup restore test | Monthly | DBA + Ops |
| Full DR failover | Semi-annually | Full team |

### 7.2 Drill Scenarios

1. **Credential compromise:** Simulated admin account breach
2. **Data exfiltration:** Unusual data export patterns detected
3. **Service outage:** Database unavailable
4. **Ransomware:** Simulated encryption attack
5. **Insider threat:** Suspicious admin activity

---

## Appendix A: Quick Commands

```bash
# View recent security events
docker-compose logs backend | grep "security\." | tail -100

# Check active sessions
psql -c "SELECT user_id, created_at FROM refresh_tokens WHERE expires_at > NOW();"

# View failed login attempts (last hour)
docker-compose logs backend | grep "login_failure" | grep "$(date -u +%Y-%m-%dT%H)"

# Emergency: Disable all non-admin users
psql -c "UPDATE users SET is_active = false WHERE NOT is_superuser;"

# Emergency: Clear all sessions
psql -c "DELETE FROM refresh_tokens;"

# Check database connections
psql -c "SELECT count(*), state FROM pg_stat_activity GROUP BY state;"
```

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-01-15 | Security Team | Initial release |
