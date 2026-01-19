# Connector Compatibility & Preconditions Checklist

> **Purpose**: Pass/fail gating checklist before connector deployment begins
> **Audience**: Bank IT, SaaS Implementation Team
> **Usage**: All items must pass before proceeding to installation

---

## How to Use This Checklist

- ✅ = Requirement met, ready to proceed
- ⚠️ = Partial, needs clarification or workaround
- ❌ = Blocker, cannot proceed until resolved

**Gate Rule**: All items must be ✅ or ⚠️ (with documented workaround) before deployment.

---

## Connector A: Image Access (Bank-Side Deployment)

### Infrastructure Requirements

| # | Requirement | Status | Notes |
|---|-------------|--------|-------|
| A1 | **Server available** for connector deployment (Windows or Linux) | ☐ | Minimum: 2 CPU, 4GB RAM |
| A2 | **Python 3.11+** installed or can be installed | ☐ | Linux preferred, Windows supported |
| A3 | **Network path** from connector server to image storage | ☐ | SMB/CIFS port 445 |
| A4 | **Inbound HTTPS** allowed from SaaS IP ranges (port 8443) | ☐ | Firewall rule required |
| A5 | **TLS certificate** available or can be provisioned | ☐ | Trusted CA for production |

### Access & Permissions

| # | Requirement | Status | Notes |
|---|-------------|--------|-------|
| A6 | **Service account** can be created | ☐ | Domain or local account |
| A7 | **Read-only access** to image share paths granted | ☐ | No write access needed |
| A8 | **Image paths documented** in UNC format | ☐ | Example: `\\server\share\path` |
| A9 | **Path structure** consistent and predictable | ☐ | Based on date/trace number |

### Image Format Compatibility

| # | Requirement | Status | Notes |
|---|-------------|--------|-------|
| A10 | **Image format** is TIFF (Group 4) or standard image format | ☐ | PNG, JPEG also supported |
| A11 | **Image size** typically under 50MB per image | ☐ | Configurable limit |
| A12 | **Image naming** includes trace number or unique identifier | ☐ | For lookup by item |

### Security

| # | Requirement | Status | Notes |
|---|-------------|--------|-------|
| A13 | **RSA key pair** can be generated and exchanged | ☐ | 2048-bit minimum |
| A14 | **Clock synchronization** (NTP) configured | ☐ | JWT validation requires accurate time |
| A15 | **Audit logging** destination available | ☐ | Local file or SIEM |

### Connector A Readiness

| Gate | Status |
|------|--------|
| All A1-A15 passed or have approved workarounds | ☐ Ready ☐ Not Ready |

---

## Connector B: Decision Output (SaaS-Side, File Delivery)

### Delivery Infrastructure

| # | Requirement | Status | Notes |
|---|-------------|--------|-------|
| B1 | **Delivery method** selected (SFTP, shared folder, API) | ☐ | SFTP recommended |
| B2 | **SFTP server** available (if SFTP selected) | ☐ | Bank-hosted preferred |
| B3 | **SFTP credentials** can be provided to SaaS | ☐ | SSH key preferred |
| B4 | **Write access** to inbound directory granted | ☐ | For decision files |
| B5 | **Read access** to acknowledgement directory | ☐ | For ack processing |

### File Format

| # | Requirement | Status | Notes |
|---|-------------|--------|-------|
| B6 | **File format** agreed (CSV, fixed-width, XML, JSON) | ☐ | Provide specification |
| B7 | **Field mapping** documented | ☐ | Which fields, what order |
| B8 | **File naming** convention agreed | ☐ | Include date, sequence |
| B9 | **Header/trailer** requirements documented | ☐ | If required by core |

### Core Integration

| # | Requirement | Status | Notes |
|---|-------------|--------|-------|
| B10 | **Import process** exists or will be built | ☐ | Core banking side |
| B11 | **Acknowledgement file** format documented | ☐ | Success/failure feedback |
| B12 | **Processing window** defined | ☐ | Cutoff times |

### Connector B Readiness

| Gate | Status |
|------|--------|
| All B1-B12 passed or have approved workarounds | ☐ Ready ☐ Not Ready |

---

## Connector C: Account Context (SaaS-Side, SFTP Import)

### Data Availability

