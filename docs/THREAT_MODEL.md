# Threat Model & Risk Mitigation Summary

> **Purpose**: Document identified threats, controls in place, and residual risk
> **Audience**: InfoSec, Vendor Risk, External Auditors
> **Philosophy**: We don't claim perfection — we demonstrate awareness and mitigation

---

## Threat Modeling Methodology

This threat model uses **STRIDE** categories:
- **S**poofing (identity)
- **T**ampering (data integrity)
- **R**epudiation (deniability)
- **I**nformation Disclosure (confidentiality)
- **D**enial of Service (availability)
- **E**levation of Privilege (authorization)

---

## System Components & Trust Boundaries

```
┌─────────────────────────────────────────────────────────────────────┐
│                         THREAT SURFACE                               │
│                                                                      │
│  ┌─────────┐   ┌─────────┐   ┌─────────┐   ┌─────────┐             │
│  │ Users   │   │ SaaS    │   │Connector│   │ Bank    │             │
│  │(Browser)│◄──►│ API     │◄──►│   A     │◄──►│ Storage │             │
│  └─────────┘   └─────────┘   └─────────┘   └─────────┘             │
│       │             │             │             │                   │
│  Trust Boundary 1   │        Trust Boundary 2   │                   │
│  (Internet)         │        (Bank perimeter)   │                   │
│                     │                           │                   │
│               ┌─────┴─────┐               ┌─────┴─────┐             │
│               │ Database  │               │   SFTP    │             │
│               │           │               │  Server   │             │
│               └───────────┘               └───────────┘             │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Threat Analysis

### T1: Credential Theft / Account Takeover

| Attribute | Value |
|-----------|-------|
| **Category** | Spoofing |
| **Target** | User accounts |
| **Attack Vector** | Phishing, credential stuffing, session hijacking |
| **Impact** | HIGH - Unauthorized access to check review decisions |

#### Controls in Place

| Control | Implementation | Effectiveness |
|---------|----------------|---------------|
| Password policy | Minimum 12 chars, complexity required | Medium |
| bcrypt hashing | Cost factor 12, salt per password | High |
| Session timeout | 30-minute inactivity timeout | Medium |
| Rate limiting | 5 failed logins → 15 min lockout | High |
| Audit logging | All auth events logged with IP | High |

#### Residual Risk

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Weak user passwords | Medium | High | Password policy enforcement |
| Phishing success | Medium | High | User training (bank responsibility) |
| Session token theft | Low | High | HTTP-only cookies, short TTL |

**Recommended Enhancement**: SSO integration with bank's MFA-enforced IdP.

---

### T2: JWT Token Replay (Connector A)

| Attribute | Value |
|-----------|-------|
| **Category** | Spoofing |
| **Target** | Connector A image access |
| **Attack Vector** | Capture and replay valid JWT token |
| **Impact** | MEDIUM - Unauthorized image access within token window |

#### Controls in Place

| Control | Implementation | Effectiveness |
|---------|----------------|---------------|
| Short token TTL | 60-120 seconds | High |
| JTI (unique ID) | UUID in each token | High |
| Replay cache | JTI stored for token lifetime | High |
| Replay rejection | Second use of JTI → 401 | High |

#### Attack Scenario & Defense

```
1. Attacker captures valid JWT (network intercept)
2. Attacker attempts to use captured token
3. IF within TTL AND first use → SUCCESS (single use)
4. IF within TTL AND second use → BLOCKED (replay detected)
5. IF after TTL → BLOCKED (expired)
```

#### Residual Risk

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| First-use within TTL | Low | Medium | Short TTL (60s default) |
| JTI cache failure | Very Low | Medium | Cache is in-memory, fast |

**Residual risk accepted**: Single-use within 60 seconds is acceptable.

---

### T3: Path Traversal (Connector A)

| Attribute | Value |
|-----------|-------|
| **Category** | Information Disclosure |
| **Target** | Bank file system |
| **Attack Vector** | `../` sequences to escape allowed directories |
| **Impact** | CRITICAL - Access to arbitrary bank files |

#### Controls in Place

| Control | Implementation | Effectiveness |
|---------|----------------|---------------|
| Path allowlist | Only configured UNC roots allowed | High |
| Traversal detection | `..` sequences rejected | High |
| Path normalization | Paths canonicalized before check | High |
| Case-insensitive | Windows path handling | High |

#### Validation Logic

```python
def validate_path(requested_path):
    # 1. Reject empty paths
    # 2. Reject paths with ..
    # 3. Normalize path (resolve . and ..)
    # 4. Check if starts with allowed root
    # 5. Case-insensitive comparison (Windows)
```

#### Residual Risk

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Allowlist bypass | Very Low | Critical | Defense in depth, multiple checks |
| Symlink following | Low | High | Service account has no symlink creation rights |

**Residual risk accepted**: Multiple layers of validation make bypass unlikely.

---

### T4: Decision Tampering

| Attribute | Value |
|-----------|-------|
| **Category** | Tampering |
| **Target** | Decision records and evidence |
| **Attack Vector** | Database modification, log manipulation |
| **Impact** | CRITICAL - Fraudulent check approvals |

#### Controls in Place

| Control | Implementation | Effectiveness |
|---------|----------------|---------------|
| Evidence snapshots | Captured at decision time | High |
| Hash chain | SHA-256 links each decision | High |
| Audit trail | Immutable append-only logs | High |
| Dual control | Two users required for high-value | High |

#### Evidence Integrity

```
Decision 1: evidence_hash = SHA256(content)
            previous_hash = null

Decision 2: evidence_hash = SHA256(content)
            previous_hash = Decision1.evidence_hash

