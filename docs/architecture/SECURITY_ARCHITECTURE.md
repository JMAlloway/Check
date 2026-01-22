# Security Architecture Overview

> **Purpose**: Single reference for authentication, trust boundaries, encryption, and key management
> **Audience**: InfoSec, Vendor Risk, CIO, External Auditors
> **Scope**: Check Review Console SaaS + Bank-side connectors

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                                   CLOUD (SaaS)                                       │
│                                                                                      │
│  ┌──────────────────────────────────────────────────────────────────────────────┐   │
│  │                        Check Review Console                                   │   │
│  │                                                                               │   │
│  │  ┌─────────────┐   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐      │   │
│  │  │  Frontend   │   │  API Layer  │   │  Services   │   │  Database   │      │   │
│  │  │  (React)    │◄──┤  (FastAPI)  │◄──┤             │◄──┤  (Postgres) │      │   │
│  │  └─────────────┘   └──────┬──────┘   └──────┬──────┘   └─────────────┘      │   │
│  │         │                 │                 │                                │   │
│  │         │ TLS 1.3         │                 │                                │   │
│  │         ▼                 │                 │                                │   │
│  │  ┌─────────────┐          │                 │                                │   │
│  │  │   Users     │          │                 │                                │   │
│  │  │ (Browsers)  │          │                 │                                │   │
│  │  └─────────────┘          │                 │                                │   │
│  │                           │                 │                                │   │
│  │  ─────────────────────────┼─────────────────┼────────────────────────────── │   │
│  │  CONNECTOR MANAGER        │                 │                                │   │
│  │                           ▼                 ▼                                │   │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐              │   │
│  │  │ Connector A Mgr │  │ Connector B     │  │ Connector C     │              │   │
│  │  │ (Image Proxy)   │  │ (Batch Export)  │  │ (Context Import)│              │   │
│  │  └────────┬────────┘  └────────┬────────┘  └────────┬────────┘              │   │
│  └───────────┼────────────────────┼────────────────────┼────────────────────────┘   │
│              │                    │                    │                            │
└──────────────┼────────────────────┼────────────────────┼────────────────────────────┘
               │                    │                    │
               │ HTTPS + JWT        │ SFTP               │ SFTP
               │ (RS256, 60-120s)   │ (SSH Key)          │ (SSH Key)
               │                    │                    │
               ▼                    ▼                    ▼
┌──────────────────────────────────────────────────────────────────────────────────────┐
│                              BANK NETWORK                                             │
│                                                                                       │
│  ┌─────────────────────┐  ┌─────────────────────┐  ┌─────────────────────┐          │
│  │   Connector A       │  │   Decision Inbox    │  │   Context Outbox    │          │
│  │   (On-Premise)      │  │   (SFTP Folder)     │  │   (SFTP Folder)     │          │
│  │                     │  │                     │  │                     │          │
│  │  ┌───────────────┐  │  │  /inbound/          │  │  /outbound/         │          │
│  │  │ JWT Validator │  │  │  decisions/         │  │  context/           │          │
│  │  │ + JTI Cache   │  │  │                     │  │                     │          │
│  │  └───────┬───────┘  │  └──────────┬──────────┘  └──────────┬──────────┘          │
│  │          │          │             │                        │                      │
│  │          │ SMB      │             │                        │                      │
│  │          ▼          │             ▼                        ▼                      │
│  │  ┌───────────────┐  │  ┌─────────────────────────────────────────────┐           │
│  │  │ Image Storage │  │  │              Core Banking System            │           │
│  │  │ (UNC Shares)  │  │  │        (Fiserv, Jack Henry, FIS, etc.)      │           │
│  │  └───────────────┘  │  └─────────────────────────────────────────────┘           │
│  └─────────────────────┘                                                             │
│                                                                                       │
└───────────────────────────────────────────────────────────────────────────────────────┘
```

---

## Trust Boundaries

### Boundary 1: User ↔ SaaS (Browser to Cloud)

| Layer | Control |
|-------|---------|
| Transport | TLS 1.3 (HTTPS) |
| Authentication | JWT access tokens (30-min expiry) |
| Session | HTTP-only secure cookies |
| CSRF | Double-submit cookie pattern |
| Rate Limiting | Per-user, per-endpoint |

### Boundary 2: SaaS ↔ Connector A (Cloud to Bank)

| Layer | Control |
|-------|---------|
| Transport | TLS 1.2+ (HTTPS) |
| Authentication | RS256 JWT (60-120 second expiry) |
| Authorization | Role-based (image_viewer required) |
| Replay Protection | JTI cache with 5-minute TTL |
| Path Security | Allowlist-only file access |

### Boundary 3: SaaS ↔ Bank SFTP (File Exchange)

| Layer | Control |
|-------|---------|
| Transport | SSH/SFTP |
| Authentication | SSH key (Ed25519 or RSA 4096) |
| Authorization | Directory-scoped (inbound/outbound only) |
| Integrity | File hashing, record counts |

---

## Authentication Model

### User Authentication

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   User      │────►│  Login      │────►│  JWT Issued │
│  (Browser)  │     │  Endpoint   │     │  (30 min)   │
└─────────────┘     └─────────────┘     └─────────────┘
                           │
                    ┌──────┴──────┐
                    │             │
              ┌─────▼─────┐ ┌─────▼─────┐
              │ Password  │ │   SSO     │
              │ (bcrypt)  │ │ (SAML/    │
              │           │ │  OIDC)    │
              └───────────┘ └───────────┘
```

