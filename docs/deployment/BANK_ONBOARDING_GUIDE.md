# Bank Onboarding & Connector Setup – End-to-End Technical Guide

> **Document Purpose**: Walk a bank from "signed NDA" → "checks visible in review console"
> **Audience**: Bank IT, InfoSec, External Developers, SaaS Administrator
> **Last Updated**: January 2026

---

## Quick Reference

| Phase | Duration | Bank Effort | SaaS Effort | Blocker Risk |
|-------|----------|-------------|-------------|--------------|
| 0. Prerequisites | 1-2 weeks | Gather info | Provision tenant | Low |
| 1. Connector A (Images) | 2-4 weeks | Deploy connector | Configure SaaS | **High** |
| 2. Connector C (Context) | 1-2 weeks | Export context file | Configure import | Medium |
| 3. Connector B (Decisions) | 1-2 weeks | Receive test file | Configure export | Medium |
| 4. Pilot & Go-Live | 1-2 weeks | User training | Support | Low |

**Critical Path**: Connector A is the longest pole. Start here.

---

## Phase 0: Prerequisites & Planning

### 0.1 What You (SaaS) Do

1. **Provision tenant** in Check Review Console
   - Generate `tenant_id` (UUID format)
   - Configure demo mode for initial testing
   - Create admin user credentials for bank

2. **Send bank onboarding package**:
   - This document
   - Technical contacts (your email, support channel)
   - Security questionnaire (if not already completed)
   - Network requirements summary

3. **Schedule kickoff call** (30 min)
   - Walk through architecture diagram
   - Identify bank IT contact + InfoSec contact
   - Set milestone dates

### 0.2 What Bank Does

1. **Identify key contacts**:
   | Role | Responsibility |
   |------|----------------|
   | IT Lead | Connector deployment, firewall rules |
   | InfoSec | Security review, key management |
   | Core Banking | Context file export, decision file import |
   | Business Owner | User setup, training, acceptance |

2. **Gather technical details**:
   - [ ] Image storage location (UNC path format: `\\server\share\path`)
   - [ ] Core banking system (Fiserv Premier, Jack Henry, FIS, etc.)
   - [ ] SFTP server for file exchange (if applicable)
   - [ ] Network egress requirements (can connect to cloud IPs?)

3. **Decision point**: On-premise connector vs. VPN tunnel
   - **Connector A (recommended)**: Bank deploys lightweight Python service
   - **VPN tunnel (alternative)**: More complex, requires ongoing network ops

### 0.3 Artifacts Exchanged

| From | To | Artifact | Purpose |
|------|----|----------|---------|
| SaaS | Bank | Tenant credentials | Admin login |
| SaaS | Bank | RSA public key | Token verification |
| Bank | SaaS | Connector public key | Token signing |
| Bank | SaaS | Image path format | Path allowlist |
| Bank | SaaS | SFTP credentials | Context/decision files |

---

## Phase 1: Connector A – Image Access (Critical Path)

> **Goal**: Bank check images visible in SaaS review console

### 1.1 Architecture Decision

```
┌─────────────────────────────┐        ┌────────────────────────────┐
│       BANK NETWORK          │        │      CLOUD (SaaS)          │
│                             │        │                            │
│  ┌───────────────────────┐  │        │  ┌──────────────────────┐  │
│  │   Connector A         │◄─┼────────┼──┤  Check Review App    │  │
│  │   (Python service)    │  │ HTTPS  │  │                      │  │
│  └───────────┬───────────┘  │ +JWT   │  └──────────────────────┘  │
│              │ SMB          │        │                            │
│  ┌───────────▼───────────┐  │        │                            │
│  │   Image Storage       │  │        │                            │
│  │   (UNC shares)        │  │        │                            │
│  └───────────────────────┘  │        │                            │
└─────────────────────────────┘        └────────────────────────────┘
```

