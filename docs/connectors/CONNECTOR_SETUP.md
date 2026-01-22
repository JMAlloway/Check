# Connector Setup Guide

This guide provides comprehensive setup instructions for all three connectors in the Check Review Console system.

## Connector Overview

The Check Review Console uses three specialized connectors for bank integration:

| Connector | Direction | Purpose | Location |
|-----------|-----------|---------|----------|
| **Connector A** | Bank → SaaS | Serves check images from bank storage | Bank network |
| **Connector B** | SaaS → Bank | Routes approved decisions to bank systems | SaaS (file delivery) |
| **Connector C** | Bank → SaaS | Imports account context data | SaaS (SFTP polling) |

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              CLOUD (SaaS)                                    │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                    Check Review Console                                │  │
│  │                                                                        │  │
│  │  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐            │  │
│  │  │ Connector A  │    │ Connector B  │    │ Connector C  │            │  │
│  │  │   Manager    │    │ Batch Export │    │ SFTP Import  │            │  │
│  │  └──────┬───────┘    └──────┬───────┘    └──────┬───────┘            │  │
│  └─────────┼───────────────────┼───────────────────┼────────────────────┘  │
└────────────┼───────────────────┼───────────────────┼────────────────────────┘
             │ HTTPS+JWT         │ SFTP/File         │ SFTP Poll
             ▼                   ▼                   ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                            BANK NETWORK                                     │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐                 │
│  │  Connector A │    │  File Drop   │    │  SFTP Server │                 │
│  │  (On-Prem)   │    │  Location    │    │  (Context)   │                 │
│  └──────┬───────┘    └──────────────┘    └──────────────┘                 │
│         │ SMB/CIFS                                                         │
│  ┌──────▼───────┐                                                          │
│  │ Image Storage│                                                          │
│  │ (Director)   │                                                          │
│  └──────────────┘                                                          │
└────────────────────────────────────────────────────────────────────────────┘
```

---

## Connector A: Image Connector

### Purpose

Connector A serves check images securely from the bank's on-premise storage to the cloud SaaS application. It runs inside the bank's network and responds to authenticated image requests.

### Architecture

- **Location**: Bank network (on-premise)
- **Protocol**: HTTPS with TLS 1.2+
- **Authentication**: RS256 JWT tokens (60-120 second expiry)
- **Storage Access**: SMB/CIFS to image shares

### Prerequisites

- Python 3.11+
- TLS certificate (production: trusted CA; testing: self-signed)
- RSA key pair for JWT authentication
- Network access to image storage shares
- Service account with read-only access to image directories

### Installation

#### Step 1: Clone and Install Dependencies

```bash
cd connector
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

#### Step 2: Generate RSA Key Pair

```bash
python scripts/mint_token.py --generate-keys
```

This creates:
- `keys/connector_private.pem` - Keep secure, used by SaaS to sign tokens
- `keys/connector_public.pem` - Configure on connector for token verification

#### Step 3: Configure Environment

```bash
cp .env.example .env
```

Edit `.env` with your settings:

```env
# Mode: DEMO for testing, BANK for production
CONNECTOR_MODE=DEMO

# Unique identifier (must match SaaS registration)
CONNECTOR_ID=connector-prod-001

# Network binding
CONNECTOR_HOST=0.0.0.0
CONNECTOR_PORT=8443

# TLS certificates (required for production)
CONNECTOR_TLS_CERT_PATH=/path/to/cert.pem
CONNECTOR_TLS_KEY_PATH=/path/to/key.pem

# JWT public key for token verification
CONNECTOR_JWT_PUBLIC_KEY_PATH=./keys/connector_public.pem

# Allowed image share paths (comma-separated, escape backslashes)
CONNECTOR_ALLOWED_SHARE_ROOTS=\\\\tn-director-pro\\Checks\\Transit\\,\\\\tn-director-pro\\Checks\\OnUs\\

# Image handling
CONNECTOR_MAX_IMAGE_MB=50
CONNECTOR_CACHE_TTL_SECONDS=60
CONNECTOR_CACHE_MAX_ITEMS=100

# Rate limiting
CONNECTOR_RATE_LIMIT_REQUESTS_PER_MINUTE=100

# Logging
CONNECTOR_LOG_LEVEL=INFO
```

#### Step 4: Generate Demo Fixtures (Demo Mode Only)

```bash
python scripts/generate_demo_fixtures.py
```

#### Step 5: Start the Connector

