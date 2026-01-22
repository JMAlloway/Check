# Demo vs Pilot vs Production Environment Definitions

> **Purpose**: Define what's real, what's simulated, and what controls apply in each environment
> **Audience**: Bank stakeholders, Implementation team, Auditors
> **Why This Matters**: Prevents misunderstandings about data, actions, and audit scope

---

## Environment Summary

| Aspect | Demo | Pilot | Production |
|--------|------|-------|------------|
| **Data** | 100% synthetic | Real bank data | Real bank data |
| **Decisions** | No downstream effect | Real, may be limited scope | Real, full scope |
| **Users** | Test accounts | Real users, limited | Real users, all |
| **Audit Trail** | Preserved but labeled | Full audit | Full audit |
| **Core Integration** | Disabled | Enabled (sandboxed) | Enabled (live) |
| **SLA** | None | Best effort | Contracted |

---

## Demo Environment

### Purpose

Demonstrate product capabilities without any connection to real bank systems or data.

### Data Characteristics

| Data Type | Source | Description |
|-----------|--------|-------------|
| Check items | Generated | Synthetic trace numbers, amounts, dates |
| Check images | Sample files | Stock check images, not real instruments |
| Account context | Simulated | Fake balances, tenure, history |
| Users | Test accounts | `demo@bank.local`, `reviewer@demo.local` |

**No real PII, account numbers, or financial data exists in demo mode.**

### Actions & Effects

| Action | Demo Behavior | Production Behavior |
|--------|---------------|---------------------|
| Approve check | Status changes in UI only | Status changes + file to core |
| Return check | Status changes in UI only | Status changes + file to core |
| Dual control | Simulated workflow | Real enforcement |
| Audit log | Written but tagged `[DEMO]` | Full production audit |

### Connector Behavior

| Connector | Demo Mode |
|-----------|-----------|
| **Connector A** (Images) | Serves local sample images, no bank connection |
| **Connector B** (Decisions) | No files generated or transmitted |
| **Connector C** (Context) | Uses synthetic context data |

### Safeguards

The system **automatically enforces** demo mode restrictions:

```
DEMO_MODE=true
├── Decision files: NOT generated
├── SFTP connections: DISABLED
├── Core callbacks: DISABLED
├── Data: Synthetic only
└── Audit logs: Tagged [DEMO]
```

### When to Use Demo

- Initial product demonstrations
- Training new users before pilot
- Sales presentations
- Internal testing and development

### Demo Mode Indicators

Users will see:
- **Banner**: "DEMO MODE - Synthetic Data Only"
- **Watermark**: On all check images
- **User badge**: Demo account indicator

---

## Pilot Environment

### Purpose

Validate the system with real bank data in a controlled, limited-scope deployment.

### Data Characteristics

| Data Type | Source | Description |
|-----------|--------|-------------|
| Check items | Real bank data | Actual exceptions from limited scope |
| Check images | Real images | From Connector A (bank storage) |
| Account context | Real data | From Connector C (core export) |
| Users | Real employees | Named, authenticated, audited |

**Pilot uses real data - all privacy and security controls apply.**

### Scope Limitations

Pilot is typically limited by:

| Limitation Type | Example |
|-----------------|---------|
| **Branch** | "Only Main St. branch items" |
| **Amount** | "Items under $10,000 only" |
| **Volume** | "First 100 items per day" |
| **User count** | "5 reviewers, 2 approvers" |
| **Duration** | "2-week pilot period" |

### Actions & Effects

| Action | Pilot Behavior |
|--------|----------------|
| Approve check | Decision recorded, file generated to **pilot folder** |
| Return check | Decision recorded, file generated to **pilot folder** |
| Dual control | **Fully enforced** |
| Audit log | **Full production audit** |

### Connector Behavior

| Connector | Pilot Mode |
|-----------|------------|
| **Connector A** (Images) | Live connection to bank storage |
| **Connector B** (Decisions) | Files to **pilot/sandbox folder** (not live core) |
| **Connector C** (Context) | Live import from bank export |

### Pilot vs Production Decision Routing

```
Production:
  Decisions → /inbound/decisions/CRC_*.csv → Core Import → Account Update

Pilot:
  Decisions → /inbound/pilot/CRC_*.csv → Manual Review → Optional Import
```

**Bank controls whether pilot decisions are imported to core.**

### Safeguards

| Control | Description |
|---------|-------------|
| Separate file path | Pilot files go to distinct folder |
| Manual gate | Bank manually imports (no auto-processing) |
| Daily reconciliation | Compare pilot decisions to core state |
| Rollback support | Can void pilot decisions if needed |

### Promotion Criteria (Pilot → Production)

| Criterion | Target | Actual |
|-----------|--------|--------|
| Decision accuracy | >99% | |
| System uptime | >99.5% | |
| User satisfaction | Positive | |
| Dual control working | 100% | |
| Audit log completeness | 100% | |
| No security incidents | 0 | |
| Integration errors | <1% | |

