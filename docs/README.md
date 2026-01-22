# Check Review Console Documentation

Welcome to the documentation for the Check Review Console. This guide helps you find the right document for your needs.

---

## Quick Links by Role

### "I'm a Bank Project Manager"
Start here to understand the setup process:
1. [Setup Path Decision Tree](getting-started/BANK_PILOT_SETUP_PATHS.md) - Answer 4 questions to know your path
2. [Quick Start Guide](getting-started/PILOT_QUICK_START.md) - A-to-Z setup in 2-4 weeks
3. [Technical Intake Form](getting-started/BANK_INTAKE_QUESTIONNAIRE.md) - Send to your IT team

### "I'm a Bank IT Administrator"
Technical setup and configuration:
1. [Connector Setup Guide](connectors/CONNECTOR_SETUP.md) - Install and configure connectors
2. [Connector Checklist](connectors/CONNECTOR_PRECONDITIONS_CHECKLIST.md) - Pre-deployment requirements
3. [Deployment Runbook](deployment/PILOT_RUNBOOK.md) - Step-by-step procedures

### "I'm in Compliance or Audit"
Security and regulatory information:
1. [Security Architecture](architecture/SECURITY_ARCHITECTURE.md) - How we protect data
2. [SOC2 Controls](security/SOC2_OPERATIONAL_CONTROLS.md) - Control mappings
3. [Regulatory Framework](security/REGULATORY_FRAMEWORK.md) - Compliance alignment

### "I'm Evaluating This Product"
Understanding what we offer:
1. [Features & Benefits](sales/SALES_FEATURES_BENEFITS.md) - What the system does
2. [Vendor FAQ](sales/VENDOR_FAQ.md) - Common due diligence questions
3. [Technical Overview](architecture/CHECK_REVIEW_CONSOLE_TECHNICAL_GUIDE.md) - Deep technical detail

---

## Documentation by Folder

### [getting-started/](getting-started/) - Start Here
For new banks beginning the pilot process.

| Document | What It Covers |
|----------|----------------|
| [PILOT_QUICK_START.md](getting-started/PILOT_QUICK_START.md) | 2-4 week path from contract to go-live |
| [BANK_PILOT_SETUP_PATHS.md](getting-started/BANK_PILOT_SETUP_PATHS.md) | Decision tree to choose your setup path |
| [BANK_INTAKE_QUESTIONNAIRE.md](getting-started/BANK_INTAKE_QUESTIONNAIRE.md) | Information we need from your bank |
| [ENVIRONMENT_DEFINITIONS.md](getting-started/ENVIRONMENT_DEFINITIONS.md) | Demo vs Pilot vs Production modes |

---

### [architecture/](architecture/) - How It Works
Technical design and reference documentation.

| Document | What It Covers |
|----------|----------------|
| [CHECK_REVIEW_CONSOLE_TECHNICAL_GUIDE.md](architecture/CHECK_REVIEW_CONSOLE_TECHNICAL_GUIDE.md) | Complete technical reference (detailed) |
| [SECURITY_ARCHITECTURE.md](architecture/SECURITY_ARCHITECTURE.md) | Authentication, encryption, access control |
| [API.md](architecture/API.md) | API endpoints reference |
| [AUDIT_EVIDENCE_MODEL.md](architecture/AUDIT_EVIDENCE_MODEL.md) | How audit trails work |
| [DEFINITIONS.md](architecture/DEFINITIONS.md) | Glossary of terms |

---

### [deployment/](deployment/) - Running the System
Operations, maintenance, and troubleshooting.

| Document | What It Covers |
|----------|----------------|
| [BANK_ONBOARDING_GUIDE.md](deployment/BANK_ONBOARDING_GUIDE.md) | End-to-end onboarding process |
| [PILOT_RUNBOOK.md](deployment/PILOT_RUNBOOK.md) | Day-to-day operations procedures |
| [DEPLOYMENT.md](deployment/DEPLOYMENT.md) | Infrastructure setup (Kubernetes, Docker) |
| [CAPACITY_PLANNING.md](deployment/CAPACITY_PLANNING.md) | Server sizing and scaling |
| [INCIDENT_RESPONSE.md](deployment/INCIDENT_RESPONSE.md) | What to do when things break |
| [DISASTER_RECOVERY_DRILL.md](deployment/DISASTER_RECOVERY_DRILL.md) | DR testing procedures |
| [ROLLBACK_PROCEDURES.md](deployment/ROLLBACK_PROCEDURES.md) | How to undo changes |

---

### [connectors/](connectors/) - Bank Integration
Connecting the system to your bank's infrastructure.

| Document | What It Covers |
|----------|----------------|
| [CONNECTOR_SETUP.md](connectors/CONNECTOR_SETUP.md) | Installing and configuring connectors |
| [CONNECTOR_PRECONDITIONS_CHECKLIST.md](connectors/CONNECTOR_PRECONDITIONS_CHECKLIST.md) | What you need before installation |
| [RESPONSIBILITY_MATRIX.md](connectors/RESPONSIBILITY_MATRIX.md) | Who does what (bank vs vendor) |

---

### [security/](security/) - Security & Compliance
For auditors, compliance teams, and security reviewers.

| Document | What It Covers |
|----------|----------------|
| [THREAT_MODEL.md](security/THREAT_MODEL.md) | Security threats and how we address them |
| [SOC2_OPERATIONAL_CONTROLS.md](security/SOC2_OPERATIONAL_CONTROLS.md) | SOC2 control mappings |
| [REGULATORY_FRAMEWORK.md](security/REGULATORY_FRAMEWORK.md) | Banking regulation compliance |
| [RBAC.md](security/RBAC.md) | User roles and permissions |
| [REQUIREMENTS.md](security/REQUIREMENTS.md) | Security and compliance requirements |

---

### [testing/](testing/) - Quality Assurance
Test cases and acceptance criteria.

| Document | What It Covers |
|----------|----------------|
| [ACCEPTANCE_CRITERIA.md](testing/ACCEPTANCE_CRITERIA.md) | Test scenarios for each feature |

---

### [sales/](sales/) - Sales & Evaluation
For prospects evaluating the product.

| Document | What It Covers |
|----------|----------------|
| [SALES_FEATURES_BENEFITS.md](sales/SALES_FEATURES_BENEFITS.md) | Product capabilities and ROI |
| [VENDOR_FAQ.md](sales/VENDOR_FAQ.md) | Common vendor risk questions |

---

## Common Questions

### "Where do I start?"
→ [Setup Path Decision Tree](getting-started/BANK_PILOT_SETUP_PATHS.md) - Takes 5 minutes to read

### "How long does setup take?"
| Setup Type | Timeline |
|------------|----------|
| Demo (evaluation) | 1 day |
| Basic pilot | 1-2 weeks |
| Full integration | 3-4 weeks |

### "Who do I contact for help?"
| Question Type | Contact |
|---------------|---------|
| Sales/Pricing | sales@checkreview.com |
| Technical Setup | onboarding@checkreview.com |
| Support Issues | support@checkreview.com |

---

## Document Maintenance

| Folder | Last Updated | Owner |
|--------|--------------|-------|
| getting-started/ | January 2026 | Product |
| architecture/ | January 2026 | Engineering |
| deployment/ | January 2026 | DevOps |
| connectors/ | January 2026 | Engineering |
| security/ | January 2026 | Security |
| testing/ | January 2026 | QA |
| sales/ | January 2026 | Sales |

---

*Documentation Version: 2.0 | Reorganized: January 2026*
