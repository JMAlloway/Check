# SOC2 Operational Controls

## Check Review Console - Security & Compliance Framework

**Document Version:** 1.0
**Last Updated:** 2026-01-15
**Classification:** Internal / Auditor Use

---

## Table of Contents

1. [Security Controls](#1-security-controls)
2. [Monitoring & Logging](#2-monitoring--logging)
3. [Incident Response](#3-incident-response)
4. [Vulnerability Management](#4-vulnerability-management)
5. [Change Management](#5-change-management)
6. [Access Control](#6-access-control)
7. [Business Continuity](#7-business-continuity)
8. [Vendor Management](#8-vendor-management)

---

## 1. Security Controls

### 1.1 Authentication & Authorization

| Control ID | Control | Implementation | Evidence |
|------------|---------|----------------|----------|
| SEC-001 | Multi-factor authentication for privileged users | TOTP-based MFA via `pyotp` library | `app/core/mfa.py`, User model `mfa_secret` field |
| SEC-002 | Session management with secure tokens | JWT access tokens (15min TTL) + httpOnly refresh cookies | `app/core/security.py`, `app/api/v1/endpoints/auth.py` |
| SEC-003 | Role-based access control (RBAC) | Granular permissions via Role/Permission models | `app/models/user.py`, `app/api/deps.py` |
| SEC-004 | Password policy enforcement | Minimum 12 chars, complexity requirements | `app/core/security.py` |
| SEC-005 | Account lockout after failed attempts | 5 failed attempts triggers 15-minute lockout | Rate limiting via `slowapi` |

### 1.2 Data Protection

| Control ID | Control | Implementation | Evidence |
|------------|---------|----------------|----------|
| SEC-010 | Encryption at rest | PostgreSQL with encrypted storage, AES-256 | Database configuration |
| SEC-011 | Encryption in transit | TLS 1.2+ required, strong cipher suites | `nginx.pilot.conf` |
| SEC-012 | Sensitive data masking | Account numbers masked in API responses | `CheckItemResponse` schema |
| SEC-013 | MICR/PII not logged | Token redaction filters on all loggers | `app/core/middleware.py` |
| SEC-014 | One-time image access tokens | UUID tokens, single-use, 90s TTL | `app/models/image_token.py` |

### 1.3 Network Security

| Control ID | Control | Implementation | Evidence |
|------------|---------|----------------|----------|
| SEC-020 | HTTPS enforcement | HTTP 301 redirect to HTTPS | `nginx.pilot.conf` |
| SEC-021 | Security headers | HSTS, X-Frame-Options, CSP | `nginx.pilot.conf` |
| SEC-022 | Rate limiting | Per-IP and per-user limits | `slowapi` configuration |
| SEC-023 | API authentication required | All endpoints except health require JWT | `app/api/deps.py` |

### 1.4 Tenant Isolation

| Control ID | Control | Implementation | Evidence |
|------------|---------|----------------|----------|
| SEC-030 | Tenant-scoped queries | All database queries filter by tenant_id | `app/api/deps.py:get_tenant_id()` |
| SEC-031 | Cross-tenant access logging | Security events logged for cross-tenant attempts | `app/api/deps.py:log_cross_tenant_attempt()` |
| SEC-032 | Tenant validation on all endpoints | Middleware validates tenant ownership | Integration tests |

---

## 2. Monitoring & Logging

### 2.1 Application Logging

| Log Type | Contents | Retention | Location |
|----------|----------|-----------|----------|
| Access logs | HTTP requests, response codes, latency | 90 days | `/var/log/nginx/access.log` (JSON) |
| Application logs | Business events, errors, warnings | 90 days | Container stdout → log aggregator |
| Security logs | Auth events, access denials, anomalies | 1 year | `audit_logs` table + SIEM export |
| Audit trail | All check decisions, user actions | 7 years | `audit_logs` table |

### 2.2 Security Event Logging

All security-relevant events are logged with structured data:

```json
{
  "timestamp": "2026-01-15T12:00:00Z",
  "event_type": "security.auth.login_success",
  "severity": "info",
  "user_id": "uuid",
  "tenant_id": "uuid",
  "ip_address": "192.168.1.1",
  "user_agent": "Mozilla/5.0...",
  "details": {}
}
```

**Security Events Captured:**

| Event Type | Trigger | Severity |
|------------|---------|----------|
| `security.auth.login_success` | Successful login | info |
| `security.auth.login_failure` | Failed login attempt | warning |
| `security.auth.logout` | User logout | info |
| `security.auth.token_refresh` | Token refresh | info |
| `security.auth.mfa_required` | MFA challenge issued | info |
| `security.auth.mfa_failure` | MFA verification failed | warning |
| `security.access.denied` | Authorization denied | warning |
| `security.access.cross_tenant` | Cross-tenant access attempt | critical |
| `security.image.token_created` | Image access token minted | info |
| `security.image.token_used` | Image access token consumed | info |
| `security.image.token_expired` | Expired token access attempt | warning |
| `security.rate.limit_exceeded` | Rate limit triggered | warning |

### 2.3 Health Monitoring

**Health Check Endpoints:**

| Endpoint | Purpose | Frequency |
|----------|---------|-----------|
| `GET /health` | Basic liveness | Every 10s |
| `GET /api/v1/health` | API readiness | Every 30s |
| `GET /health` (nginx) | Load balancer health | Every 5s |

**Monitored Metrics:**

- Response time (p50, p95, p99)
- Error rate (5xx responses)
- Database connection pool utilization
- Redis connection status
- Active user sessions
- Queue depths (pending checks)

### 2.4 Alerting Thresholds

| Metric | Warning | Critical | Notification |
|--------|---------|----------|--------------|
| Error rate (5xx) | > 1% | > 5% | PagerDuty |
| Response time p95 | > 2s | > 5s | Slack |
| Failed logins (per IP) | > 5/min | > 20/min | SIEM + Slack |
| Cross-tenant attempts | Any | Any | PagerDuty (immediate) |
| Database connections | > 80% | > 95% | PagerDuty |
| Disk usage | > 80% | > 90% | Slack |

---

## 3. Incident Response

### 3.1 Incident Classification

| Severity | Definition | Response Time | Examples |
|----------|------------|---------------|----------|
| **SEV-1** | Security breach, data exposure, complete outage | 15 minutes | Unauthorized data access, credential compromise |
| **SEV-2** | Partial outage, degraded security | 1 hour | Authentication system down, high error rate |
| **SEV-3** | Minor issue, workaround available | 4 hours | Single feature broken, performance degradation |
| **SEV-4** | Low impact, cosmetic | Next business day | UI glitches, non-critical bugs |

### 3.2 Incident Response Procedures

See: [INCIDENT_RESPONSE.md](./INCIDENT_RESPONSE.md)

**Key Contacts:**

| Role | Responsibility | Escalation Time |
|------|----------------|-----------------|
| On-call Engineer | Initial triage, containment | Immediate |
| Security Lead | Security incidents, forensics | 15 min (SEV-1/2) |
| Engineering Manager | Resource allocation, communication | 30 min (SEV-1) |
| Executive Sponsor | Customer communication, legal | 1 hour (SEV-1) |

### 3.3 Post-Incident Review

All SEV-1 and SEV-2 incidents require:

1. **Incident Timeline** - Minute-by-minute reconstruction
2. **Root Cause Analysis** - 5 Whys methodology
3. **Action Items** - Preventive measures with owners/dates
4. **Customer Communication** - If data was affected
5. **Lessons Learned** - Team retrospective

---

## 4. Vulnerability Management

### 4.1 Dependency Scanning

| Tool | Scope | Frequency | Action Threshold |
|------|-------|-----------|------------------|
| `pip-audit` | Python dependencies | Daily (CI) | Critical: 24h, High: 7d |
| `npm audit` | Node.js dependencies | Daily (CI) | Critical: 24h, High: 7d |
| Dependabot | All dependencies | Continuous | Auto-PR for patches |
| Container scan | Docker images | On build | Block deployment if critical |

### 4.2 Security Patching SLAs

| Severity | Patch Timeline | Testing Required |
|----------|----------------|------------------|
| Critical (CVSS 9.0+) | 24 hours | Smoke test only |
| High (CVSS 7.0-8.9) | 7 days | Full regression |
| Medium (CVSS 4.0-6.9) | 30 days | Full regression |
| Low (CVSS < 4.0) | Next release | Standard QA |

### 4.3 Penetration Testing

| Test Type | Frequency | Performed By | Scope |
|-----------|-----------|--------------|-------|
| Automated DAST | Weekly | Internal (OWASP ZAP) | OWASP Top 10 |
| Manual pentest | Annually | Third-party firm | Full application |
| Red team exercise | Annually | Third-party firm | Infrastructure + social |

### 4.4 Vulnerability Disclosure

- **Security contact:** security@[company].com
- **PGP key:** Available at /.well-known/security.txt
- **Response SLA:** Acknowledge within 48 hours
- **Coordinated disclosure:** 90-day window

---

## 5. Change Management

### 5.1 Code Review Requirements

| Change Type | Required Reviewers | Approval |
|-------------|-------------------|----------|
| Feature code | 1 engineer | PR approval |
| Security-sensitive | 1 engineer + security lead | 2 approvals |
| Database migration | 1 engineer + DBA | 2 approvals |
| Infrastructure | 1 engineer + ops lead | 2 approvals |
| Emergency hotfix | Post-hoc review within 24h | Manager approval |

### 5.2 Deployment Process

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   PR Open   │───▶│  CI Tests   │───▶│   Review    │───▶│   Merge     │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
                                                               │
                                                               ▼
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│ Production  │◀───│   Canary    │◀───│   Staging   │◀───│    Build    │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
```

**Deployment Gates:**

1. All CI tests pass
2. Security scan clean (no critical/high vulns)
3. Code review approved
4. Staging smoke tests pass
5. Canary metrics healthy (15 min)

### 5.3 Rollback Procedures

| Scenario | Procedure | RTO |
|----------|-----------|-----|
| Bad deployment | Revert to previous container image | < 5 min |
| Database migration issue | Run downgrade migration | < 15 min |
| Configuration error | Restore from config backup | < 5 min |
| Complete failure | Restore from backup + replay logs | < 4 hours |

---

## 6. Access Control

### 6.1 User Provisioning

| Step | Owner | SLA |
|------|-------|-----|
| Access request | Employee + Manager | N/A |
| Security review | Security team | 1 business day |
| Account creation | IT Operations | 1 business day |
| Role assignment | Application admin | 1 business day |
| MFA enrollment | Employee (self-service) | Before first login |

### 6.2 Privileged Access

| Role | Access Level | Additional Controls |
|------|--------------|---------------------|
| Developer | Read-only prod logs | MFA required, audit logged |
| DBA | Database admin | MFA required, session recorded |
| SRE | Full infrastructure | MFA required, break-glass audit |
| Security | Security tools | MFA required, dual approval |

### 6.3 Access Reviews

| Review Type | Frequency | Owner |
|-------------|-----------|-------|
| User access recertification | Quarterly | Managers |
| Privileged access review | Monthly | Security team |
| Service account review | Quarterly | IT Operations |
| Terminated user audit | Weekly | HR + IT |

### 6.4 Separation of Duties

| Action | Requires |
|--------|----------|
| Approve check > $50,000 | Different user than reviewer |
| Deploy to production | Different user than code author |
| Create privileged user | Security team approval |
| Modify audit logs | Not permitted (append-only) |

---

## 7. Business Continuity

### 7.1 Backup Strategy

| Data | Frequency | Retention | Location |
|------|-----------|-----------|----------|
| Database (full) | Daily | 30 days | Encrypted S3, cross-region |
| Database (WAL) | Continuous | 7 days | Encrypted S3 |
| Configuration | On change | 90 days | Git repository |
| Audit logs | Real-time | 7 years | Separate storage account |

### 7.2 Recovery Objectives

| Metric | Target | Tested |
|--------|--------|--------|
| RPO (Recovery Point Objective) | 1 hour | Quarterly |
| RTO (Recovery Time Objective) | 4 hours | Quarterly |
| MTTR (Mean Time to Recovery) | < 1 hour | Monthly metrics |

### 7.3 Disaster Recovery

**DR Site:** Warm standby in separate region

| Component | DR Strategy | Failover Time |
|-----------|-------------|---------------|
| Database | Async replica, promote on failover | 15 minutes |
| Application | Container images replicated | 10 minutes |
| Load balancer | DNS failover | 5 minutes (TTL) |
| Static assets | CDN with origin failover | Automatic |

### 7.4 DR Testing

| Test Type | Frequency | Scope |
|-----------|-----------|-------|
| Backup restore | Monthly | Single table restore |
| Failover drill | Quarterly | Full DR site activation |
| Chaos engineering | Monthly | Random component failure |

---

## 8. Vendor Management

### 8.1 Third-Party Services

| Service | Purpose | SOC2 Status | Data Shared |
|---------|---------|-------------|-------------|
| AWS/Azure | Infrastructure | SOC2 Type II | All data (encrypted) |
| PostgreSQL | Database | N/A (self-hosted) | All data |
| Redis | Caching | N/A (self-hosted) | Session data |
| SMTP Provider | Email notifications | SOC2 Type II | Email addresses only |

### 8.2 Vendor Security Requirements

All vendors with access to customer data must:

1. Maintain SOC2 Type II certification (or equivalent)
2. Sign data processing agreement (DPA)
3. Support encryption in transit and at rest
4. Provide breach notification within 72 hours
5. Allow security questionnaire completion annually

---

## Appendices

### A. Compliance Mapping

| Framework | Relevant Controls |
|-----------|-------------------|
| SOC2 CC6.1 | SEC-001 through SEC-005 |
| SOC2 CC6.6 | SEC-010 through SEC-014 |
| SOC2 CC7.2 | Section 2 (Monitoring) |
| SOC2 CC7.3 | Section 3 (Incident Response) |
| SOC2 CC7.4 | Section 4 (Vulnerability Management) |
| SOC2 CC8.1 | Section 5 (Change Management) |
| PCI-DSS 3.4 | SEC-012 (Data Masking) |
| PCI-DSS 8.3 | SEC-001 (MFA) |
| GLBA 501(b) | SEC-030 through SEC-032 (Tenant Isolation) |

### B. Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-01-15 | Security Team | Initial release |

### C. Review Schedule

This document is reviewed:
- **Quarterly:** By security team
- **Annually:** By external auditor
- **On change:** When controls are modified
