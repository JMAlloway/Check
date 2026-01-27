# Check Review Console - Architecture Documentation

## Overview

The Check Review Console is a bank-grade web application designed for community bank operations teams to review presented checks. This document describes the system architecture, component interactions, and design decisions.

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              PRESENTATION LAYER                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                     React Frontend (Vite + TypeScript)               │   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐  │   │
│  │  │Dashboard │ │ Check    │ │ Decision │ │  Queue   │ │  Admin   │  │   │
│  │  │  Page    │ │ Review   │ │  Panel   │ │  View    │ │  Panel   │  │   │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘  │   │
│  │                                                                     │   │
│  │  ┌─────────────────────┐  ┌─────────────────────┐                  │   │
│  │  │   Zustand Stores    │  │   API Service       │                  │   │
│  │  │ (auth, review, etc) │  │   (Axios + React    │                  │   │
│  │  │                     │  │    Query)           │                  │   │
│  │  └─────────────────────┘  └─────────────────────┘                  │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└───────────────────────────────────┬─────────────────────────────────────────┘
                                    │ HTTPS (TLS 1.2+)
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              GATEWAY LAYER                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                           Nginx Reverse Proxy                        │   │
│  │                                                                       │   │
│  │  • TLS Termination          • Security Headers (CSP, HSTS)           │   │
│  │  • Static File Serving      • Rate Limiting                          │   │
│  │  • Request Routing          • Request Logging                        │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└───────────────────────────────────┬─────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              API LAYER                                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    FastAPI Application (Python 3.11+)                │   │
│  │                                                                       │   │
│  │  ┌───────────────────────────────────────────────────────────────┐   │   │
│  │  │                        Middleware Stack                        │   │   │
│  │  │  Token Redaction → CORS → Metrics → Security Headers          │   │   │
│  │  └───────────────────────────────────────────────────────────────┘   │   │
│  │                                                                       │   │
│  │  ┌─────────────────────────────────────────────────────────────────┐ │   │
│  │  │                     API Endpoints (/api/v1)                     │ │   │
│  │  │                                                                 │ │   │
│  │  │  /auth     /checks    /decisions   /policies   /queues         │ │   │
│  │  │  /users    /audit     /fraud       /images     /reports        │ │   │
│  │  │  /connectors         /operations   /monitoring                 │ │   │
│  │  └─────────────────────────────────────────────────────────────────┘ │   │
│  │                                                                       │   │
│  │  ┌──────────────────────┐  ┌──────────────────────┐                 │   │
│  │  │   Dependency         │  │   Authentication     │                 │   │
│  │  │   Injection          │  │   (JWT + RBAC)       │                 │   │
│  │  │   (FastAPI Depends)  │  │                      │                 │   │
│  │  └──────────────────────┘  └──────────────────────┘                 │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────┬───────────────────────────────────────┬───────────────────┘
                  │                                       │
                  ▼                                       ▼
┌─────────────────────────────────────┐   ┌─────────────────────────────────────┐
│          SERVICE LAYER               │   │          INTEGRATION LAYER          │
├─────────────────────────────────────┤   ├─────────────────────────────────────┤
│                                     │   │                                     │
│  ┌─────────────────────────────┐   │   │  ┌─────────────────────────────┐   │
│  │       Business Services      │   │   │  │    Connector Adapters       │   │
│  │                             │   │   │  │                             │   │
│  │  • CheckService             │   │   │  │  • Connector A (Images)     │   │
│  │  • DecisionService          │   │   │  │  • Connector B (Real-time)  │   │
│  │  • PolicyEngine             │   │   │  │  • Connector C (Batch)      │   │
│  │  • EntitlementService       │   │   │  │  • Mock Adapter (Testing)   │   │
│  │  • AuditService             │   │   │  └─────────────────────────────┘   │
│  │  • FraudService             │   │   │                                     │
│  │  • AuthService              │   │   │  ┌─────────────────────────────┐   │
│  └─────────────────────────────┘   │   │  │    External Services        │   │
│                                     │   │  │                             │   │
│  ┌─────────────────────────────┐   │   │  │  • Core Banking System      │   │
│  │       Shared Services        │   │   │  │  • Image Archive           │   │
│  │                             │   │   │  │  • Fraud Network            │   │
│  │  • PDFGenerator             │   │   │  └─────────────────────────────┘   │
│  │  • ImageTokenService        │   │   │                                     │
│  │  • EvidenceSealService      │   │   │                                     │
│  │  • PIIDetectionService      │   │   │                                     │
│  └─────────────────────────────┘   │   │                                     │
│                                     │   │                                     │
└─────────────────┬───────────────────┘   └─────────────────┬───────────────────┘
                  │                                         │
                  ▼                                         ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              DATA LAYER                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────┐  ┌─────────────────────────────┐          │
