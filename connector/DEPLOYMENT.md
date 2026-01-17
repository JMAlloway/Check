# Bank-Side Connector Deployment Guide

## Overview

The Bank-Side Connector is a secure service that runs inside the bank's network to serve check images to the cloud-based Check Review Console SaaS. It acts as a bridge between the SaaS application and the bank's on-premise image storage.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        CLOUD (SaaS)                             │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │           Check Review Console                           │   │
│  │  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐  │   │
│  │  │ Browser UI  │───▶│ API Server  │───▶│ Connector   │  │   │
│  │  │             │◀───│             │◀───│ Manager     │  │   │
│  │  └─────────────┘    └─────────────┘    └─────────────┘  │   │
│  └──────────────────────────┬──────────────────────────────┘   │
└─────────────────────────────┼───────────────────────────────────┘
                              │ HTTPS + JWT (RS256)
┌─────────────────────────────┼───────────────────────────────────┐
│                        BANK NETWORK                              │
│  ┌──────────────────────────▼──────────────────────────────┐   │
│  │              Bank-Side Connector                         │   │
│  │  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐  │   │
│  │  │ JWT Auth    │───▶│ Image       │───▶│ Storage     │  │   │
│  │  │ (RS256)     │    │ Service     │    │ Provider    │  │   │
│  │  └─────────────┘    └─────────────┘    └─────────────┘  │   │
│  └──────────────────────────┬──────────────────────────────┘   │
│                              │ SMB/CIFS (Service Account)        │
│  ┌──────────────────────────▼──────────────────────────────┐   │
│  │              Fiserv Director Image Storage               │   │
│  │  \\tn-director-pro\Checks\Transit\V406\580\*.IMG        │   │
│  │  \\tn-director-pro\Checks\OnUs\V406\123\*.IMG           │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

## Modes

### DEMO Mode

Demo mode uses the local filesystem to simulate UNC shares. Use this for:
- Development and testing
- Demonstrations without bank connectivity
- Integration testing

### BANK Mode (Production)

Bank mode connects to real UNC paths using SMB. Requires:
- Service account with read-only access to image shares
- Network connectivity to file servers
- Production implementation of `BankStorageProvider`

## Prerequisites

- Python 3.11+
- TLS certificate for HTTPS
- RSA key pair for JWT authentication
- Network access to image storage (BANK mode only)

## Installation

### 1. Clone and Install Dependencies

```bash
cd connector
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Generate RSA Key Pair

```bash
python scripts/mint_token.py --generate-keys
```

This creates:
- `keys/connector_private.pem` - Store securely, configure on connector
- `keys/connector_public.pem` - Register with SaaS

### 3. Configure Environment

Copy `.env.example` to `.env` and configure:

```bash
cp .env.example .env
```

Key settings:

```env
# Mode: DEMO or BANK
CONNECTOR_MODE=DEMO

# Unique connector ID
CONNECTOR_ID=connector-prod-001

# Network
CONNECTOR_HOST=0.0.0.0
CONNECTOR_PORT=8443

# TLS (required for production)
CONNECTOR_TLS_CERT_PATH=/path/to/cert.pem
CONNECTOR_TLS_KEY_PATH=/path/to/key.pem

# Demo mode paths
CONNECTOR_DEMO_REPO_ROOT=./demo_repo
CONNECTOR_ITEM_INDEX_PATH=./demo_repo/item_index.json

# Allowed UNC share roots (comma-separated)
CONNECTOR_ALLOWED_SHARE_ROOTS=\\\\tn-director-pro\\Checks\\Transit\\,\\\\tn-director-pro\\Checks\\OnUs\\

# JWT public key (from SaaS)
CONNECTOR_JWT_PUBLIC_KEY_PATH=./keys/connector_public.pem

# Image handling
CONNECTOR_MAX_IMAGE_MB=50
CONNECTOR_CACHE_TTL_SECONDS=60
```

### 4. Generate Demo Fixtures (Demo Mode Only)

```bash
python scripts/generate_demo_fixtures.py
```

This creates sample TIFF images and item index.

### 5. Start the Connector

```bash
# Development
uvicorn app.main:app --host 0.0.0.0 --port 8443 --reload

# Production (with TLS)
uvicorn app.main:app \
  --host 0.0.0.0 \
  --port 8443 \
  --ssl-keyfile /path/to/key.pem \
  --ssl-certfile /path/to/cert.pem \
  --workers 4
```

### 6. Verify Installation

```bash
# Health check
curl -k https://localhost:8443/healthz

# With token (get from SaaS or mint_token.py)
TOKEN=$(python scripts/mint_token.py --curl)
curl -k -H "Authorization: Bearer $TOKEN" \
  "https://localhost:8443/v1/images/by-item?trace=12374628&date=2024-01-15&side=front" \
  -o front.png
