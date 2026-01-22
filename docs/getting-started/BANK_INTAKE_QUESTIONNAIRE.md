# Bank Technical Intake Questionnaire

> **Purpose**: Capture all technical requirements in one pass to minimize back-and-forth
> **Audience**: Bank IT Lead, Core Banking Team, InfoSec
> **When to Complete**: Before kickoff call

---

## Instructions

Please complete all sections. If a question doesn't apply, write "N/A" with a brief explanation.
This questionnaire covers the three integration points:
- **Connector A**: Check image access (bank → SaaS)
- **Connector B**: Decision output (SaaS → bank)
- **Connector C**: Account context enrichment (bank → SaaS)

---

## Section 1: Bank Information

| Field | Response |
|-------|----------|
| Bank Name | |
| Bank Charter Number | |
| Primary Contact (Name, Title, Email) | |
| IT Contact (Name, Title, Email) | |
| InfoSec Contact (Name, Title, Email) | |
| Core Banking Contact (Name, Title, Email) | |
| Preferred Communication Channel | ☐ Email ☐ Slack ☐ Teams ☐ Other: ______ |

---

## Section 2: Core Banking System

| Field | Response |
|-------|----------|
| Core Banking Provider | ☐ Fiserv Premier ☐ Fiserv DNA ☐ Jack Henry SilverLake ☐ Jack Henry Symitar ☐ FIS Horizon ☐ Other: ______ |
| Core Version/Release | |
| Check Processing Module | |
| Item Processing Platform | ☐ Director Pro ☐ ITI ☐ NCR ☐ Other: ______ |
| Daily Check Volume (approx) | ☐ <500 ☐ 500-2,000 ☐ 2,000-10,000 ☐ >10,000 |
| Current Exception Review Process | ☐ Manual (paper) ☐ Core module ☐ Spreadsheet ☐ Third-party tool: ______ |

---

## Section 3: Check Image Storage (Connector A)

### 3.1 Image System

| Field | Response |
|-------|----------|
| Image Storage System | ☐ Director Pro ☐ ITI ViewDirect ☐ NCR ImageMark ☐ SAN/NAS ☐ Other: ______ |
| Image Format | ☐ TIFF (standard) ☐ TIFF Group 4 ☐ PNG ☐ JPEG ☐ Other: ______ |
| Image Resolution (DPI) | ☐ 200 ☐ 240 ☐ 300 ☐ Other: ______ |
| Average Image File Size | ☐ <50KB ☐ 50-200KB ☐ 200-500KB ☐ >500KB |

### 3.2 Storage Location

| Field | Response |
|-------|----------|
| Storage Type | ☐ Windows File Share (UNC) ☐ NAS ☐ SAN ☐ Cloud (S3/Azure) ☐ Other: ______ |
| UNC Path Format (example) | Example: `\\server\Checks\Transit\{date}\{trace}.tif` |
| Transit Check Path | |
| On-Us Check Path | |
| Image Retention Period | |

### 3.3 Network Access

| Field | Response |
|-------|----------|
| Can provision Windows server for connector? | ☐ Yes ☐ No (explain: ______) |
| Can provision Linux server for connector? | ☐ Yes ☐ No (explain: ______) |
| Firewall allows inbound HTTPS (443/8443)? | ☐ Yes ☐ No ☐ Requires change request |
| Preferred connector hosting location | ☐ On-premise ☐ Bank private cloud ☐ DMZ |

### 3.4 Service Account

| Field | Response |
|-------|----------|
| Can create service account for connector? | ☐ Yes ☐ No |
| Service account naming convention | Example: `svc_checkreview` |
| Can grant read-only access to image shares? | ☐ Yes ☐ No |

---

## Section 4: Account Context Data (Connector C)

### 4.1 Data Availability

| Field | Available? | Source System | Notes |
|-------|-----------|---------------|-------|
| Current Balance | ☐ Yes ☐ No | | |
| 30-Day Average Balance | ☐ Yes ☐ No | | |
| Account Open Date | ☐ Yes ☐ No | | |
| Account Type | ☐ Yes ☐ No | | |
| Check Count (30 days) | ☐ Yes ☐ No | | |
| Average Check Amount | ☐ Yes ☐ No | | |
| Returned Items (12 months) | ☐ Yes ☐ No | | |
| Exception Count (12 months) | ☐ Yes ☐ No | | |
| Relationship/Household ID | ☐ Yes ☐ No | | |

### 4.2 Export Capability

| Field | Response |
|-------|----------|
| Can generate daily account context export? | ☐ Yes ☐ No ☐ Custom development needed |
| Preferred export format | ☐ CSV ☐ Fixed-width ☐ XML ☐ JSON |
| Can schedule automated daily export? | ☐ Yes ☐ No |
| Existing SFTP server available? | ☐ Yes (host: ______) ☐ No |