| Component | Implementation |
|-----------|----------------|
| Password hashing | bcrypt (cost factor 12) |
| Token algorithm | HS256 (symmetric) for user tokens |
| Token lifetime | Access: 30 min, Refresh: 7 days |
| Session binding | Token bound to user_id, tenant_id |

### Connector A Authentication (Image Requests)

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   SaaS      │────►│  Generate   │────►│  Connector  │
│   Backend   │     │  JWT (RS256)│     │  Validates  │
└─────────────┘     └─────────────┘     └─────────────┘
                           │
                    Private Key               Public Key
                    (SaaS holds)              (Connector holds)
```

| Component | Implementation |
|-----------|----------------|
| Algorithm | RS256 (asymmetric) |
| Key size | RSA 2048-bit minimum |
| Token lifetime | 60-120 seconds (configurable) |
| Claims | sub, org_id, roles, jti, exp, iat, iss |

### JWT Token Lifecycle

```
1. SaaS generates token:
   {
     "sub": "user-123",
     "org_id": "tenant-456",
     "roles": ["image_viewer", "check_reviewer"],
     "jti": "unique-token-id-789",
     "iat": 1705000000,
     "exp": 1705000120,  // 120 seconds
     "iss": "check-review-saas"
   }

2. Token signed with SaaS private key (RS256)

3. Connector validates:
   - Signature (using SaaS public key)
   - Expiration (exp claim)
   - Issuer (iss claim)
   - Replay (jti not in cache)
   - Roles (has required role)

4. JTI added to replay cache (TTL = token TTL)

5. Subsequent use of same JTI → REJECTED
```

---

## Encryption

### Data in Transit

| Connection | Protocol | Cipher Suites |
|------------|----------|---------------|
| User → SaaS | TLS 1.3 | AEAD ciphers (AES-GCM, ChaCha20) |
| SaaS → Connector A | TLS 1.2+ | RSA/ECDHE key exchange |
| SaaS → Bank SFTP | SSH | Ed25519, RSA-4096 |

### Data at Rest

| Data Type | Encryption | Key Management |
|-----------|------------|----------------|
| Database | AES-256 (transparent) | Cloud KMS |
| Credentials | AES-256-GCM | Application-level encryption |
| Audit logs | Immutable storage | Write-once, read-many |
| Evidence snapshots | SHA-256 hash chain | Tamper-evident |

### Key Hierarchy

```
┌─────────────────────────────────────────────────────────┐
│                    Master Key (KMS)                      │
│               (Cloud provider managed)                   │
└──────────────────────────┬──────────────────────────────┘
                           │
          ┌────────────────┼────────────────┐
          │                │                │
          ▼                ▼                ▼
   ┌─────────────┐  ┌─────────────┐  ┌─────────────┐
   │ Database    │  │ Application │  │ Connector   │
   │ Encryption  │  │ Secrets     │  │ JWT Keys    │
   │ Key         │  │ Key         │  │             │
   └─────────────┘  └─────────────┘  └─────────────┘
```

---

## Key Rotation

### User Session Keys

| Key Type | Rotation Frequency | Rotation Method |
|----------|-------------------|-----------------|
| SECRET_KEY (JWT signing) | 90 days | Rolling deployment |
| CSRF_SECRET_KEY | 90 days | Rolling deployment |

### Connector Keys

| Key Type | Rotation Frequency | Rotation Method |
|----------|-------------------|-----------------|
| Connector JWT key pair | Annual or on compromise | Overlap period (24h) |
| SFTP SSH keys | Annual | Coordinated with bank |

### Key Rotation Process (Connector A)

```
Day 0:  New key pair generated
        New public key registered with connector
        Old key remains valid

