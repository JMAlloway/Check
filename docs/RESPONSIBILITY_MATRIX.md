# Product Scope & Responsibility Matrix

> **Purpose**: Define what we own, what the bank owns, and where the boundaries are
> **Audience**: Bank leadership, Legal/Procurement, Implementation teams
> **Why This Matters**: Prevents scope creep, liability confusion, and sales misunderstandings

---

## Product Scope Summary

### What Check Review Console IS

| Capability | Description |
|------------|-------------|
| Exception review workflow | Review, approve, return, escalate check items |
| Image viewing | Display check images from bank storage |
| Context enrichment | Show account history, balances, patterns |
| Policy enforcement | Apply bank-defined rules to decisions |
| Dual control | Require second approval for high-value items |
| Audit trail | Capture evidence of every decision |
| Reporting | Operational and compliance reports |

### What Check Review Console IS NOT

| Not In Scope | Why |
|--------------|-----|
| Check image capture | Bank's item processing system handles capture |
| OCR / MICR reading | Bank's item processing system handles |
| Deposit posting | Core banking system handles |
| Return processing | Core banking system handles |
| Customer notification | Bank's communication systems handle |
| Account opening/closing | Core banking system handles |

---

## Responsibility Matrix (RACI)

**Legend**:
- **R** = Responsible (does the work)
- **A** = Accountable (ultimately answerable)
- **C** = Consulted (provides input)
- **I** = Informed (kept updated)

### System Implementation

| Activity | SaaS | Bank IT | Bank Ops | Bank InfoSec |
|----------|------|---------|----------|--------------|
| Provision tenant & users | R/A | C | C | I |
| Deploy Connector A | C | R/A | I | C |
| Configure firewall rules | I | R/A | I | C |
| Generate/exchange keys | R | R | I | A |
| Configure SFTP (Connectors B/C) | C | R/A | I | C |
| Define exception policies | C | I | R/A | C |
| User training | C | I | R/A | I |
| Go-live approval | C | C | R/A | C |

### Ongoing Operations

| Activity | SaaS | Bank IT | Bank Ops | Bank InfoSec |
|----------|------|---------|----------|--------------|
| SaaS platform availability | R/A | I | I | I |
| Connector A uptime | C | R/A | I | I |
| User provisioning | C | R | R/A | C |
| Policy updates | C | I | R/A | C |
| Security monitoring | R | C | I | A |
| Incident response | R | R | C | A |
| Audit support | R | C | R | A |

### Data Management

| Activity | SaaS | Bank IT | Bank Ops | Bank InfoSec |
|----------|------|---------|----------|--------------|
| Check images | I | R/A | I | C |
| Account context data | I | R/A | C | C |
| Decision records | R/A | I | C | C |
| Audit logs | R/A | I | C | A |
| User credentials | R | R/A | I | A |

---

## Detailed Ownership Boundaries

### Check Images

| Aspect | Owner | Notes |
|--------|-------|-------|
| Image capture | **Bank** | Item processing system |
| Image storage | **Bank** | UNC shares, SAN, NAS |
| Image retention | **Bank** | Per bank policy |
| Image serving | **SaaS** | Via Connector A |
| Image caching | **SaaS** | 60-second TTL |
| Image display | **SaaS** | In review console |

**We never store check images.** Images are fetched on-demand and cached briefly for performance.

### Account Data

| Aspect | Owner | Notes |
|--------|-------|-------|
| Account master data | **Bank** | Core banking system |
| Context data export | **Bank** | Daily file to SFTP |
| Context data import | **SaaS** | Connector C ingestion |
| Context data display | **SaaS** | In review console |
| Context data accuracy | **Bank** | SaaS displays what's provided |

**We display the data you provide.** We don't validate or enrich account data beyond what's in the export file.

### Decisions

| Aspect | Owner | Notes |
|--------|-------|-------|
| Decision workflow | **SaaS** | Review, approve, return, escalate |
| Decision policies | **Bank** | Define thresholds, rules |
| Decision execution | **SaaS** | Enforce policies, capture evidence |
| Decision output file | **SaaS** | Generate via Connector B |
| Decision import to core | **Bank** | Core banking process |
| Account impact | **Bank** | Core banking posts/returns |

**We facilitate decisions. The bank executes them.**

### Users & Access

| Aspect | Owner | Notes |
|--------|-------|-------|
| User identity | **Bank** | HR owns, IT provisions |
| User authentication | **Shared** | SaaS authenticates, bank may provide SSO |
| User authorization | **Shared** | Bank assigns roles, SaaS enforces |
| User activity logging | **SaaS** | All actions logged |
| User access reviews | **Bank** | Periodic review required |

---

## Integration Boundaries

### Connector A (Image Access)