| # | Requirement | Status | Notes |
|---|-------------|--------|-------|
| C1 | **Account context data** can be exported from core | ☐ | Daily batch |
| C2 | **Minimum fields** available: account_number, balance | ☐ | Additional fields enhance value |
| C3 | **Export format** is parseable (CSV, fixed-width, XML) | ☐ | Provide sample |

### Delivery Infrastructure

| # | Requirement | Status | Notes |
|---|-------------|--------|-------|
| C4 | **SFTP server** available for SaaS to poll | ☐ | Bank-hosted |
| C5 | **SFTP credentials** can be provided to SaaS | ☐ | Read-only access |
| C6 | **File location** documented | ☐ | Path and filename pattern |
| C7 | **Daily export schedule** can be configured | ☐ | Before business hours |

### Data Quality

| # | Requirement | Status | Notes |
|---|-------------|--------|-------|
| C8 | **Account numbers** match check item format | ☐ | Same identifier used |
| C9 | **Data freshness** acceptable (T-1 or T-0) | ☐ | Previous day minimum |
| C10 | **File completeness** verifiable | ☐ | Record count, checksum |

### Connector C Readiness

| Gate | Status |
|------|--------|
| All C1-C10 passed or have approved workarounds | ☐ Ready ☐ Not Ready |

---

## General Requirements (All Connectors)

### Network & Security

| # | Requirement | Status | Notes |
|---|-------------|--------|-------|
| G1 | **Outbound HTTPS** from bank to SaaS allowed | ☐ | For SaaS console access |
| G2 | **TLS 1.2+** supported on all connections | ☐ | TLS 1.3 preferred |
| G3 | **IP allowlisting** requirements documented | ☐ | If applicable |
| G4 | **Proxy requirements** documented | ☐ | If required |

### Compliance & Governance

| # | Requirement | Status | Notes |
|---|-------------|--------|-------|
| G5 | **Vendor risk assessment** completed or scheduled | ☐ | InfoSec requirement |
| G6 | **Data processing agreement** signed | ☐ | Legal requirement |
| G7 | **Change management** process documented | ☐ | Lead times, windows |

### Support

| # | Requirement | Status | Notes |
|---|-------------|--------|-------|
| G8 | **Technical contacts** identified (both sides) | ☐ | Name, email, phone |
| G9 | **Escalation path** documented | ☐ | Who to call |
| G10 | **Communication channel** agreed | ☐ | Email, Slack, Teams |

---

## Final Gate Assessment

### Connector Readiness Summary

| Connector | Status | Blockers |
|-----------|--------|----------|
| **Connector A** (Images) | ☐ Ready ☐ Blocked | |
| **Connector B** (Decisions) | ☐ Ready ☐ Blocked | |
| **Connector C** (Context) | ☐ Ready ☐ Blocked | |
| **General** | ☐ Ready ☐ Blocked | |

### Deployment Decision

| Decision | Date | By |
|----------|------|-----|
| ☐ **PROCEED** - All gates passed | | |
| ☐ **PROCEED WITH CONDITIONS** - Workarounds approved | | |
| ☐ **HOLD** - Blockers must be resolved | | |

### Blockers & Resolutions

| Blocker ID | Description | Owner | Target Resolution |
|------------|-------------|-------|-------------------|
| | | | |
| | | | |
| | | | |

---

## Common Blocker Resolutions

### "Cannot open firewall for inbound connections" (A4)
**Workaround**: Use outbound-only architecture with VPN tunnel or cloud relay
**Impact**: Increased complexity, additional latency
**Approval Required**: Yes (architecture change)

### "No SFTP server available" (B2, C4)
**Workaround**: SaaS can host SFTP endpoint for bank to push/pull
**Impact**: Direction reversal, bank initiates connection
**Approval Required**: Yes (security review)

### "Cannot export context data from core" (C1)
**Workaround**: Start without context enrichment, add later
**Impact**: Reduced decision quality, manual lookup required
**Approval Required**: Yes (product scope change)

### "Change management requires 4+ weeks lead time" (G7)
**Workaround**: Begin process immediately, parallel development
**Impact**: Extended timeline
**Approval Required**: No (process accommodation)

---

## Sign-Off

| Role | Name | Date | Signature |
|------|------|------|-----------|
| Bank IT Lead | | | |
| Bank InfoSec | | | |
| SaaS Implementation Lead | | | |

---

*Document Version: 1.0 | Last Updated: January 2026*
