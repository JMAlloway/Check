# Check Review Console - Non-Functional Requirements

This document captures the non-functional requirements (NFRs) for the Check Review Console.

## 1. Data Retention

### Check Images
| Data Type | Retention Period | Storage | Notes |
|-----------|-----------------|---------|-------|
| Check images (front/back) | 7 years minimum | Bank's image archive | Images remain on-premise, accessed via connector |
| Image thumbnails/cache | 24 hours | Application cache | Cleared on session end or daily purge |

### Logs and Audit Trail
| Data Type | Retention Period | Storage | Notes |
|-----------|-----------------|---------|-------|
| Audit logs | 7 years | Database + backup | Immutable after creation |
| Decision history | 7 years | Database | Linked to check item |
| Session logs | 90 days | Database | For security analysis |
| API access logs | 1 year | Log aggregation | For debugging and security |

### User Data
| Data Type | Retention Period | Storage | Notes |
|-----------|-----------------|---------|-------|
| User accounts | Until deactivated + 1 year | Database | Soft delete, retain for audit |
| Failed login attempts | 90 days | Database | For security monitoring |
| Password history | Last 12 passwords | Database | Prevent reuse |

### Fraud Data
| Data Type | Retention Period | Storage | Notes |
|-----------|-----------------|---------|-------|
| Fraud events | 24 months default | Database | Configurable per tenant |
| Network match alerts | 12 months | Database | Based on alert severity |
| Indicator hashes | 24 months | Database | For matching purposes |

---

## 2. Encryption

### Data in Transit
| Connection | Protocol | Minimum Version | Cipher Suites |
|------------|----------|----------------|---------------|
| Browser → API | TLS | 1.2 | AES-256-GCM, CHACHA20 |
| API → Database | TLS | 1.2 | Certificate validation required |
| API → Redis | TLS | 1.2 | Optional in dev, required in prod |
| API → Image Connector | mTLS | 1.2 | Certificate pinning recommended |
| Connector → Image Archive | Bank-managed | - | Per bank security policy |

### Data at Rest
| Data | Encryption | Key Management |
|------|------------|----------------|
| Database | AES-256 (cloud provider) | Provider-managed or customer HSM |
| Backups | AES-256 | Separate encryption key |
| Check images | Bank-managed | Images never stored in SaaS |
| Passwords | bcrypt (work factor 12+) | N/A - one-way hash |
| JWT tokens | RS256 or HS256 | Rotatable keys |
| Refresh tokens | SHA-256 hash | Only hash stored |

### Sensitive Field Handling
| Field | Treatment |
|-------|-----------|
| Account numbers | Masked in logs, encrypted in transit |
| SSN/TIN | Never stored or transmitted |
| Routing numbers | Hashed for fraud matching |
| Payee names | Hashed for fraud matching |

---

## 3. Audit Logging

### Logged Events
Every action that modifies data or accesses sensitive information:

| Category | Events Logged |
|----------|--------------|
| Authentication | Login, logout, failed login, password change, session refresh |
| Authorization | Permission denied, role changes, access to restricted resources |
| Check Processing | View, decide, approve, return, hold, escalate, note added |
| Fraud | Alert viewed, alert dismissed, event created, event submitted |
| User Management | Create, update, deactivate, role assignment |
| Configuration | Policy changes, queue changes, connector updates |
| Data Export | Audit packet export, report generation |

### Log Entry Structure
```json
{
  "id": "uuid",
  "timestamp": "ISO-8601 with timezone",
  "user_id": "uuid",
  "username": "string",
  "action": "enum (LOGIN, VIEW_CHECK, DECIDE, etc.)",
  "resource_type": "string",
  "resource_id": "string or null",
  "ip_address": "string",
  "user_agent": "string",
  "description": "human-readable",
  "metadata": "JSON (additional context)"
}
```

### Immutability
- Audit logs are append-only
- No update or delete operations permitted
- Database-level triggers prevent modification
- Signed hash chain for tamper detection (future enhancement)

### Access to Logs
- Users see their own actions only (default)
- Approvers see team actions
- Admins see all tenant actions
- Auditors have read-only access to all logs

---

## 4. Uptime Expectations

### Service Level Targets

| Environment | Uptime Target | Planned Maintenance Window |
|-------------|--------------|---------------------------|
| Production | 99.9% (8.76 hrs/year downtime) | Sundays 2-6 AM ET |
| Staging | 99% (best effort) | As needed |
| Development | No SLA | As needed |

### Degraded Operation
System should continue operating with reduced functionality if:
- Redis unavailable → Sessions fallback to database
- Image connector unreachable → Queue items, show cached thumbnails
- AI service unavailable → Manual review only (no AI recommendations)