**Development:**
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8443 --reload
```

**Production:**
```bash
uvicorn app.main:app \
  --host 0.0.0.0 \
  --port 8443 \
  --ssl-keyfile /path/to/key.pem \
  --ssl-certfile /path/to/cert.pem \
  --workers 4
```

#### Step 6: Verify Installation

```bash
# Health check (no auth required)
curl -k https://localhost:8443/healthz

# Test with token
TOKEN=$(python scripts/mint_token.py --curl)
curl -k -H "Authorization: Bearer $TOKEN" \
  "https://localhost:8443/v1/images/by-item?trace=12374628&date=2024-01-15&side=front" \
  -o front.png
```

### SaaS Registration

1. Log in to Check Review Console as admin
2. Navigate to **Admin → Image Connectors**
3. Click **Add Connector**
4. Enter configuration:
   - **Connector ID**: `connector-prod-001` (must match connector config)
   - **Name**: Human-friendly display name
   - **Base URL**: `https://connector.bank.local:8443`
   - **Public Key**: Paste contents of `connector_public.pem`
5. Click **Test Connection**
6. Enable the connector

### Security Configuration

#### TLS Certificate

Production requires TLS 1.2+ with certificates from a trusted CA:

```bash
# Self-signed for testing only
openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes
```

#### Service Account

Create a read-only service account for accessing image shares:

```powershell
# Windows
New-LocalUser -Name "svc_connector" -Description "Connector Service Account"
icacls "\\tn-director-pro\Checks" /grant "svc_connector:(OI)(CI)R"
```

#### Firewall Rules

```
Inbound:  Port 8443 TCP from SaaS IP ranges
Outbound: Port 445 TCP to file servers (SMB)
```

