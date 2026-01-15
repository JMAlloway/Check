# Regulatory Framework Alignment

This document describes how the Check Review Console aligns with key regulatory frameworks applicable to community banks and financial institutions.

## Table of Contents
- [SOC 2 Type II Alignment](#soc-2-type-ii-alignment)
- [Banking Regulations](#banking-regulations)
- [Data Protection Requirements](#data-protection-requirements)
- [Audit Trail Requirements](#audit-trail-requirements)
- [Security Controls Matrix](#security-controls-matrix)

---

## SOC 2 Type II Alignment

The Check Review Console implements controls aligned with SOC 2 Trust Service Criteria.

### CC6 - Logical and Physical Access Controls

| Control | Implementation | Evidence Location |
|---------|---------------|-------------------|
| CC6.1 - Access to systems | Role-based access control (RBAC) with permissions matrix | `app/core/security.py`, `app/models/user.py` |
| CC6.2 - Access removal | Session revocation, token expiry, account deactivation | `app/services/auth.py` |
| CC6.3 - Authentication | JWT tokens with refresh rotation, MFA support | `app/core/security.py` |
| CC6.6 - Logical access monitoring | Audit logging of all access events | `app/audit/service.py` |
| CC6.7 - Unauthorized access detection | Failed login tracking, IP allowlist violations | `app/services/auth.py` |
| CC6.8 - Access to sensitive data | Field-level PII redaction in audit logs | `app/audit/service.py` |

### CC7 - System Operations

| Control | Implementation | Evidence Location |
|---------|---------------|-------------------|
| CC7.1 - Security event detection | Prometheus alerting, SIEM integration | `docker/prometheus/alerts/` |
| CC7.2 - Incident response | Alertmanager routing, breach notification workflow | `app/security/breach.py` |
| CC7.3 - System anomaly detection | Security event filtering, metrics tracking | `app/core/logging_config.py` |
| CC7.4 - System recovery | Database backups, log retention | `app/audit/retention.py` |

### CC8 - Change Management

| Control | Implementation | Evidence Location |
|---------|---------------|-------------------|
| CC8.1 - Change authorization | Git-based workflow, PR reviews | Repository settings |
| CC8.2 - Change testing | Automated test suite, CI/CD pipeline | `tests/`, GitHub Actions |

### CC9 - Risk Mitigation

| Control | Implementation | Evidence Location |
|---------|---------------|-------------------|
| CC9.1 - Risk identification | Dual control for high-value items | `app/api/v1/endpoints/decisions.py` |
| CC9.2 - Fraud prevention | Fraud intelligence sharing network | `app/services/fraud.py` |

---

## Banking Regulations

### Uniform Commercial Code (UCC) Article 4

**Check Processing Requirements:**

| Requirement | Implementation |
|-------------|---------------|
| Midnight deadline compliance | SLA tracking with breach alerts (`sla_breached` field) |
| Reasonable commercial standards | Configurable review queues and policies |
| Customer notification | Decision status tracking and history |

### Bank Secrecy Act (BSA) / Anti-Money Laundering (AML)

| Requirement | Implementation |
|-------------|---------------|
| Suspicious Activity Reporting | Fraud event creation and tracking |
| Record retention (5+ years) | 7-year audit log retention |
| Customer identification | Account holder verification workflow |

### Regulation CC - Funds Availability

| Requirement | Implementation |
|-------------|---------------|
| Next-day availability tracking | `presented_date` and SLA calculations |
| Exception hold documentation | Decision notes and reason codes |
| Disclosure requirements | Audit trail with full history |

### FFIEC Examination Guidelines

**IT Examination Handbook Alignment:**

| Area | Implementation |
|------|---------------|
| Authentication | Multi-factor authentication support |
| Access Controls | RBAC with permission granularity |
| Audit Trails | Comprehensive, immutable audit logging |
| Vendor Management | Connector abstraction layer |
| Business Continuity | Database replication support |

---

## Data Protection Requirements

### Personally Identifiable Information (PII) Handling

**Data Classification:**

| Category | Examples | Protection |
|----------|----------|------------|
| Sensitive PII | SSN, Account Numbers | Never stored, masked in display |
| Financial Data | Check amounts, balances | Encrypted at rest, audit logged |
| Contact Info | Addresses, phone | Masked in logs, access controlled |
| Authentication | Passwords, MFA secrets | Hashed/encrypted, never logged |

**PII Redaction in Audit Logs:**

```python
# Fields automatically redacted (app/audit/service.py)
PII_FIELDS = {
    "account_number", "routing_number", "ssn",
    "phone", "password", "mfa_secret", ...
}
```

### Data Retention Policies

| Data Type | Retention Period | Justification |
|-----------|-----------------|---------------|
| Audit logs | 7 years | BSA/AML requirements |
| Item views | 90 days | Operational needs |
| User sessions | 90 days | Security monitoring |
| Check images | Per connector policy | Bank-specific |

---

## Audit Trail Requirements

### Audit Log Integrity

**Immutability Controls:**

1. **Database triggers** - Block UPDATE and DELETE on audit_logs
2. **Application controls** - INSERT-only ORM operations
3. **Integrity hashes** - SHA256 checksums for tamper detection
4. **Verification API** - `/api/v1/system/retention/verify-integrity`

### Required Audit Events

| Event Category | Events Logged |
|---------------|---------------|
| Authentication | Login, logout, failed attempts, MFA events |
| Authorization | Permission denials, role changes |
| Data Access | Item views, image access, report exports |
| Decisions | Approvals, returns, rejections, overrides |
| Administrative | User management, policy changes |
| Security | IP violations, suspicious activity |

### Audit Log Structure

```json
{
  "@timestamp": "2024-01-15T12:00:00Z",
  "event_type": "decision.made",
  "user_id": "uuid",
  "action": "decision_made",
  "resource_type": "check_item",
  "resource_id": "uuid",
  "tenant_id": "uuid",
  "ip_address": "192.168.1.1",
  "integrity_hash": "sha256...",
  "before_value": {...},
  "after_value": {...}
}
```

---

## Security Controls Matrix

### Authentication & Authorization

| Control | Status | Notes |
|---------|--------|-------|
| Password complexity | Implemented | Configurable requirements |
| Account lockout | Implemented | 5 attempts, 30-min lockout |
| Session timeout | Implemented | 30 minutes default |
| MFA support | Implemented | TOTP-based |
| IP allowlisting | Implemented | Per-user configuration |
| Role-based access | Implemented | Hierarchical permissions |

### Network Security

| Control | Status | Notes |
|---------|--------|-------|
| HTTPS enforcement | Required | Via deployment |
| CORS restrictions | Implemented | Configurable origins |
| Rate limiting | Implemented | Per-endpoint limits |
| Security headers | Implemented | CSP, HSTS, X-Frame-Options |

### Monitoring & Alerting

| Control | Status | Notes |
|---------|--------|-------|
| Prometheus metrics | Implemented | `/metrics` endpoint |
| Alertmanager integration | Implemented | Webhook receiver |
| SIEM logging | Implemented | JSON structured logs |
| Health checks | Implemented | `/health` endpoint |

### Data Protection

| Control | Status | Notes |
|---------|--------|-------|
| Encryption at rest | Via PostgreSQL | Database-level |
| Encryption in transit | Via HTTPS | Transport-level |
| PII redaction | Implemented | Audit log filtering |
| Token redaction | Implemented | Bearer token masking |

---

## Compliance Verification

### Automated Checks

Run the following commands to verify compliance controls:

```bash
# Verify audit log integrity
python scripts/run_retention.py --verify

# Check retention statistics
python scripts/run_retention.py --stats

# Review security event logs
grep '"is_security_event": true' /var/log/check-review/security.log
```

### Periodic Reviews

| Review | Frequency | Responsible Party |
|--------|-----------|-------------------|
| Access control audit | Quarterly | Security team |
| Audit log verification | Weekly | Automated cron |
| Retention compliance | Monthly | Compliance officer |
| Security event review | Daily | SOC/NOC team |

---

## Contact Information

For compliance-related inquiries:

- **Security Issues**: security@example.com
- **Compliance Questions**: compliance@example.com
- **Audit Requests**: audit@example.com

---

*Last Updated: 2024-01-15*
*Document Version: 1.0*
