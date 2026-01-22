# Bank Pilot Setup: A-to-Z Quick Start

> **Purpose**: Get a bank from "signed contract" to "live pilot" in the shortest path
> **Time**: 2-4 weeks typical
> **Audience**: Implementation team, Bank IT contacts

This guide consolidates the critical path. For deep dives, see the linked detailed docs.

---

## Overview: What Gets Deployed

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              BANK NETWORK                                    │
│  ┌─────────────────────┐                                                    │
│  │  Connector A        │◄──── Images stay in bank network                   │
│  │  (optional - for    │      until explicitly requested                    │
│  │   real images)      │                                                    │
│  └─────────────────────┘                                                    │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │ HTTPS + JWT
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            YOUR INFRASTRUCTURE                               │
│                                                                             │
│   ┌─────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐              │
│   │  Nginx  │───▶│ Frontend │    │ Backend  │───▶│ Postgres │              │
│   │  (TLS)  │───▶│ (React)  │    │ (FastAPI)│───▶│  Redis   │              │
│   └─────────┘    └──────────┘    └──────────┘    └──────────┘              │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Two deployment modes:**
- **Demo Mode**: Synthetic data, no bank integration needed. Good for initial demos.
- **Live Mode**: Real bank data via connectors. Required for actual pilot.

---

## Phase 1: Initial Demo (Day 1)

Get the system running with synthetic data to show stakeholders.

### Step 1.1: Clone and Configure

```bash
git clone <repository-url>
cd Check/docker
cp .env.pilot.example .env.pilot
```

### Step 1.2: Generate Secrets

```bash
# Run this 4 times, save each output
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

Edit `.env.pilot`:
```bash
# Database
POSTGRES_USER=check_review_user
POSTGRES_PASSWORD=<generated-password>
POSTGRES_DB=check_review

# Application Secrets (paste your generated values)
SECRET_KEY=<generated-1>
CSRF_SECRET_KEY=<generated-2>
NETWORK_PEPPER=<generated-3>
IMAGE_SIGNING_KEY=<generated-4>

# For demo mode
DEMO_MODE=true
CORS_ORIGINS='["https://localhost"]'
```

### Step 1.3: Generate TLS Certificates

```bash
mkdir -p certs
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout certs/server.key \
  -out certs/server.crt \
  -subj "/CN=localhost"
chmod 600 certs/server.key
```

### Step 1.4: Start Services

```bash
docker compose -f docker-compose.pilot.yml --env-file .env.pilot build
docker compose -f docker-compose.pilot.yml --env-file .env.pilot up -d
```

### Step 1.5: Verify

```bash
# Check all services are healthy
docker compose -f docker-compose.pilot.yml ps

# Test the endpoints
curl -k https://localhost/health
curl -k https://localhost/api/v1/health
```

### Step 1.6: Login

Open https://localhost in browser. Demo credentials (from seed data):
- `reviewer` / `reviewer123` - Basic reviewer
- `supervisor` / `supervisor123` - Supervisor access
- `administrator` / `admin123` - Full admin

**You now have a working demo.** Show this to bank stakeholders.

---

## Phase 2: Bank Onboarding (Week 1)

Collect information needed for live pilot.

### Step 2.1: Send Intake Questionnaire

Send the bank [BANK_INTAKE_QUESTIONNAIRE.md](./BANK_INTAKE_QUESTIONNAIRE.md) to collect:

| Information | Why We Need It |
|-------------|----------------|
| Image storage paths | Configure connector allowlist |
| Core banking system | Map context file format |
| SFTP credentials | Exchange decision files |
| Network contacts | Troubleshoot connectivity |

### Step 2.2: Provision Tenant

Create their tenant in the admin panel:

1. Login as administrator
2. Navigate to **Admin → Tenants → Create**
3. Generate `tenant_id` (or use bank's identifier)
4. Note the tenant credentials for bank admin

### Step 2.3: Exchange Keys (if using Connector A)

For banks deploying the on-premise image connector:

```bash
# Bank generates their key pair
cd connector
python scripts/mint_token.py --generate-keys

# Bank sends you: connector_public.pem
# You send bank: saas_public.pem (your verification key)
```

### Step 2.4: Define Scope

| Decision | Options | Recommendation |
|----------|---------|----------------|
| Data mode | Demo (synthetic) vs Live (real) | Start with Demo for training |
| Image source | Demo fixtures vs Bank connector | Demo first, connector week 2 |
| User count | 2-5 pilot users | Start small |
| Queue scope | All checks vs subset | Subset (one branch) |

---

## Phase 3: Production Configuration (Week 2)

Harden the deployment for pilot use.

### Step 3.1: Update Environment

Edit `.env.pilot`:
```bash
# Disable demo mode for real data
DEMO_MODE=false

# Set actual domain
CORS_ORIGINS='["https://pilot.yourbank.com"]'

# Optionally expose docs for pilot (disable in production)
# EXPOSE_DOCS=true
```

### Step 3.2: Real TLS Certificates

Replace self-signed certs with real ones:
```bash
# From your CA or Let's Encrypt
cp /path/to/real/certificate.crt docker/certs/server.crt
cp /path/to/real/private.key docker/certs/server.key
chmod 600 docker/certs/server.key
```

### Step 3.3: Run Migrations

```bash
# Ensure database is ready
docker compose -f docker-compose.pilot.yml up -d db
docker compose -f docker-compose.pilot.yml ps db  # Wait for "healthy"

# Run migrations
docker compose -f docker-compose.pilot.yml run --rm backend alembic upgrade head