### API Endpoints

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/healthz` | GET | No | Health check |
| `/v1/images/by-handle` | GET | JWT | Get image by UNC path |
| `/v1/images/by-item` | GET | JWT | Get image by trace/date |
| `/v1/items/lookup` | GET | JWT | Look up item metadata |

### Troubleshooting

| Issue | Solution |
|-------|----------|
| Connection refused | Check firewall, TLS cert, connector status |
| JWT validation failed | Verify key pair matches, check token expiry |
| Image not found | Check path allowlist, file existence, permissions |
| Decode failed | Verify TIFF format, check file size limits |

---

## Connector B: Batch Commit Connector

### Purpose

Connector B routes human-approved check review decisions to bank core systems via file-based integration. It generates batch files in configurable formats for downstream processing.

### Architecture

- **Location**: SaaS (cloud)
- **Direction**: Outbound (SaaS generates files for bank consumption)
- **Delivery**: SFTP, shared folder, message queue, or API callback
- **Control**: Dual control enforcement (reviewer + approver)

### Key Features

- File-based integration (no direct core writes)
- Multiple formats: CSV, Fixed-Width, XML, JSON
- Idempotent file generation with deterministic hashing
- Bank-specific configuration per tenant
- Acknowledgement processing and reconciliation
- Evidence snapshot capture for audit replay

### Configuration

#### Step 1: Create Bank Configuration

Use the API or admin interface to create a bank connector configuration:

```json
POST /v1/connector/configs
{
  "bank_id": "bank-001",
  "bank_name": "First National Bank",
  "file_format": "CSV",
  "delivery_method": "SFTP",
  "sftp_host": "sftp.bank.local",
  "sftp_port": 22,
  "sftp_username": "check_review",
  "sftp_remote_path": "/inbound/check_decisions/",
  "file_naming_pattern": "CRC_{bank_id}_{date}_{sequence}.csv",
  "include_header": true,
  "include_trailer": true,
  "field_delimiter": ",",
  "dual_control_threshold": 5000.00,
  "auto_generate_enabled": false
}
```

#### Step 2: Configure File Format

**CSV Format:**
```env
file_format=CSV
field_delimiter=,
include_header=true
include_trailer=true
```

**Fixed-Width Format:**
```json
{
  "file_format": "FIXED_WIDTH",
  "field_definitions": [
    {"name": "trace_number", "start": 1, "length": 15, "padding": "right", "pad_char": " "},
    {"name": "amount", "start": 16, "length": 12, "padding": "left", "pad_char": "0"},
    {"name": "decision", "start": 28, "length": 1, "padding": "right", "pad_char": " "},
    {"name": "timestamp", "start": 29, "length": 19, "padding": "right", "pad_char": " "}
  ]
}
```

**XML Format:**
```json
{
  "file_format": "XML",
  "xml_root_element": "CheckDecisions",
  "xml_record_element": "Decision",
  "xml_include_namespace": true
}
```

#### Step 3: Configure Delivery Method

**SFTP Delivery:**
```json
{
  "delivery_method": "SFTP",
  "sftp_host": "sftp.bank.local",
  "sftp_port": 22,
  "sftp_username": "check_review",
  "sftp_key_path": "/secrets/sftp_key",
  "sftp_remote_path": "/inbound/decisions/"
}
```

**Shared Folder:**
```json
{
  "delivery_method": "SHARED_FOLDER",
  "shared_folder_path": "\\\\fileserver\\check_decisions\\inbound\\"
}
```

**API Callback:**
```json
{
  "delivery_method": "API_CALLBACK",
  "callback_url": "https://api.bank.local/check-decisions",
  "callback_auth_header": "X-API-Key",
  "callback_auth_value": "${BANK_API_KEY}"
}
```

### Workflow

1. **Batch Creation**: System collects approved decisions into a batch
2. **Dual Control**: Second approver reviews and approves batch (if above threshold)
3. **File Generation**: System generates file in configured format
4. **Delivery**: File transmitted via configured method
5. **Acknowledgement**: Bank sends acknowledgement file
6. **Reconciliation**: Daily reconciliation report generated

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `GET /v1/connector/configs` | GET | List bank configurations |
| `POST /v1/connector/configs` | POST | Create configuration |
| `POST /v1/connector/batches` | POST | Create batch from approved decisions |
| `POST /v1/connector/batches/{id}/approve` | POST | Approve batch (dual control) |
| `POST /v1/connector/batches/{id}/generate-file` | POST | Generate output file |
| `POST /v1/connector/batches/{id}/transmit` | POST | Transmit file to bank |
| `POST /v1/connector/batches/{id}/acknowledge` | POST | Process acknowledgement |
| `GET /v1/connector/reconciliation` | GET | Get reconciliation report |

### File Naming Patterns

Available variables:
- `{bank_id}` - Bank identifier
- `{date}` - File date (YYYYMMDD)
- `{datetime}` - File datetime (YYYYMMDDHHmmss)
- `{sequence}` - Daily sequence number
- `{batch_id}` - Unique batch identifier

Example: `CRC_{bank_id}_{date}_{sequence}.csv` → `CRC_bank001_20240115_001.csv`

### Acknowledgement Processing

Configure acknowledgement file pattern for reconciliation:

```json
{
  "ack_file_pattern": "CRC_ACK_{bank_id}_{date}_*.csv",
  "ack_success_indicator": "SUCCESS",
  "ack_failure_indicator": "FAILED",
  "ack_polling_enabled": true,
  "ack_polling_interval_minutes": 15
}
```

---

## Connector C: Item Context Connector

### Purpose

Connector C imports daily account context data from bank SFTP servers to enrich check review decisions with account history, balances, and patterns.

### Architecture

- **Location**: SaaS (cloud)
- **Direction**: Inbound (SaaS polls bank SFTP for context files)
- **Protocol**: SFTP
- **Schedule**: Daily or on-demand imports

### Key Features

- SFTP polling and file download
- Field mapping templates for major core systems
- Context data enrichment (balances, check patterns, history)
- Per-record matching and error handling
- Comprehensive import tracking

### Configuration

#### Step 1: Create Context Connector

```json
POST /v1/item-context-connectors
{
  "bank_id": "bank-001",
  "name": "First National Context Feed",
  "sftp_host": "sftp.bank.local",
  "sftp_port": 22,
  "sftp_username": "context_export",
  "sftp_remote_path": "/outbound/account_context/",
  "file_pattern": "ACCT_CONTEXT_*.csv",
  "core_system_type": "FISERV_PREMIER",
  "import_schedule": "0 6 * * *",
  "enabled": true
}
```

#### Step 2: Configure Field Mapping

Use a predefined template or create custom mapping:

**Fiserv Premier Template:**
```json
{
  "core_system_type": "FISERV_PREMIER",
  "field_mapping": {
    "account_number": "ACCT_NBR",
    "current_balance": "CUR_BAL",
    "average_balance": "AVG_BAL_30",
    "account_open_date": "OPEN_DT",
    "check_count_30d": "CHK_CNT_30",
    "check_amount_avg": "CHK_AMT_AVG",
    "returned_item_count": "RTN_CNT_12M",
    "exception_count": "EXCPT_CNT_12M",
    "account_type": "ACCT_TYPE",
    "relationship_id": "REL_ID"
  }
}
```

**Jack Henry SilverLake Template:**
```json
{
  "core_system_type": "JH_SILVERLAKE",
  "field_mapping": {
    "account_number": "AccountNumber",
    "current_balance": "CurrentBalance",
    "average_balance": "AvgBalance30Day",
    "account_open_date": "DateOpened",
    "check_count_30d": "CheckCount30",
    "check_amount_avg": "AvgCheckAmount",
    "returned_item_count": "ReturnedItems12Mo",
    "exception_count": "ExceptionCount12Mo",
    "account_type": "AccountType",
    "relationship_id": "RelationshipID"
  }
}
```

**Custom Mapping:**
```json
{
  "core_system_type": "CUSTOM",
  "field_mapping": {
    "account_number": "your_acct_field",
    "current_balance": "your_balance_field",
    ...
  }
}
```

#### Step 3: Configure SFTP Credentials

Store credentials securely:

```bash
# Set via environment variable
SFTP_CONTEXT_KEY=/secrets/context_sftp_key

