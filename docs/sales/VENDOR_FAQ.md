# Vendor Due Diligence FAQ

> **Purpose**: Answer common questions from bank legal, compliance, and risk teams
> **Audience**: General Counsel, Vendor Risk Management, Compliance Officers
> **Tone**: Direct, factual, no marketing language

---

> **TEMPLATE NOTE**: Items marked with `[CUSTOMIZE]` must be filled in with your company's actual information before sharing with prospects.

---

## Company & Product

### What does Check Review Console do?

Check Review Console is a cloud-based workflow application for reviewing exception check items. Bank employees use it to view check images, review account context, and make pay/return/hold decisions on items flagged by the bank's existing item processing system.

### What does it NOT do?

- Does not capture check images (uses bank's existing system)
- Does not read MICR lines or perform OCR
- Does not write directly to core banking systems
- Does not make autonomous decisions
- Does not replace item processing software

### Who are your customers?

Community banks and credit unions in the United States.

### How long have you been in business?

`[CUSTOMIZE]` Founded in 2024. Example: "We've been serving community banks for 2 years with a focus on check exception workflows."

---

## Data Handling

### What data do you collect?

| Data Type | Source | Purpose |
|-----------|--------|---------|
| User identities | Bank provides | Authentication, audit trail |
| Check item metadata | Bank provides | Display in review workflow |
| Account context | Bank provides (optional) | Enrich decision context |
| Decision records | Generated | Audit trail, reporting |
| Audit logs | Generated | Compliance, investigation |

### What data do you NOT collect?

- Full check images (fetched on-demand, not stored)
- Social Security numbers
- Full account numbers (may be masked)
- Customer names beyond what appears on check

### Where is data stored?

Production data is stored in `[CUSTOMIZE: e.g., AWS/Azure/GCP]` data centers located in the United States (`[CUSTOMIZE: e.g., us-east-1]`).

### Do you store check images?

**No.** Check images remain on bank storage systems. Our application fetches images on-demand through a bank-deployed connector. Images may be cached briefly (60 seconds) for performance but are not persisted.

### How long do you retain data?

| Data Type | Retention | Rationale |
|-----------|-----------|-----------|
| Decision records | 7 years | Regulatory requirement |
| Audit logs | 7 years | Regulatory requirement |
| User session logs | 2 years | Security investigation |
| Cached images | 60 seconds | Performance only |

### Can we request data deletion?

Yes. Upon contract termination, all bank data is exported (if requested) and permanently deleted within 30 days. A certificate of destruction is provided upon request.

### Do you share data with third parties?

**No.** Bank data is never shared with other customers, partners, or third parties. The only exceptions are:
- Cloud infrastructure providers (data processing agreement in place)
- As required by valid legal process (bank notified first if permitted)

---

## Security

### Do you have a SOC 2 report?

`[CUSTOMIZE]` Yes / In progress. Our SOC 2 Type II report covers security, availability, and confidentiality. Available under NDA upon request.

### Do you perform penetration testing?

Yes, annually by an independent third party. Summary results available under NDA.

### How do you handle vulnerabilities?

- Automated dependency scanning (daily)
- Security patches applied within 30 days of disclosure (14 days for critical)
- Critical vulnerabilities patched within 24 hours
- Responsible disclosure program available

### What authentication methods do you support?

- Username/password with configurable complexity requirements
- Single Sign-On (SSO) via SAML 2.0 or OIDC
- Multi-factor authentication (MFA) supported

### How is data encrypted?

- **In transit**: TLS 1.2+ for all connections
- **At rest**: AES-256 encryption for database and storage
- **Keys**: Managed by cloud KMS, rotated per policy

### Who has access to our data?

- Bank-authorized users only (RBAC enforced)
- SaaS support staff (with bank permission, audit logged)
- No access by other customers (complete tenant isolation)

### How do you ensure tenant isolation?

Every database query includes tenant identifier filtering. Cross-tenant access is architecturally impossible, not just policy-restricted.

---

## Integration

### Does your system write to our core banking system?

**No.** Integration is file-based only. We generate decision files that your team imports into core banking through your existing processes. We have no direct API access to core systems.

### What happens if your service is unavailable?

Check review pauses until service is restored. No data is lost. Decisions already exported to file continue processing in core banking. We provide an SLA with availability commitments.

### Can you change our account balances?

**No.** We display account context data that you provide via export file. We cannot modify any data in your core systems.

---

## AI & Automation

### Do you use AI or machine learning?

Optional AI features may display risk indicators or recommendations. All AI output is **advisory only** — final decisions are always made by human reviewers. AI features can be disabled if not desired.

### Do you train models on our data?

**No.** Your data is never used to train models that benefit other customers. Any models used are pre-trained on synthetic or licensed data.

### Can AI make decisions without human approval?

**No.** AI output is presented alongside other data points. A human reviewer must explicitly approve, return, or escalate every item.

### Who is responsible if AI recommends a bad decision?

The human reviewer who approved the decision. AI recommendations are advisory inputs, not determinative factors.

---

## Compliance

### Are you subject to bank examination?

Our services may be subject to examination by your regulator as a third-party service provider. We cooperate with examiner requests as permitted by contract.

### What regulations apply to your service?

We are designed to support bank compliance with:
- FFIEC Examination Guidance
- GLBA (data protection)
- BSA/AML (audit trail support)
- OCC/FDIC/NCUA guidance on third-party risk

We do not claim to make the bank "compliant" — compliance is the bank's responsibility.

### Can you provide compliance certifications?

We can provide:
- SOC 2 report
- Penetration test summary
- Security questionnaire responses
- Data processing agreement

### Do you have a Business Continuity Plan?

Yes. Our BCP includes:
- Geographic redundancy
- Regular backup testing
- Documented recovery procedures
- RTO/RPO targets

---

## Legal & Contractual

### What are your standard contract terms?

Our Master Services Agreement includes:
- Service description and scope
- Pricing and payment terms
- Data protection obligations
- Service levels and remedies
- Limitation of liability
- Term and termination
- Insurance requirements

### Do you carry professional liability insurance?

Yes. Coverage amounts available upon request.

### What is your limitation of liability?

`[CUSTOMIZE]` Typically capped at 12 months of fees paid. Consult your legal team for specific terms.

### What law governs the contract?

`[CUSTOMIZE]` Delaware law, with disputes resolved in Delaware courts. (Adjust to your company's jurisdiction.)

### Can we negotiate terms?

Yes, within reason. Material changes may affect pricing or availability.

---

## Operations

### What are your support hours?

- Standard support: `[CUSTOMIZE]` Monday-Friday 8am-6pm Eastern
- Emergency support: 24/7 for P1 issues
- Response time targets in SLA

### How do you handle incidents?

1. Detection (automated monitoring + user reports)
2. Triage and severity assignment
3. Communication to affected customers
4. Resolution and root cause analysis
5. Post-incident report (for significant incidents)

### How do you notify us of changes?

- Security patches: Applied automatically, notification after
- Feature releases: Release notes provided
- Breaking changes: 90-day advance notice minimum
- Planned maintenance: 7-day advance notice

### What happens if you go out of business?

Contract includes data return/destruction provisions. Source code escrow available upon request for additional fee.

---

## Implementation

### How long does implementation take?

Typical timeline: 4-8 weeks from kickoff to pilot. Variables include:
- Bank IT resource availability
- Network/firewall change processes
- File format alignment with core

### What resources do we need to provide?

- IT resource for connector deployment
- Core banking resource for file integration
- Operations resource for user setup and training
- InfoSec resource for security review

### Do you provide training?

Yes. Training options include:
- Administrator training (included)
- End-user training (included)
- Custom training (additional fee)

---

## Quick Reference

| Question | Short Answer |
|----------|--------------|
| Do you store check images? | No |
| Do you write to core banking? | No |
| Do you train AI on our data? | No |
| Can AI make decisions? | No (advisory only) |
| Is our data isolated from other banks? | Yes (architecturally) |
| Where is data stored? | US only |
| How long is data retained? | 7 years |
| Do you have SOC 2? | `[CUSTOMIZE]` Yes |
| What's your uptime SLA? | `[CUSTOMIZE]` 99.9% |
| Can we audit you? | Yes (per contract) |

---

## Contact

| Purpose | Contact |
|---------|---------|
| Sales inquiries | sales@checkreview.com `[CUSTOMIZE]` |
| Security questions | security@checkreview.com `[CUSTOMIZE]` |
| Legal/contracts | legal@checkreview.com `[CUSTOMIZE]` |
| Support | support@checkreview.com `[CUSTOMIZE]` |

---

*Document Version: 1.0 | Last Updated: January 2026*