# Verify
docker compose -f docker-compose.pilot.yml run --rm backend alembic current
```

### Step 3.4: Restart with Production Config

```bash
docker compose -f docker-compose.pilot.yml --env-file .env.pilot down
docker compose -f docker-compose.pilot.yml --env-file .env.pilot up -d
```

### Step 3.5: Register Image Connector (if applicable)

If bank deployed Connector A:

1. Login as administrator
2. Navigate to **Admin → Image Connectors → Add**
3. Enter:
   - Connector ID: `bank-001-prod`
   - Base URL: `https://connector.bank.internal:8443`
   - Public Key: (paste from bank)
4. Click **Test Connection** - must succeed

---

## Phase 4: User Setup (Week 2-3)

### Step 4.1: Create Bank Users

Use the secure admin script:
```bash
cd backend
python -m scripts.create_admin
# Follow interactive prompts
```

Or via API:
```bash
curl -X POST https://pilot.yourbank.com/api/v1/users \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "jsmith",
    "email": "jsmith@bank.com",
    "full_name": "Jane Smith",
    "role": "reviewer",
    "tenant_id": "bank-001"
  }'
```

### Step 4.2: Role Assignment

| Role | Permissions | Typical Users |
|------|-------------|---------------|
| `reviewer` | View, review, decide on checks | Tellers, operations staff |
| `senior_reviewer` | Above + dual control approval | Senior staff |
| `supervisor` | Above + reassign, manage queues | Team leads |
| `administrator` | Above + user management, policies | Bank ops manager |
| `auditor` | Read-only access to all audit logs | Compliance team |

See [RBAC.md](./RBAC.md) for detailed permissions.

### Step 4.3: User Training

Provide users with:
1. Login URL and initial credentials
2. Password change requirement (first login)
3. Quick reference card (review workflow)
4. Escalation contacts

---

## Phase 5: Go-Live Verification (Week 3-4)

### Step 5.1: Pre-Flight Checklist

Verify each item before go-live:

| Check | Command | Expected |
|-------|---------|----------|
| Services healthy | `docker compose ps` | All "healthy" |
| API responds | `curl https://pilot/api/v1/health` | `{"status":"healthy"}` |
| TLS valid | `openssl s_client -connect pilot:443` | Valid cert chain |
| Security headers | `curl -I https://pilot/` | HSTS, X-Frame-Options present |
| Login works | Browser test | Successful auth |
| Images load | View check detail | Image renders |

### Step 5.2: Security Verification

```bash
# Verify security headers
curl -sI https://pilot.yourbank.com | grep -E "(Strict-Transport|X-Frame|X-Content)"

# Expected output:
# Strict-Transport-Security: max-age=31536000; includeSubDomains
# X-Frame-Options: SAMEORIGIN
# X-Content-Type-Options: nosniff
```

### Step 5.3: Pilot Kickoff

- [ ] All connectors green in health dashboard
- [ ] Pilot users have credentials and training
- [ ] Escalation path documented and tested
- [ ] Backup verified (test restore)
- [ ] Monitoring/alerting configured

**Go/No-Go Decision Point**

---

## Phase 6: Pilot Operations (Weeks 4+)

### Daily Monitoring

```bash
# Check service health
docker compose -f docker-compose.pilot.yml ps

# View recent logs
docker compose -f docker-compose.pilot.yml logs --tail=100 backend

# Check for errors
docker compose -f docker-compose.pilot.yml logs backend | grep -i error
```

### Weekly Tasks

- [ ] Review audit logs for anomalies
- [ ] Check decision throughput metrics
- [ ] Collect user feedback
- [ ] Verify backup integrity

### Backup Schedule

```bash
# Manual backup (automate via cron)
docker exec check_review_db pg_dump -U check_review_user -d check_review \
  --format=custom > backup_$(date +%Y%m%d).dump
```

See [PILOT_RUNBOOK.md](./PILOT_RUNBOOK.md) for detailed backup/restore procedures.

---

## Troubleshooting Quick Reference

| Symptom | Likely Cause | Fix |
|---------|--------------|-----|
| Can't login | Wrong credentials or DB issue | Check backend logs, verify user exists |
| Images don't load | Connector not configured | Register connector in admin panel |
| 502 Bad Gateway | Backend not running | `docker compose logs backend` |
| Slow performance | Resource constraints | Check `docker stats`, increase limits |
| TLS errors | Certificate issue | Verify cert chain, check expiry |

See [PILOT_RUNBOOK.md → Troubleshooting](./PILOT_RUNBOOK.md#troubleshooting) for more.

---

## Document Map

| Document | Use When |
|----------|----------|
| **This guide** | First-time setup, quick reference |
| [BANK_ONBOARDING_GUIDE.md](./BANK_ONBOARDING_GUIDE.md) | Detailed connector setup, bank coordination |
| [PILOT_RUNBOOK.md](./PILOT_RUNBOOK.md) | Day-to-day operations, backup/restore |
| [DEPLOYMENT.md](./DEPLOYMENT.md) | Kubernetes deployment, scaling |
| [CONNECTOR_SETUP.md](./CONNECTOR_SETUP.md) | Bank-side connector deep dive |
| [RBAC.md](./RBAC.md) | Role and permission details |
| [INCIDENT_RESPONSE.md](./INCIDENT_RESPONSE.md) | When things break |
| [ROLLBACK_PROCEDURES.md](./ROLLBACK_PROCEDURES.md) | Emergency rollback |

---

## Support

| Severity | Response | Contact |
|----------|----------|---------|
| P1 - System down | 15 min | On-call page |
| P2 - Degraded | 2 hours | support@checkreview.com |
| P3 - Question | 24 hours | support@checkreview.com |

---

*Version 1.0 - January 2026*