```
┌────────────────────────────┬────────────────────────────┐
│      BANK OWNS             │       SAAS OWNS            │
├────────────────────────────┼────────────────────────────┤
│ Connector server (hardware)│ Connector software         │
│ Connector network access   │ JWT token generation       │
│ Image storage              │ Image request routing      │
│ Service account            │ Rate limiting              │
│ TLS certificate            │ Health monitoring          │
│ Firewall rules             │ Audit logging              │
└────────────────────────────┴────────────────────────────┘
```

### Connector B (Decision Output)

```
┌────────────────────────────┬────────────────────────────┐
│      BANK OWNS             │       SAAS OWNS            │
├────────────────────────────┼────────────────────────────┤
│ SFTP server                │ Batch file generation      │
│ SFTP credentials           │ File delivery              │
│ File format specification  │ File format compliance     │
│ Core import process        │ Acknowledgement processing │
│ Account posting            │ Reconciliation reporting   │
│ Error handling (core side) │ Retry logic                │
└────────────────────────────┴────────────────────────────┘
```

### Connector C (Context Import)

```
┌────────────────────────────┬────────────────────────────┐
│      BANK OWNS             │       SAAS OWNS            │
├────────────────────────────┼────────────────────────────┤
│ Context data accuracy      │ SFTP polling               │
│ Context data export job    │ File parsing               │
│ SFTP server                │ Data matching              │
│ File format specification  │ Error handling             │
│ Data freshness             │ Import reporting           │
└────────────────────────────┴────────────────────────────┘
```

---

## Support Responsibilities

### Incident Categories

| Category | Primary Owner | Secondary |
|----------|---------------|-----------|
| SaaS platform down | **SaaS** | Bank IT (notification) |
| Connector A unreachable | **Bank IT** | SaaS (diagnosis) |
| Images not loading | **Joint** | Depends on root cause |
| User cannot log in | **Joint** | Depends on auth method |
| Decision file rejected | **Joint** | Format or content issue |
| Wrong decision made | **Bank Ops** | SaaS (audit support) |

### Escalation Path

```
Tier 1: Bank help desk (user issues)
   │
   ▼
Tier 2: Bank IT (connectivity, access)
   │
   ▼
Tier 3: SaaS support (platform issues)
   │
   ▼
Tier 4: Joint escalation (complex issues)
```

---

## Compliance Responsibilities

| Requirement | SaaS Responsibility | Bank Responsibility |
|-------------|---------------------|---------------------|
| SOC 2 (SaaS platform) | Obtain and provide report | Review report |
| SOC 2 (bank controls) | N/A | Maintain own controls |
| GLBA data protection | Encrypt in transit/rest | Control access |
| FFIEC dual control | Enforce in software | Define policy |
| Audit trail retention | Store 7 years | Define retention needs |
| Examiner access | Provide data export | Respond to requests |
| User access reviews | Provide access reports | Perform reviews |
| Security testing | Annual pentest | Review results |

---

## What We Don't Do

To be completely clear, the following are **explicitly out of scope**:

| Activity | Why Not |
|----------|---------|
| Write to core banking | File-based integration only; no direct API |
| Make posting decisions | We recommend; humans decide |
| Store images permanently | Images stay on bank storage |
| Validate account numbers | We display what you provide |
| Calculate interest/fees | Core banking function |
| Generate customer letters | Bank communication systems |
| Train ML on your data | Your data is yours alone |
| Share data between banks | Complete tenant isolation |

---

## Change Management

### Platform Changes (SaaS)

| Change Type | Notice | Bank Action Required |
|-------------|--------|----------------------|
| Bug fix | None | None |
| Minor feature | Release notes | Optional adoption |
| Major feature | 30 days | Training may be needed |
| Breaking change | 90 days | Configuration update |
| Security patch | ASAP | None (automatic) |

### Configuration Changes (Bank)

| Change Type | Process |
|-------------|---------|
| User add/remove | Bank admin self-service |
| Role change | Bank admin with approval |
| Policy update | Bank ops with testing |
| Connector config | Joint coordination |
| Key rotation | Joint coordination |

---

## Liability Summary

| Scenario | Liability |
|----------|-----------|
| Platform unavailable due to SaaS issue | SaaS (per SLA) |
| Connector unavailable due to bank network | Bank |
| Incorrect decision due to user error | Bank |
| Incorrect decision due to software bug | SaaS |
| Data breach due to SaaS vulnerability | SaaS |
| Data breach due to bank credential theft | Bank |
| Regulatory fine due to missing audit trail | SaaS (if our fault) |
| Regulatory fine due to policy violation | Bank |

**See Master Services Agreement for complete terms.**

---

## Questions to Ask Before Signing

1. "Who owns the check images?" → **Bank** (always)
2. "Do you write directly to our core?" → **No** (file-based only)
3. "Can you make decisions without humans?" → **No** (advisory only)
4. "Who is responsible if a bad check is approved?" → **Bank** (human decision)
5. "What happens to our data if we cancel?" → **Exported and deleted per contract**

---

*Document Version: 1.0 | Last Updated: January 2026*