│  │        PostgreSQL           │  │           Redis              │          │
│  │                             │  │                             │          │
│  │  • User & Auth Data         │  │  • Session Cache            │          │
│  │  • Check Items              │  │  • Rate Limiting            │          │
│  │  • Decisions                │  │  • Policy Cache             │          │
│  │  • Audit Logs               │  │  • Permission Cache         │          │
│  │  • Policies & Rules         │  │                             │          │
│  │  • Fraud Events             │  │                             │          │
│  │  • Queues                   │  │                             │          │
│  └─────────────────────────────┘  └─────────────────────────────┘          │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Entity Relationship Diagram (ERD)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           CORE ENTITIES                                      │
└─────────────────────────────────────────────────────────────────────────────┘

┌──────────────────┐       ┌──────────────────┐       ┌──────────────────┐
│     TENANT       │       │      USER        │       │      ROLE        │
├──────────────────┤       ├──────────────────┤       ├──────────────────┤
│ id (PK)          │       │ id (PK)          │       │ id (PK)          │
│ name             │◄──────│ tenant_id (FK)   │       │ tenant_id (FK)   │
│ settings (JSON)  │   1:N │ email            │  N:M  │ name             │
│ created_at       │       │ username         │◄─────►│ description      │
│ updated_at       │       │ hashed_password  │       │ is_system        │
└──────────────────┘       │ full_name        │       │ created_at       │
                           │ is_active        │       └────────┬─────────┘
                           │ is_superuser     │                │
                           │ mfa_enabled      │                │ N:M
                           │ department       │                ▼
                           │ last_login       │       ┌──────────────────┐
                           │ failed_attempts  │       │   PERMISSION     │
                           │ locked_until     │       ├──────────────────┤
                           │ created_at       │       │ id (PK)          │
                           └────────┬─────────┘       │ tenant_id (FK)   │
                                    │                 │ name             │
                                    │ 1:N             │ resource         │
                                    ▼                 │ action           │
                           ┌──────────────────┐       │ conditions       │
                           │  USER_SESSION    │       │ is_system        │
                           ├──────────────────┤       └──────────────────┘
                           │ id (PK)          │
                           │ user_id (FK)     │
                           │ token_hash       │
                           │ ip_address       │
                           │ user_agent       │
                           │ expires_at       │
                           │ is_active        │
                           └──────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                         CHECK PROCESSING                                     │
└─────────────────────────────────────────────────────────────────────────────┘

┌──────────────────┐       ┌──────────────────┐       ┌──────────────────┐
│     QUEUE        │       │   CHECK_ITEM     │       │   CHECK_IMAGE    │
├──────────────────┤       ├──────────────────┤       ├──────────────────┤
│ id (PK)          │       │ id (PK)          │       │ id (PK)          │
│ tenant_id (FK)   │  1:N  │ tenant_id (FK)   │  1:N  │ check_item_id(FK)│
│ name             │◄──────│ queue_id (FK)    │──────►│ image_type       │
│ description      │       │ external_item_id │       │ external_id      │
│ queue_type       │       │ account_id       │       │ content_type     │
│ sla_hours        │       │ amount           │       │ file_size        │
│ warning_threshold│       │ status           │       │ storage_path     │
│ is_active        │       │ risk_level       │       │ captured_at      │
│ display_order    │       │ item_type        │       │ created_at       │
│ created_at       │       │ presented_date   │       └──────────────────┘
└──────────────────┘       │ payee_name       │
                           │ payer_name       │       ┌──────────────────┐
                           │ check_number     │       │    DECISION      │
                           │ has_ai_flags     │       ├──────────────────┤
                           │ ai_risk_score    │       │ id (PK)          │
                           │ policy_version_id│  1:N  │ tenant_id (FK)   │
                           │ assigned_reviewer│◄──────│ check_item_id(FK)│
                           │ created_at       │       │ user_id (FK)     │
                           └────────┬─────────┘       │ decision_type    │
                                    │                 │ action           │
                                    │ 1:N             │ reason_codes     │
                                    ▼                 │ notes            │
                           ┌──────────────────┐       │ ai_assisted      │
                           │  CHECK_HISTORY   │       │ evidence_snapshot│
                           ├──────────────────┤       │ is_dual_control  │
                           │ id (PK)          │       │ dc_approver_id   │
                           │ tenant_id (FK)   │       │ created_at       │
                           │ account_id       │       └──────────────────┘
                           │ check_date       │
                           │ amount           │
                           │ status           │
                           │ created_at       │
                           └──────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                           POLICY ENGINE                                      │