Decision 3: evidence_hash = SHA256(content)
            previous_hash = Decision2.evidence_hash

Tampering with Decision 1 → breaks hash chain at Decision 2
```

#### Residual Risk

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Database admin compromise | Low | Critical | Audit logs detect, hash chain proves |
| Hash algorithm weakness | Very Low | Critical | SHA-256 is industry standard |

**Residual risk accepted**: Hash chain provides cryptographic tamper-evidence.

---

### T5: Privilege Escalation

| Attribute | Value |
|-----------|-------|
| **Category** | Elevation of Privilege |
| **Target** | RBAC system |
| **Attack Vector** | Role manipulation, permission bypass |
| **Impact** | HIGH - Unauthorized approvals |

#### Controls in Place

| Control | Implementation | Effectiveness |
|---------|----------------|---------------|
| Server-side RBAC | Permissions checked on every request | High |
| Tenant isolation | tenant_id enforced on all queries | High |
| Self-approval block | Cannot approve own decisions | High |
| Permission audit | All permission checks logged | High |

#### Multi-Tenant Isolation

```sql
-- Every query includes tenant filter
SELECT * FROM check_items
WHERE id = :id
  AND tenant_id = :current_user_tenant_id  -- ALWAYS PRESENT
```

**Cross-tenant access is architecturally impossible.**

#### Residual Risk

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| SQL injection | Very Low | Critical | ORM (SQLAlchemy), no raw SQL |
| Logic bug in RBAC | Low | High | Unit tests, code review |

---

### T6: Denial of Service

| Attribute | Value |
|-----------|-------|
| **Category** | Denial of Service |
| **Target** | SaaS availability, Connector A |
| **Attack Vector** | Volumetric attacks, resource exhaustion |
| **Impact** | HIGH - Unable to process check decisions |

#### Controls in Place

| Control | Implementation | Effectiveness |
|---------|----------------|---------------|
| Rate limiting (API) | Per-user, per-endpoint limits | High |
| Rate limiting (Connector) | 100 req/min default | High |
| Cloud DDoS | Cloud-native DDoS protection | High |
| WAF | OWASP rule set | Medium |
| Resource limits | Max image size, query limits | High |

#### Residual Risk

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Sustained DDoS | Medium | High | Cloud mitigation, geographic distribution |
| Application-layer attack | Low | Medium | WAF rules, rate limiting |

---

### T7: Data Exfiltration

| Attribute | Value |
|-----------|-------|
| **Category** | Information Disclosure |
| **Target** | Check images, account data |
| **Attack Vector** | Unauthorized bulk download, insider threat |
| **Impact** | HIGH - PII and financial data exposure |

#### Controls in Place

| Control | Implementation | Effectiveness |
|---------|----------------|---------------|
| Per-image authorization | JWT required for each image request | High |
| Access logging | Every image access logged | High |
| Rate limiting | Prevents bulk download | High |
| No persistent URLs | Signed URLs expire in 90 seconds | High |

#### Residual Risk

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Authorized user exfiltration | Low | High | Audit logs enable detection |
| Screenshot capture | Medium | Medium | Watermarks (optional), user agreement |

**Residual risk accepted**: Authorized users can view data; logging enables detection.

---

### T8: Supply Chain Attack

| Attribute | Value |
|-----------|-------|
| **Category** | Tampering |
| **Target** | Dependencies, build pipeline |
| **Attack Vector** | Compromised npm/pip packages |
| **Impact** | CRITICAL - Backdoor in application |

#### Controls in Place

| Control | Implementation | Effectiveness |
|---------|----------------|---------------|
| Dependency pinning | Lock files for all dependencies | High |
| Vulnerability scanning | Dependabot / Snyk | Medium |
| Code review | All changes reviewed | High |
| Minimal dependencies | Reduce attack surface | Medium |

#### Residual Risk

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Zero-day in dependency | Low | Critical | Rapid patching process |
| Typosquatting | Very Low | Critical | Lock files prevent |

---

## Risk Summary Matrix

| Threat | Likelihood | Impact | Risk Level | Status |
|--------|------------|--------|------------|--------|
| T1: Credential Theft | Medium | High | **HIGH** | Mitigated |
| T2: JWT Replay | Low | Medium | **MEDIUM** | Mitigated |
| T3: Path Traversal | Very Low | Critical | **MEDIUM** | Mitigated |
| T4: Decision Tampering | Low | Critical | **HIGH** | Mitigated |
| T5: Privilege Escalation | Low | High | **MEDIUM** | Mitigated |
| T6: Denial of Service | Medium | High | **HIGH** | Mitigated |
| T7: Data Exfiltration | Low | High | **MEDIUM** | Accepted |
| T8: Supply Chain | Low | Critical | **HIGH** | Mitigated |

---

## Accepted Risks

The following residual risks are **accepted** with documented rationale:

| Risk | Rationale | Review Frequency |
|------|-----------|------------------|
| Authorized user data access | Users need to view data to do their job; logging enables detection | Quarterly |
| Single JWT use within 60s | Extremely short window; replay protection active | Annual |
| Screenshot/photo capture | Physical access control is bank's responsibility | N/A |

---

## Threat Model Review Schedule

| Event | Action |
|-------|--------|
| Quarterly | Review accepted risks |
| After incident | Update threat model |
| Major release | Review new attack surface |
| Annual | Full threat model refresh |

---

## Security Testing

| Test Type | Frequency | Last Completed |
|-----------|-----------|----------------|
| Automated vulnerability scan | Weekly | [Date] |
| Dependency audit | Daily | Automated |
| Penetration test | Annual | [Date] |
| Code review | Every PR | Continuous |

---

*Document Version: 1.0 | Last Updated: January 2026*