# Or configure in admin interface
# Admin → Item Context Connectors → Edit → SFTP Settings
```

#### Step 4: Set Import Schedule

Cron expression format for scheduled imports:

```
"import_schedule": "0 6 * * *"   # Daily at 6 AM
"import_schedule": "0 */4 * * *" # Every 4 hours
"import_schedule": "30 5 * * 1-5" # Weekdays at 5:30 AM
```

### Import Workflow

1. **Poll**: System connects to SFTP and checks for new files
2. **Download**: New files downloaded to secure staging
3. **Parse**: File parsed according to field mapping
4. **Validate**: Each record validated for required fields
5. **Match**: Records matched to existing check items by account
6. **Enrich**: Context data applied to matching items
7. **Report**: Import summary with success/failure counts

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `GET /v1/item-context-connectors` | GET | List connectors |
| `POST /v1/item-context-connectors` | POST | Create connector |
| `PUT /v1/item-context-connectors/{id}` | PUT | Update connector |
| `POST /v1/item-context-connectors/{id}/import` | POST | Trigger manual import |
| `GET /v1/item-context-connectors/{id}/imports` | GET | List import history |
| `GET /v1/item-context-connectors/{id}/imports/{import_id}` | GET | Get import details |

### Context Data Fields

| Field | Description | Source |
|-------|-------------|--------|
| `current_balance` | Current account balance | Core system |
| `average_balance` | 30-day average balance | Core system |
| `account_tenure_days` | Days since account opened | Calculated |
| `check_count_30d` | Checks written in last 30 days | Core system |
| `check_amount_avg` | Average check amount | Core system |
| `returned_item_count` | Returns in last 12 months | Core system |
| `exception_count` | Exceptions in last 12 months | Core system |
| `account_type` | Account type code | Core system |
| `relationship_id` | Customer relationship ID | Core system |

### Import Status Codes

| Status | Description |
|--------|-------------|
| `PENDING` | Import queued |
| `DOWNLOADING` | Downloading file from SFTP |
| `PROCESSING` | Parsing and matching records |
| `COMPLETED` | Import successful |
| `PARTIAL` | Some records failed |
| `FAILED` | Import failed |

---

## Environment Variables Reference

### Backend Server (.env)

```env
# Database
DATABASE_URL=postgresql+asyncpg://user:pass@db:5432/check_review

# Redis (for caching)
REDIS_URL=redis://redis:6379/0

# Connector B Settings
DUAL_CONTROL_THRESHOLD=5000.0
HIGH_PRIORITY_THRESHOLD=10000.0
BATCH_AUTO_GENERATE_ENABLED=false

# Connector C Settings
SFTP_CONTEXT_ENABLED=true
SFTP_CONTEXT_POLL_INTERVAL=3600

# Security
JWT_SECRET_KEY=your-secret-key
JWT_ALGORITHM=RS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
```

### Bank-Side Connector A (.env)

```env
# Mode
CONNECTOR_MODE=DEMO

# Identity
CONNECTOR_ID=connector-prod-001

# Network
CONNECTOR_HOST=0.0.0.0
CONNECTOR_PORT=8443

# TLS
CONNECTOR_TLS_CERT_PATH=/path/to/cert.pem
CONNECTOR_TLS_KEY_PATH=/path/to/key.pem

# Authentication
CONNECTOR_JWT_PUBLIC_KEY_PATH=./keys/connector_public.pem

# Security
CONNECTOR_ALLOWED_SHARE_ROOTS=\\\\server\\share1\\,\\\\server\\share2\\
CONNECTOR_MAX_IMAGE_MB=50