└─────────────────────────────────────────────────────────────────────────────┘

┌──────────────────┐       ┌──────────────────┐       ┌──────────────────┐
│     POLICY       │       │  POLICY_VERSION  │       │   POLICY_RULE    │
├──────────────────┤       ├──────────────────┤       ├──────────────────┤
│ id (PK)          │       │ id (PK)          │       │ id (PK)          │
│ tenant_id (FK)   │  1:N  │ policy_id (FK)   │  1:N  │ version_id (FK)  │
│ name             │──────►│ version_number   │──────►│ name             │
│ description      │       │ effective_date   │       │ description      │
│ status           │       │ expiry_date      │       │ rule_type        │
│ is_default       │       │ is_current       │       │ priority         │
│ applies_to_types │       │ approved_by_id   │       │ is_enabled       │
│ applies_to_branch│       │ approved_at      │       │ conditions (JSON)│
│ created_at       │       │ change_notes     │       │ actions (JSON)   │
└──────────────────┘       │ created_at       │       │ amount_threshold │
                           └──────────────────┘       │ created_at       │
                                                       └──────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                         FRAUD INTELLIGENCE                                   │
└─────────────────────────────────────────────────────────────────────────────┘

┌──────────────────┐       ┌──────────────────┐       ┌──────────────────┐
│   FRAUD_EVENT    │       │ SHARED_ARTIFACT  │       │  NETWORK_MATCH   │
├──────────────────┤       ├──────────────────┤       ├──────────────────┤
│ id (PK)          │       │ id (PK)          │       │ id (PK)          │
│ tenant_id (FK)   │  1:N  │ fraud_event_id   │       │ tenant_id (FK)   │
│ check_item_id(FK)│──────►│ indicator_type   │       │ artifact_id (FK) │
│ fraud_type       │       │ hashed_value     │       │ match_score      │
│ channel          │       │ pepper_version   │       │ matched_at       │
│ description      │       │ created_at       │       │ acknowledged     │
│ amount_bucket    │       │ expires_at       │       │ acknowledged_by  │
│ status           │       └──────────────────┘       │ created_at       │
│ submitted_at     │                                   └──────────────────┘
│ withdrawn_at     │
│ created_at       │
└──────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                            AUDIT TRAIL                                       │
└─────────────────────────────────────────────────────────────────────────────┘

┌──────────────────┐       ┌──────────────────┐
│    AUDIT_LOG     │       │    ITEM_VIEW     │
├──────────────────┤       ├──────────────────┤
│ id (PK)          │       │ id (PK)          │
│ tenant_id (FK)   │       │ tenant_id (FK)   │
│ timestamp        │       │ check_item_id(FK)│
│ action           │       │ user_id (FK)     │
│ resource_type    │       │ view_started_at  │
│ resource_id      │       │ view_ended_at    │
│ user_id          │       │ duration_seconds │
│ username         │       │ front_viewed     │
│ ip_address       │       │ back_viewed      │
│ user_agent       │       │ zoom_used        │
│ description      │       │ magnifier_used   │
│ before_value     │       │ history_compared │
│ after_value      │       │ created_at       │
│ chain_hash       │       └──────────────────┘
│ created_at       │
└──────────────────┘
```

## Key Design Patterns

### 1. Multi-Tenant Architecture

All data-bearing tables include a `tenant_id` column that:
- Is indexed for query performance
- Is enforced at the service layer (never trusted from client)
- Enables complete data isolation between banks
- Supports composite unique constraints (e.g., email unique per tenant)

### 2. RBAC (Role-Based Access Control)

```
Permission Model: resource:action
Examples:
  - check_item:view
  - check_item:review
  - check_item:approve
  - policy:create
  - audit:export

Role Hierarchy:
  System Admin > Tenant Admin > Supervisor > Reviewer > Auditor > Read Only
```

### 3. Dual Control Workflow

For high-value or policy-flagged items:

```
┌─────────┐    ┌──────────────┐    ┌───────────────────┐    ┌──────────┐
│   NEW   │───►│  IN_REVIEW   │───►│ PENDING_DUAL_CTRL │───►│ APPROVED │
└─────────┘    └──────────────┘    └───────────────────┘    └──────────┘
                     │                      │
                     │                      │ (Rejected by approver)
                     │                      ▼
                     │              ┌──────────────┐
                     └─────────────►│  IN_REVIEW   │
                                    └──────────────┘