**Why this architecture**:
- Images never leave bank network unless explicitly requested
- JWT tokens are short-lived (60-120 seconds)
- Bank controls path allowlist (can't request arbitrary files)
- No VPN required (outbound HTTPS from SaaS to bank)

### 1.2 What Bank IT Does

#### Step 1: Prepare Infrastructure (Week 1)

1. **Provision server for connector**
   - Linux (preferred) or Windows
   - Python 3.11+ installed
   - 2 CPU, 4GB RAM minimum
   - Network access to image storage (SMB/CIFS)

2. **Create service account**
   ```powershell
   # Windows example
   New-LocalUser -Name "svc_connector" -Description "Check Review Connector"
   # Grant read-only access to image shares
   icacls "\\tn-director-pro\Checks" /grant "svc_connector:(OI)(CI)R"
   ```

3. **Configure firewall**
   ```
   Inbound:  TCP 8443 from SaaS IP ranges (we'll provide)
   Outbound: TCP 445 to image storage servers
   ```

4. **Obtain TLS certificate**
   - Production: Trusted CA (DigiCert, Let's Encrypt, internal CA)
   - Testing: Self-signed is OK temporarily

#### Step 2: Deploy Connector (Week 2)

```bash
# Clone connector code (or receive ZIP from SaaS)
cd /opt
git clone <connector-repo> check-connector
cd check-connector/connector

# Create virtual environment
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Generate RSA key pair
python scripts/mint_token.py --generate-keys
# Creates: keys/connector_private.pem (SEND TO SaaS)
#          keys/connector_public.pem (keep for verification)
```

#### Step 3: Configure Connector

```bash
cp .env.example .env
```

Edit `.env`:
```env
# Identity (coordinate with SaaS)
CONNECTOR_MODE=BANK
CONNECTOR_ID=bank-001-prod

# Network
CONNECTOR_HOST=0.0.0.0
CONNECTOR_PORT=8443
CONNECTOR_TLS_CERT_PATH=/etc/ssl/connector/cert.pem
CONNECTOR_TLS_KEY_PATH=/etc/ssl/connector/key.pem

# Authentication - public key from SaaS
CONNECTOR_JWT_PUBLIC_KEY_PATH=/opt/check-connector/keys/saas_public.pem

# CRITICAL: Path allowlist (only these paths can be accessed)
CONNECTOR_ALLOWED_SHARE_ROOTS=\\\\tn-director-pro\\Checks\\Transit\\,\\\\tn-director-pro\\Checks\\OnUs\\

# Security
CONNECTOR_MAX_IMAGE_MB=50
CONNECTOR_RATE_LIMIT_REQUESTS_PER_MINUTE=100
```

#### Step 4: Start and Verify

```bash
# Start connector (production: use systemd or supervisor)
uvicorn app.main:app \
  --host 0.0.0.0 \
  --port 8443 \
  --ssl-keyfile /etc/ssl/connector/key.pem \
  --ssl-certfile /etc/ssl/connector/cert.pem \
  --workers 4

# Verify health endpoint
curl -k https://localhost:8443/healthz
# Expected: {"status": "healthy", "mode": "BANK", ...}
```

### 1.3 What You (SaaS) Do

1. **Register connector in admin panel**
   - Navigate to Admin → Image Connectors → Add
   - Enter connector ID, base URL, public key
   - Click "Test Connection" – must succeed

2. **Configure tenant**
   ```
   Connector URL: https://connector.bank.example.com:8443
   Connector ID: bank-001-prod
   Public Key: [paste from bank]
   ```

3. **Verify end-to-end**
   - Load a check item in review console
   - Image should render from bank connector

### 1.4 Verification Checklist

| Test | Command/Action | Expected Result |
|------|----------------|-----------------|
| Health check | `curl https://connector:8443/healthz` | `{"status": "healthy"}` |
| JWT auth | SaaS connection test button | "Connection successful" |
| Image fetch | Load check in review console | Image renders |
| Path block | Request file outside allowlist | 403 Forbidden |
| Rate limit | 150 requests in 60 seconds | 429 after 100 |

### 1.5 Common Blockers

| Issue | Root Cause | Resolution |
|-------|-----------|------------|
| Connection timeout | Firewall blocking | Whitelist SaaS IPs |
| 401 Unauthorized | Key mismatch | Verify public/private key pair |
| 404 Not Found | Path not in allowlist | Add path to ALLOWED_SHARE_ROOTS |
| TLS error | Certificate issue | Check cert chain, expiry |
| SMB access denied | Service account | Grant read access to shares |

---

## Phase 2: Connector C – Account Context (Enrichment)

> **Goal**: Account history/balances available for review decisions

### 2.1 Architecture

```
┌─────────────────────────────┐        ┌────────────────────────────┐
│       BANK NETWORK          │        │      CLOUD (SaaS)          │
│                             │        │                            │
│  ┌───────────────────────┐  │        │  ┌──────────────────────┐  │
│  │   Core Banking        │  │        │  │  Check Review App    │  │
│  │   (Fiserv, JH, etc)   │  │        │  │                      │  │
│  └───────────┬───────────┘  │        │  └──────────┬───────────┘  │
│              │ Export       │        │             │ SFTP Poll    │
│  ┌───────────▼───────────┐  │        │  ┌──────────▼───────────┐  │
│  │   SFTP Server         │◄─┼────────┼──┤  Connector C         │  │
│  │   /outbound/context/  │  │ SFTP   │  │  (Context Import)    │  │
│  └───────────────────────┘  │        │  └──────────────────────┘  │
└─────────────────────────────┘        └────────────────────────────┘
```

### 2.2 What Bank Core Team Does

1. **Create daily export job** from core banking system

   Required fields (we provide mapping for major cores):
   | Field | Description | Example |
   |-------|-------------|---------|
   | account_number | Primary account identifier | 1234567890 |
   | current_balance | Current available balance | 5432.10 |
   | average_balance_30d | 30-day average | 4500.00 |
   | account_open_date | Date opened | 2020-03-15 |
   | check_count_30d | Checks written in 30 days | 12 |
   | returned_item_count | Returns in 12 months | 0 |
   | account_type | Type code | CHECKING |

2. **Place file on SFTP server**
   - Location: `/outbound/account_context/`
   - Naming: `ACCT_CONTEXT_YYYYMMDD.csv`
   - Schedule: Daily before 6 AM local

3. **Create SFTP credentials for SaaS**
   ```
   Username: check_review_context
   Auth: SSH key (preferred) or password
   Path: Read access to /outbound/account_context/
   ```

### 2.3 What You (SaaS) Do

1. **Configure context connector**
   ```json
   POST /v1/item-context-connectors
   {
     "name": "First National Context Feed",
     "sftp_host": "sftp.bank.example.com",
     "sftp_username": "check_review_context",
     "sftp_remote_path": "/outbound/account_context/",
     "file_pattern": "ACCT_CONTEXT_*.csv",
     "core_system_type": "FISERV_PREMIER",
     "import_schedule": "0 6 * * *"
   }
   ```

2. **Test import**
   - Trigger manual import
   - Verify records match to check items
   - Check enrichment appears in review console

### 2.4 Verification

- [ ] SFTP connection succeeds
- [ ] File downloads correctly
- [ ] Records parse without errors
- [ ] Match rate > 95% (most accounts found)
- [ ] Context visible in check review detail

---

## Phase 3: Connector B – Decision Output

> **Goal**: Approved decisions flow back to bank systems

### 3.1 Architecture

```
┌─────────────────────────────┐        ┌────────────────────────────┐
│       BANK NETWORK          │        │      CLOUD (SaaS)          │
│                             │        │                            │
│  ┌───────────────────────┐  │        │  ┌──────────────────────┐  │
│  │   Core Banking        │  │        │  │  Check Review App    │  │
│  │   (Decision Import)   │  │        │  │                      │  │
│  └───────────▲───────────┘  │        │  └──────────┬───────────┘  │
│              │ Import       │        │             │              │
│  ┌───────────┴───────────┐  │        │  ┌──────────▼───────────┐  │
│  │   SFTP Server         │◄─┼────────┼──┤  Connector B         │  │
│  │   /inbound/decisions/ │  │ SFTP   │  │  (Batch Export)      │  │
│  └───────────────────────┘  │        │  └──────────────────────┘  │
└─────────────────────────────┘        └────────────────────────────┘
```

### 3.2 What You (SaaS) Do

1. **Configure bank export settings**
   ```json
   POST /v1/connector/configs
   {
     "bank_id": "bank-001",
     "file_format": "CSV",
     "delivery_method": "SFTP",
     "sftp_host": "sftp.bank.example.com",
     "sftp_username": "check_review_decisions",
     "sftp_remote_path": "/inbound/decisions/",
     "file_naming_pattern": "CRC_{bank_id}_{date}_{sequence}.csv",
     "dual_control_threshold": 5000.00
   }
   ```

2. **Coordinate file format** with bank core team
   - Provide sample file
   - Confirm field positions/names
   - Agree on acknowledgement format

### 3.3 What Bank Core Team Does

1. **Create SFTP credentials for SaaS**
   ```
   Username: check_review_decisions
   Auth: SSH key (preferred)
   Path: Write to /inbound/decisions/, read /outbound/acks/
   ```

2. **Configure import job** in core banking
   - Poll `/inbound/decisions/` for new files
   - Process decision records
   - Generate acknowledgement file

3. **Test with sample file**
   - We send test decision file
   - Bank confirms import succeeds
   - Bank sends acknowledgement

### 3.4 Verification

- [ ] SFTP upload succeeds
- [ ] File format accepted by core system
- [ ] Decisions update check status in core
- [ ] Acknowledgement file generated
- [ ] SaaS processes acknowledgement
- [ ] Reconciliation report matches

---

## Phase 4: Pilot & Go-Live

### 4.1 Pilot Scope

| Criteria | Recommendation |
|----------|----------------|
| Duration | 2 weeks minimum |
| Users | 2-5 reviewers |
| Volume | Subset of queue (e.g., one branch) |
| Decision types | All (pay, return, hold, escalate) |

### 4.2 Pilot Checklist

**Day 1**:
- [ ] All connectors green in health dashboard
- [ ] Training completed for pilot users
- [ ] Escalation path documented

**Week 1**:
- [ ] 100+ decisions processed without error
- [ ] Dual control working for high-value items
- [ ] Audit logs capturing all actions

**Week 2**:
- [ ] Any issues from Week 1 resolved
- [ ] Performance acceptable (image load < 2s)
- [ ] User feedback collected

### 4.3 Go-Live Gate

| Requirement | Status |
|-------------|--------|
| All connectors passing health checks | |
| Dual control tested and working | |
| Security review completed | |
| Audit logging verified | |
| DR/rollback plan documented | |
| Support escalation path defined | |

---

## Security Checklist

### Connector A (Bank-Side)

| Control | Status | Notes |
|---------|--------|-------|
| TLS 1.2+ enforced | | Required for production |
| RSA 2048+ key pair | | Generated fresh for each bank |
| Path allowlist configured | | Only approved UNC paths |
| Service account minimal privilege | | Read-only to image shares |
| Rate limiting enabled | | 100 req/min default |
| Audit logging enabled | | All requests logged |
| JTI replay protection | | Automatic, 5-min window |

### Connector B & C (SaaS-Side)

| Control | Status | Notes |
|---------|--------|-------|
| SFTP key-based auth | | Preferred over password |
| Credentials encrypted at rest | | Vault storage |
| Dual control for high-value | | $5000+ threshold |
| Evidence snapshots sealed | | SHA-256 hash chain |

### Production Secrets Validated

The following must be set in production (not defaults):
- [ ] `SECRET_KEY` (32+ chars)
- [ ] `CSRF_SECRET_KEY` (32+ chars)
- [ ] `NETWORK_PEPPER` (32+ chars)
- [ ] `CONNECTOR_JWT_PRIVATE_KEY` (RSA key, 100+ chars)

---

## Document References

| Document | Purpose | When to Use |
|----------|---------|-------------|
| [CONNECTOR_SETUP.md](./CONNECTOR_SETUP.md) | Detailed connector configuration | Technical implementation |
| [DEPLOYMENT.md](./DEPLOYMENT.md) | Environment variables, infrastructure | DevOps setup |
| [RBAC.md](./RBAC.md) | Roles and permissions | User provisioning |
| [INCIDENT_RESPONSE.md](./INCIDENT_RESPONSE.md) | Handling failures | When things break |
| [ROLLBACK_PROCEDURES.md](./ROLLBACK_PROCEDURES.md) | Reverting changes | Emergency recovery |
| [PILOT_RUNBOOK.md](./PILOT_RUNBOOK.md) | Pilot execution details | During pilot phase |

---

## Support & Escalation

| Severity | Response Time | Contact |
|----------|---------------|---------|
| P1 - Production down | 15 minutes | [On-call page] |
| P2 - Degraded service | 2 hours | support@checkreview.com |
| P3 - Question/issue | 24 hours | support@checkreview.com |

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-01 | Initial release |