# Performance
CONNECTOR_CACHE_TTL_SECONDS=60
CONNECTOR_CACHE_MAX_ITEMS=100
CONNECTOR_RATE_LIMIT_REQUESTS_PER_MINUTE=100

# Logging
CONNECTOR_LOG_LEVEL=INFO
```

---

## Security Considerations

### Authentication

| Connector | Method | Details |
|-----------|--------|---------|
| **A** | RS256 JWT | Short-lived tokens (60-120s), public key pinned |
| **B** | SFTP Key/Password | Credentials encrypted at rest |
| **C** | SFTP Key/Password | Credentials encrypted at rest |

### Encryption

- **In Transit**: TLS 1.2+ for all connections
- **At Rest**: Database encryption, credential vault

### Access Control

- Connector A: Path allowlisting prevents unauthorized file access
- Connector B: Dual control for high-value batches
- Connector C: Read-only SFTP access

### Audit Logging

All connectors log:
- Configuration changes
- Connection attempts
- Data transfers
- Errors and exceptions

---

## Monitoring and Alerting

### Health Checks

**Connector A (Bank-side):**
```bash
curl https://connector.bank.local:8443/healthz
```

**Connector B & C (SaaS):**
```bash
curl https://api.checkreview.com/v1/health/connectors
```

### Key Metrics

| Metric | Target | Alert Threshold |
|--------|--------|-----------------|
| Connector A latency | <200ms | >500ms |
| Connector A cache hit rate | >50% | <30% |
| Connector B batch success rate | >99% | <95% |
| Connector C import success rate | >99% | <95% |
| SFTP connection failures | 0 | >3/hour |

### Recommended Alerts

1. Connector A health check failures
2. Batch file delivery failures
3. Context import failures
4. SFTP connection timeouts
5. JWT authentication failures
6. Rate limit exceeded

---

## Production Checklist

### Connector A (Image Connector)

- [ ] TLS certificate from trusted CA installed
- [ ] RSA key pair generated and registered with SaaS
- [ ] Service account created with minimal read-only access
- [ ] Firewall rules configured (inbound 8443, outbound 445)
- [ ] Path allowlist configured correctly
- [ ] Audit logging enabled and shipping to SIEM
- [ ] Health monitoring configured
- [ ] Load testing completed
- [ ] Security review completed

### Connector B (Batch Commit)

- [ ] Bank configuration created and validated
- [ ] File format matches bank requirements
- [ ] Delivery method configured and tested
- [ ] SFTP credentials stored securely
- [ ] Acknowledgement processing configured
- [ ] Dual control thresholds set appropriately
- [ ] Reconciliation reports enabled
- [ ] End-to-end test with bank completed

### Connector C (Item Context)

- [ ] SFTP connection configured and tested
- [ ] Field mapping matches bank export format
- [ ] Import schedule configured
- [ ] Error handling and retry logic verified
- [ ] Context enrichment validated
- [ ] Import monitoring enabled
- [ ] Initial full import completed successfully

---

## Troubleshooting Guide

### Connector A Issues

| Symptom | Possible Cause | Resolution |
|---------|----------------|------------|
| Connection timeout | Firewall blocking | Check firewall rules |
| 401 Unauthorized | JWT invalid/expired | Verify key pair, check clock sync |
| 404 Not Found | Path not in allowlist | Update CONNECTOR_ALLOWED_SHARE_ROOTS |
| 500 Server Error | Storage unavailable | Check SMB connectivity |

### Connector B Issues

| Symptom | Possible Cause | Resolution |
|---------|----------------|------------|
| SFTP connection failed | Credentials incorrect | Verify credentials |
| File format rejected | Mapping mismatch | Review bank specifications |
| Duplicate batch | Idempotency triggered | Check batch_id uniqueness |
| Acknowledgement missing | Polling disabled | Enable ack_polling |

### Connector C Issues

| Symptom | Possible Cause | Resolution |
|---------|----------------|------------|
| No files found | Wrong path/pattern | Check sftp_remote_path and file_pattern |
| Parse errors | Field mapping wrong | Update field_mapping configuration |
| Low match rate | Account number format | Verify account number formatting |
| Import timeout | Large file | Increase timeout, consider chunking |

---

## Additional Resources

- [Bank-Side Connector Deployment Guide](../connector/DEPLOYMENT.md) - Detailed Connector A setup
- [API Documentation](./API.md) - Full API reference
- [RBAC Guide](./RBAC.md) - Role-based access control
- [Incident Response](./INCIDENT_RESPONSE.md) - Handling connector failures