### When to Use Pilot

- First deployment at a new bank
- Major version upgrades
- New connector type deployment
- After significant configuration changes

---

## Production Environment

### Purpose

Live system processing real bank exceptions with full downstream effects.

### Data Characteristics

| Data Type | Source | Description |
|-----------|--------|-------------|
| Check items | Real bank data | All exceptions per policy |
| Check images | Real images | From Connector A |
| Account context | Real data | From Connector C |
| Users | All authorized | Full user population |

**Production processes real financial instruments. All actions have real consequences.**

### Actions & Effects

| Action | Production Behavior |
|--------|---------------------|
| Approve check | Funds posted to account |
| Return check | Item returned to depositor |
| Dual control | Enforced per policy |
| Audit log | Full immutable audit trail |

### Connector Behavior

| Connector | Production Mode |
|-----------|-----------------|
| **Connector A** (Images) | Live, monitored, SLA-bound |
| **Connector B** (Decisions) | Live file delivery to core import |
| **Connector C** (Context) | Scheduled daily import |

### Controls & Compliance

| Control | Status |
|---------|--------|
| Audit logging | ✅ Full, immutable |
| Evidence snapshots | ✅ Cryptographically sealed |
| Dual control | ✅ Enforced by policy |
| Access logging | ✅ All actions attributed |
| Data encryption | ✅ In transit and at rest |
| Session management | ✅ Timeout, single-session |

### SLA Commitments

| Metric | Target |
|--------|--------|
| Availability | 99.9% during business hours |
| Image load time | <2 seconds (95th percentile) |
| Decision file delivery | Within 15 minutes of batch close |
| Support response (P1) | 15 minutes |
| Support response (P2) | 2 hours |

### Incident Handling

All production incidents follow the documented [Incident Response Plan](./INCIDENT_RESPONSE.md).

---

## Environment Promotion Process

```
┌─────────┐     ┌─────────┐     ┌─────────────┐
│  DEMO   │ ──► │  PILOT  │ ──► │ PRODUCTION  │
└─────────┘     └─────────┘     └─────────────┘
     │               │                 │
     │               │                 │
  No gate      Gate: Checklist    Gate: Sign-off
               + Bank approval    + Go-live checklist
```

### Demo → Pilot Checklist

- [ ] Intake questionnaire completed
- [ ] Preconditions checklist passed
- [ ] Connector A deployed and tested
- [ ] User accounts provisioned (real users)
- [ ] Pilot scope defined and documented
- [ ] Bank IT sign-off

### Pilot → Production Checklist

- [ ] Pilot success criteria met
- [ ] No open P1/P2 issues
- [ ] Security review completed
- [ ] User training completed
- [ ] Support escalation path confirmed
- [ ] Bank business owner sign-off
- [ ] Go-live date agreed

---

## Data Isolation Guarantees

### Cross-Environment Isolation

| Data Flow | Allowed? |
|-----------|----------|
| Demo → Pilot | ❌ No |
| Demo → Production | ❌ No |
| Pilot → Production | ✅ Yes (promotion only) |
| Production → Demo | ❌ No |
| Production → Pilot | ❌ No |

### Multi-Tenant Isolation

Each bank tenant is fully isolated:
- Separate database schemas (where applicable)
- `tenant_id` filter on all queries
- No cross-tenant data access possible
- Audit logs include tenant context

---

## Audit Implications

### Demo Environment

- Audit logs are preserved but clearly labeled
- Not subject to retention requirements
- Can be purged after demo period
- **Not suitable for compliance demonstrations**

### Pilot Environment

- **Full audit trail required**
- Same retention as production
- Subject to internal audit review
- Evidence snapshots are sealed

### Production Environment

- **Immutable audit trail**
- Minimum 7-year retention (configurable)
- Evidence snapshots cryptographically sealed
- Chain of custody maintained
- Supports regulatory examination

---

## Frequently Asked Questions

### "Can demo data be promoted to pilot?"

**No.** Demo uses synthetic data that would corrupt production systems. Pilot must start fresh with real bank data.

### "Can pilot decisions affect real accounts?"

**Only if the bank manually imports them.** Pilot files go to a sandbox folder that the bank controls.

### "What if we find a bug in production?"

Follow the [Incident Response Plan](./INCIDENT_RESPONSE.md). Depending on severity, we may:
- Hot-fix in production
- Roll back to previous version
- Temporarily disable affected feature

### "Can we run pilot and production simultaneously?"

**Yes, for different scopes.** Example: Pilot new feature with select users while production handles normal volume.

### "How do we know we're in the right environment?"

- **UI indicator**: Environment name in header
- **URL**: Different domains (demo.app.com, app.com)
- **Login**: Different credentials per environment

---

*Document Version: 1.0 | Last Updated: January 2026*