Day 1:  SaaS begins signing with new private key
        Connector accepts both old and new

Day 2+: Overlap period (24-48 hours)
        Both keys valid

Day N:  Old key removed from connector
        Rotation complete
```

---

## Access Control

### Role-Based Access Control (RBAC)

```
┌─────────────────────────────────────────────────────────────┐
│                        PERMISSIONS                           │
│  check_item:view  check_item:review  check_item:approve     │
│  policy:view      policy:edit        admin:manage           │
│  audit:view       report:view        image_connector:manage │
└───────────────────────────┬─────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                          ROLES                               │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐    │
│  │ Viewer   │  │ Reviewer │  │ Approver │  │  Admin   │    │
│  │          │  │          │  │          │  │          │    │
│  │ view     │  │ view     │  │ view     │  │ all      │    │
│  │          │  │ review   │  │ review   │  │          │    │
│  │          │  │          │  │ approve  │  │          │    │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘    │
└───────────────────────────┬─────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                         USERS                                │
│         Each user assigned to one or more roles              │
│         Each user belongs to exactly one tenant              │
└─────────────────────────────────────────────────────────────┘
```

### Multi-Tenant Isolation

| Layer | Isolation Mechanism |
|-------|---------------------|
| Data | `tenant_id` column on all tables, enforced in queries |
| API | Current user's tenant_id injected into all queries |
| Audit | Tenant context logged with every action |
| Files | Tenant-prefixed storage paths |

**Cross-tenant access is architecturally impossible.**

### Dual Control Enforcement

```
High-Value Decision (>$5,000):
  1. Reviewer makes recommendation
  2. Item enters PENDING_DUAL_CONTROL state
  3. Different user (Approver role) must approve
  4. Self-approval blocked at API level
  5. Both users logged in audit trail
```

---

## Network Security

### SaaS Infrastructure

| Control | Implementation |
|---------|----------------|
| WAF | Cloud-native WAF (OWASP rules) |
| DDoS | Cloud-native DDoS protection |
| Network segmentation | VPC with private subnets |
| Egress filtering | Allowlist for connector IPs |

### Connector A (Bank-Side)

| Control | Implementation |
|---------|----------------|
| Firewall | Inbound 8443 from SaaS IPs only |
| Rate limiting | 100 req/min per connector |
| Path allowlist | Only configured UNC paths accessible |
| TLS termination | At connector (not proxy) |

---

## Secrets Management

### Production Secrets Validated at Startup

```python
secrets_to_check = {
    "SECRET_KEY": 32,               # JWT signing
    "CSRF_SECRET_KEY": 32,          # CSRF protection
    "NETWORK_PEPPER": 32,           # Data hashing
    "CONNECTOR_JWT_PRIVATE_KEY": 100,  # Connector auth (RSA)
}
```

**Application refuses to start if secrets are default/insecure.**

### Secret Storage

| Environment | Storage | Access |
|-------------|---------|--------|
| Development | `.env` file (gitignored) | Local only |
| Production | Cloud Secrets Manager | IAM-controlled |
| Connector | Environment variables | OS-level protection |

---

## Audit & Logging

### What Gets Logged

| Event | Data Captured |
|-------|---------------|
| Authentication | user_id, IP, success/failure, timestamp |
| Authorization | user_id, resource, permission, result |
| Data access | user_id, record_id, fields accessed |
| Decisions | user_id, item_id, action, reason, evidence_hash |
| Admin actions | user_id, action, before/after state |
| Connector requests | correlation_id, path_hash, latency, result |

### Log Integrity

- Logs written to append-only storage
- Evidence snapshots include SHA-256 hash
- Hash chain links decisions for tamper-evidence
- Logs retained minimum 7 years

### SIEM Integration

Logs exported in standard formats:
- JSON (structured)
- CEF (Common Event Format)
- Syslog

---

## Compliance Mapping

| Requirement | Control |
|-------------|---------|
| **SOC 2 CC6.1** | Logical access controls (RBAC) |
| **SOC 2 CC6.2** | User authentication (JWT, MFA) |
| **SOC 2 CC6.3** | Authorization enforcement |
| **SOC 2 CC7.1** | System monitoring (audit logs) |
| **SOC 2 CC7.2** | Anomaly detection (rate limiting) |
| **GLBA 501(b)** | Data encryption (TLS, AES-256) |
| **FFIEC** | Dual control for high-value transactions |

---

## Security Contacts

| Role | Contact |
|------|---------|
| Security Lead | security@company.com |
| Incident Response | incident@company.com |
| Vulnerability Disclosure | security@company.com |

---

*Document Version: 1.0 | Last Updated: January 2026*