---

## Section 5: Decision Output (Connector B)

### 5.1 Decision Routing

| Field | Response |
|-------|----------|
| How should decisions be received? | ☐ SFTP file drop ☐ Shared folder ☐ API callback ☐ Other: ______ |
| SFTP host (if applicable) | |
| File format preference | ☐ CSV ☐ Fixed-width ☐ XML ☐ JSON |
| Existing decision import process? | ☐ Yes (describe: ______) ☐ No (will build) |

### 5.2 File Requirements

| Field | Response |
|-------|----------|
| Required fields in decision file | |
| File naming convention | Example: `DECISIONS_YYYYMMDD_###.csv` |
| Header row required? | ☐ Yes ☐ No |
| Trailer row required? | ☐ Yes ☐ No |
| Acknowledgement file format | |

### 5.3 Processing Windows

| Field | Response |
|-------|----------|
| Decision file cutoff time | |
| Core posting window | |
| Weekend/holiday handling | |

---

## Section 6: Security & Compliance

### 6.1 Authentication

| Field | Response |
|-------|----------|
| Preferred authentication method | ☐ SSH keys ☐ Username/password ☐ Certificates |
| MFA requirements for service accounts | ☐ Required ☐ Not required ☐ N/A |
| IP allowlisting required? | ☐ Yes ☐ No |

### 6.2 Encryption

| Field | Response |
|-------|----------|
| TLS version requirement | ☐ TLS 1.2+ ☐ TLS 1.3 only ☐ Other: ______ |
| Certificate requirements | ☐ Public CA ☐ Internal CA ☐ Self-signed OK for testing |
| Data-at-rest encryption requirements | |

### 6.3 Compliance

| Field | Response |
|-------|----------|
| Regulatory framework | ☐ OCC ☐ FDIC ☐ NCUA ☐ State: ______ |
| SOC 2 report required? | ☐ Yes ☐ No |
| Penetration test report required? | ☐ Yes ☐ No |
| Vendor risk assessment required? | ☐ Yes ☐ No |
| Data residency requirements | ☐ US only ☐ Specific region: ______ ☐ None |

### 6.4 Change Management

| Field | Response |
|-------|----------|
| Change request lead time | ☐ None ☐ 1 week ☐ 2 weeks ☐ 1 month+ |
| Change window restrictions | |
| Emergency change process | |

---

## Section 7: Users & Access

### 7.1 User Population

| Role | Count | Notes |
|------|-------|-------|
| Reviewers (L1) | | |
| Approvers (L2 / Dual Control) | | |
| Supervisors | | |
| Administrators | | |
| Auditors (read-only) | | |

### 7.2 Authentication

| Field | Response |
|-------|----------|
| User authentication preference | ☐ Username/password ☐ SSO (SAML) ☐ SSO (OIDC) ☐ Active Directory |
| SSO provider (if applicable) | ☐ Okta ☐ Azure AD ☐ Ping ☐ Other: ______ |
| MFA required for users? | ☐ Yes ☐ No |

---

## Section 8: Infrastructure & Network

### 8.1 Network Topology

| Field | Response |
|-------|----------|
| Internet egress allowed? | ☐ Yes ☐ Proxy required ☐ No |
| Proxy server (if required) | |
| DNS resolution method | ☐ Internal DNS ☐ Public DNS ☐ Hosts file |

### 8.2 Monitoring & Logging

| Field | Response |
|-------|----------|
| SIEM platform | ☐ Splunk ☐ QRadar ☐ Sentinel ☐ Other: ______ ☐ None |
| Log shipping requirements | |
| Alerting integration | |

---

## Section 9: Timeline & Constraints

| Milestone | Target Date | Notes |
|-----------|-------------|-------|
| Kickoff call | | |
| Connector A deployed | | |
| Context feed configured | | |
| Decision output tested | | |
| Pilot start | | |
| Go-live target | | |

### Known Constraints

| Constraint | Details |
|------------|---------|
| Blackout periods | |
| Resource availability | |
| Dependencies on other projects | |
| Budget constraints | |

---

## Section 10: Additional Notes

*Use this space for any additional context, concerns, or questions:*

```
[Free text area]
```

---

## Submission

| Field | Response |
|-------|----------|
| Completed by | |
| Title | |
| Date | |
| Email | |

**Please return completed questionnaire to**: [your-email@company.com]

---

## What Happens Next

1. We review your responses within 2 business days
2. We schedule a 30-minute kickoff call to clarify any questions
3. We provide a customized onboarding timeline
4. We begin Connector A deployment (critical path)

---

*Document Version: 1.0 | Last Updated: January 2026*