```

## SaaS Integration

### Register Connector in SaaS

1. Log in to Check Review Console as admin
2. Navigate to Admin → Image Connectors
3. Click "Add Connector"
4. Enter:
   - Connector ID: `connector-prod-001` (must match connector config)
   - Name: Human-friendly name
   - Base URL: `https://connector.bank.local:8443`
   - Public Key: Contents of `connector_public.pem`
5. Test connection
6. Enable connector

### JWT Token Flow

1. User requests check image in SaaS
2. SaaS generates short-lived JWT (60-120s) signed with private key
3. Browser calls connector directly with JWT
4. Connector validates JWT using pinned public key
5. Connector returns PNG image

## Security Configuration

### TLS Requirements

Production requires TLS 1.2+. Generate or obtain certificates:

```bash
# Self-signed for testing (NOT for production)
openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes
```

### Service Account

Create a read-only service account for accessing image shares:

```powershell
# Windows example
New-LocalUser -Name "svc_connector" -Description "Connector Service Account"
# Grant read-only access to share
icacls "\\tn-director-pro\Checks" /grant "svc_connector:(OI)(CI)R"
```

### Firewall Rules

```
# Inbound (to connector)
- Port 8443 TCP from SaaS IP ranges

# Outbound (from connector)
- Port 445 TCP to file servers (SMB)
```

### Path Allowlisting

Configure `CONNECTOR_ALLOWED_SHARE_ROOTS` to restrict which paths can be accessed:

```env
CONNECTOR_ALLOWED_SHARE_ROOTS=\\\\tn-director-pro\\Checks\\Transit\\,\\\\tn-director-pro\\Checks\\OnUs\\
```

## Monitoring

### Health Endpoint

```bash
curl https://localhost:8443/healthz
```

Returns:
```json
{
  "status": "healthy",
  "mode": "DEMO",
  "version": "1.0.0",
  "connector_id": "connector-prod-001",
  "components": {
    "resolver": {"healthy": true, "message": "Demo resolver ready with 5 items"},
    "storage": {"healthy": true, "message": "Demo storage accessible"},
    "decoder": {"healthy": true, "message": "Image decoder operational"}
  },
  "cache": {
    "items": 0,
    "hit_rate": 0.0
  }
}
```

### Audit Logs

Structured JSON logs are written to `logs/connector_audit.jsonl`:

```json
{"timestamp":"2024-01-15T10:30:00Z","connector_id":"connector-prod-001","mode":"DEMO","action":"IMAGE_SERVED","endpoint":"/v1/images/by-handle","allow":true,"org_id":"demo-org","user_id":"demo-user","path_hash":"sha256:...","bytes_sent":45678,"latency_ms":125}
```

### Metrics to Monitor

- Request latency (target: <200ms)
- Cache hit rate (target: >50%)
- Error rate (target: <1%)
- Health check status
- Storage accessibility

## Troubleshooting

### Common Issues

**Connection refused from SaaS**
- Check firewall allows inbound on port 8443
- Verify TLS certificate is valid
- Check connector is running

**JWT validation failed**
- Verify public key matches SaaS private key
- Check token hasn't expired
- Verify issuer matches configuration

**Image not found**
- Check path is in allowed roots
- Verify file exists on storage
- Check service account has read access

**Decode failed**
- Verify file is valid TIFF format
- Check file isn't corrupted
- Review max image size settings

### Debug Mode

Enable debug logging:

```env
CONNECTOR_LOG_LEVEL=DEBUG
```

## Production Checklist

- [ ] TLS certificate from trusted CA installed
- [ ] RSA key pair generated and registered with SaaS
- [ ] Service account created with minimal read-only access
- [ ] Firewall rules configured
- [ ] Path allowlist configured correctly
- [ ] Audit logging enabled and shipping to SIEM
- [ ] Health monitoring configured
- [ ] Backup connector configured (optional)
- [ ] BANK mode implementation completed (if needed)
- [ ] Load testing completed
- [ ] Security review completed

## API Reference

See `/docs` endpoint when running in DEMO mode for OpenAPI documentation.

### Endpoints

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/healthz` | GET | No | Health check |
| `/v1/images/by-handle` | GET | JWT | Get image by UNC path |
| `/v1/images/by-item` | GET | JWT | Get image by trace/date |
| `/v1/items/lookup` | GET | JWT | Look up item metadata |

### Query Parameters

**by-handle**
- `path` (required): UNC path to image
- `side`: `front` or `back` (default: front)

**by-item**
- `trace` (required): Trace number
- `date` (required): Check date (YYYY-MM-DD)
- `side`: `front` or `back` (default: front)

### Response Headers

- `X-Correlation-ID`: Request tracking ID
- `X-From-Cache`: Whether response was cached
- `X-Image-Width`: Image width in pixels
- `X-Image-Height`: Image height in pixels