```

### 4. Evidence Chain Integrity

Each decision creates a sealed evidence snapshot with:
- SHA-256 hash of the evidence data
- Reference to previous decision's hash (chain)
- Allows tamper-evident audit replay

### 5. Image Token Security

```
┌─────────────┐    ┌──────────────────┐    ┌─────────────┐
│  Frontend   │───►│ Request Image    │───►│   Backend   │
│             │    │ Token            │    │             │
└─────────────┘    └──────────────────┘    └──────┬──────┘
                                                   │
                           ┌───────────────────────┘
                           ▼
                   ┌──────────────────┐
                   │ Generate Signed  │
                   │ URL (90s TTL)    │
                   └────────┬─────────┘
                            │
                            ▼
                   ┌──────────────────┐
                   │ One-time token   │
                   │ stored in DB     │
                   └────────┬─────────┘
                            │
                            ▼
              ┌────────────────────────────┐
              │ Signed URL returned to     │
              │ frontend for direct access │
              └────────────────────────────┘
```

## Data Flow: Check Review Process

```
1. Check Presented
   └─► Core Banking System sends check data via Connector B/C

2. Item Created
   └─► Check item created with status=NEW
   └─► Policy engine evaluates, sets risk_level
   └─► Routed to appropriate queue

3. Review Assignment
   └─► Item assigned to reviewer (manual or auto)
   └─► Status changes to IN_REVIEW

4. Reviewer Action
   └─► Reviewer views images (logged)
   └─► Reviews AI flags if present
   └─► Makes decision (approve/reject/escalate)

5. Dual Control (if required)
   └─► Status changes to PENDING_DUAL_CONTROL
   └─► Second reviewer must approve/reject

6. Final Status
   └─► APPROVED: Processed for payment
   └─► REJECTED: Returned to depositor
   └─► RETURNED: Sent back with reason

7. Audit Trail
   └─► All actions logged with timestamps, IPs, evidence
```

## Security Architecture

See [SECURITY_ARCHITECTURE.md](./SECURITY_ARCHITECTURE.md) for detailed security documentation.

Key security features:
- JWT-based authentication with short-lived access tokens
- Refresh tokens in httpOnly cookies (XSS-safe)
- CSRF protection for state-changing operations
- Rate limiting (5/min login, 100/min API)
- Account lockout after 5 failed attempts
- MFA support (TOTP)
- Comprehensive audit logging

## Deployment Architecture

See [PILOT_RUNBOOK.md](./PILOT_RUNBOOK.md) for deployment procedures.

```
Production Environment:
┌─────────────────────────────────────────────────────────────┐
│                     Load Balancer                           │
└─────────────────────────┬───────────────────────────────────┘
                          │
         ┌────────────────┼────────────────┐
         │                │                │
         ▼                ▼                ▼
┌─────────────┐   ┌─────────────┐   ┌─────────────┐
│   Nginx     │   │   Nginx     │   │   Nginx     │
│  + Backend  │   │  + Backend  │   │  + Backend  │
└──────┬──────┘   └──────┬──────┘   └──────┬──────┘
       │                 │                 │
       └─────────────────┼─────────────────┘
                         │
         ┌───────────────┼───────────────┐
         │               │               │
         ▼               ▼               ▼
┌─────────────┐   ┌─────────────┐   ┌─────────────┐
│ PostgreSQL  │   │   Redis     │   │    S3       │
│  (Primary)  │   │  Cluster    │   │  (Images)   │
└─────────────┘   └─────────────┘   └─────────────┘
         │
         ▼
┌─────────────┐
│ PostgreSQL  │
│  (Replica)  │
└─────────────┘
```

## Performance Considerations

1. **Database Indexes**: Composite indexes on (tenant_id, status), (tenant_id, queue_id)
2. **Redis Caching**: Policy rules, user permissions, rate limiting
3. **Connection Pooling**: SQLAlchemy async with configured pool size
4. **Image Loading**: Signed URLs with CDN caching where applicable
5. **Pagination**: All list endpoints support cursor-based pagination

## Monitoring & Observability

- **Metrics**: Prometheus endpoint at `/metrics`
- **Logging**: Structured JSON logging via structlog
- **Health Checks**: `/health` and `/ready` endpoints
- **Tracing**: OpenTelemetry integration (optional)