### Monitoring
- Health check endpoint (`/health`) checks database and Redis
- External uptime monitoring recommended
- Alerts on error rate > 1% or latency P95 > 2s

---

## 5. Recovery Objectives

### RPO (Recovery Point Objective)
**Maximum acceptable data loss in case of failure:**

| Data Type | RPO | Backup Frequency |
|-----------|-----|-----------------|
| Decisions and audit logs | 15 minutes | Continuous replication |
| User data | 1 hour | Hourly snapshots |
| Configuration | 24 hours | Daily backups |
| Check images | N/A | Bank-managed (on-premise) |

### RTO (Recovery Time Objective)
**Maximum acceptable downtime:**

| Scenario | RTO | Recovery Procedure |
|----------|-----|-------------------|
| Single node failure | 5 minutes | Auto-failover to replica |
| Database failure | 30 minutes | Promote replica, failover |
| Complete region failure | 4 hours | DR site activation |
| Data corruption | 1 hour | Point-in-time recovery |

### Backup Testing
- Monthly: Automated backup restoration test
- Quarterly: Full DR drill with documented runbook
- Annual: Complete failover to DR site

---

## 6. Multi-Tenant Data Isolation

### Database Level
- All tables include `tenant_id` column
- Row-level security policies (where supported)
- No cross-tenant queries possible via API
- Tenant ID derived from authenticated user's JWT

### API Level
- All endpoints filter by tenant automatically
- Superuser permissions are tenant-scoped
- No endpoint allows specifying different tenant_id
- Cross-tenant requests return 404 (not 403) to prevent enumeration

### Network Level
- Shared infrastructure with logical separation
- Image connectors are tenant-specific
- Fraud sharing network hashes include tenant salt

### Audit Trail
- Tenant ID included in all audit log entries
- Audit exports filtered by tenant
- No administrative access to other tenants' data

### Testing Requirements
- Automated tests verify isolation
- Penetration testing includes cross-tenant attack vectors
- Security review required for any multi-tenant query

---

## 7. Performance Requirements

### Response Time Targets

| Operation | P50 | P95 | P99 |
|-----------|-----|-----|-----|
| Login | 200ms | 500ms | 1s |
| Load queue | 300ms | 700ms | 1.5s |
| View check item | 400ms | 800ms | 2s |
| Load check image | 500ms | 1.5s | 3s |
| Submit decision | 200ms | 500ms | 1s |
| Search (simple) | 500ms | 1s | 2s |
| Search (complex) | 1s | 3s | 5s |
| Export audit packet | 2s | 5s | 10s |

### Concurrent Users
- Designed for: 100 concurrent users per tenant
- Peak capacity: 500 concurrent users per tenant
- Database connection pool: 20 connections per tenant

### Scalability
- Horizontal scaling via container orchestration
- Database read replicas for reporting queries
- CDN for static assets

---

## 8. Security Requirements

### Authentication
- Password minimum: 8 characters, mixed case, number, special char
- Account lockout: 5 failed attempts → 30 minute lock
- Session timeout: 30 minutes of inactivity
- MFA: TOTP (Google Authenticator compatible)
- Rate limiting: 5 login attempts per minute per IP

### Session Management
- JWT access tokens: 15 minute expiry
- Refresh tokens: 7 day expiry, httpOnly cookie
- CSRF protection: Double-submit cookie pattern
- Session invalidation on password change
- Device fingerprinting for anomaly detection

### API Security
- All endpoints require authentication (except /health, /login)
- Input validation on all parameters
- SQL injection prevention via parameterized queries
- XSS prevention via output encoding
- CORS restricted to known origins

### Network Security
- HTTPS only (HTTP redirects to HTTPS)
- Security headers (HSTS, CSP, X-Frame-Options)
- Rate limiting at API gateway
- DDoS protection at CDN/load balancer

---

## 9. Compliance Considerations

### Regulatory Framework
This system handles check processing data which falls under:
- Bank Secrecy Act (BSA)
- Reg CC (Expedited Funds Availability)
- FFIEC examination guidelines
- State banking regulations

### Required Controls
| Requirement | Implementation |
|------------|----------------|
| Access controls | RBAC with documented permission model |
| Audit trail | Immutable logs with 7-year retention |
| Data protection | Encryption at rest and in transit |
| Change management | All changes logged, dual control for critical |
| Incident response | Security event logging, alerting |
| Vendor management | SOC 2 Type II certification (in progress) |

### Examination Readiness
- Audit log export in examiner-friendly format
- Decision history with full context
- User access reports
- Policy change history
- System access logs
