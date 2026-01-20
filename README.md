# Check Review Console

A bank-grade web application for community bank operations teams to review presented checks in a faster, more consistent, and audit-defensible way. The system is human-in-the-loop: reviewers and approvers make final decisions while the system provides workflow, context, and assistive analytics.

## Features

### Core Functionality
- **Check Image Viewer**: Bank-grade UX with zoom, pan, magnifier, brightness/contrast controls
- **ROI Overlays**: User-defined regions of interest for amount box, signature, MICR line, etc.
- **Side-by-Side Comparison**: Compare current check with historical checks from the same account
- **Context Panel**: Account tenure, balance, check behavior stats, returned item history
- **Detection Rules**: Explainable rule-based flags with confidence levels and explanations
- **On Us vs Transit**: Check type classification for routing optimization

### Workflow
- **Dual Control**: Configurable thresholds for two-person approval
- **Queue Management**: Priority-based queues with SLA tracking
- **Policy Engine**: Versioned, configurable business rules with tenant isolation
- **Full Audit Trail**: Every action logged with immutable chain integrity

### Connectors
- **Connector A (Image)**: Real-time check image retrieval via secure signed URLs
- **Connector B (Real-Time)**: Account context and history from core banking (planned)
- **Connector C (Item Context)**: Daily flat file imports via SFTP for batch data

### Security
- **6-Role RBAC System**: Granular permissions per Technical Guide Section 2.2
- **Multi-Tenant Isolation**: Complete data separation between bank tenants
- **Session Management**: Secure JWT-based authentication with CSRF protection
- **Evidence Sealing**: Cryptographic validation of connector keys and snapshots
- **One-Time Image Tokens**: Secure, single-use tokens for image access

## Tech Stack

- **Backend**: Python 3.11, FastAPI, SQLAlchemy 2.0, PostgreSQL 15, Redis
- **Frontend**: React 18, TypeScript, TailwindCSS, React Query, Zustand
- **Infrastructure**: Docker, Nginx, Alembic migrations
- **CI/CD**: GitHub Actions (linting, testing, security scans, container builds)

## Quick Start

### Prerequisites
- Docker and Docker Compose v2
- Node.js 20+ (for local frontend development)
- Python 3.11+ (for local backend development)

### Running with Docker (Recommended)

```bash
# Clone the repository
git clone https://github.com/JMAlloway/Check.git
cd Check

# Start all services in demo mode
cd docker
DEMO_MODE=true docker compose up --build

# The application will be available at:
# - Frontend: http://localhost:3000
# - Backend API: http://localhost:8000
# - API Docs: http://localhost:8000/api/v1/docs
```

### Demo Credentials

When `DEMO_MODE=true`, the following users are auto-seeded:

| Username | Password | Role |
|----------|----------|------|
| `system_admin_demo` | `DemoSysAdmin123!` | System Admin |
| `tenant_admin_demo` | `DemoTenantAdmin123!` | Tenant Admin |
| `supervisor_demo` | `DemoSupervisor123!` | Supervisor |
| `reviewer_demo` | `DemoReviewer123!` | Reviewer |
| `auditor_demo` | `DemoAuditor123!` | Auditor |
| `readonly_demo` | `DemoReadonly123!` | Read Only |

### Local Development

#### Backend

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set environment variables
export DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/check_review"
export SECRET_KEY="your-secret-key"
export DEMO_MODE=true

# Run migrations
alembic upgrade head

# Start development server
uvicorn app.main:app --reload --port 8000
```

#### Frontend

```bash
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

## Project Structure

```
Check/
├── backend/
│   ├── app/
│   │   ├── api/           # API endpoints (v1)
│   │   ├── core/          # Configuration, security, middleware
│   │   ├── db/            # Database session management
│   │   ├── models/        # SQLAlchemy models
│   │   ├── schemas/       # Pydantic request/response schemas
│   │   ├── services/      # Business logic services
│   │   ├── integrations/  # External system adapters
│   │   ├── policy/        # Policy engine
│   │   ├── audit/         # Audit logging and retention
│   │   ├── security/      # Breach detection, security models
│   │   ├── scheduler/     # Background task scheduling
│   │   └── demo/          # Demo mode (synthetic data, mock providers)
│   ├── alembic/           # Database migrations (15 versions)
│   ├── scripts/           # Utility scripts (seeding, DR drills)
│   └── tests/             # Unit and integration tests
├── connector/             # Standalone connector service
│   ├── app/
│   │   ├── adapters/      # Bank-specific and demo adapters
│   │   ├── api/           # Connector API endpoints
│   │   └── services/      # Image and caching services
│   └── demo_repo/         # Demo check images
├── frontend/
│   ├── src/
│   │   ├── components/    # React components (check, decision, fraud, layout)
│   │   ├── pages/         # Page components
│   │   ├── services/      # API client
│   │   ├── stores/        # Zustand state management
│   │   └── types/         # TypeScript type definitions
│   └── public/
├── docker/                # Docker configuration
│   ├── docker-compose.yml       # Development compose
│   ├── docker-compose.pilot.yml # Production-hardened compose
│   ├── Dockerfile.backend       # Backend dev image
│   ├── Dockerfile.backend.prod  # Backend prod image
│   ├── Dockerfile.frontend      # Frontend dev image
│   └── Dockerfile.frontend.prod # Frontend prod image
├── docs/                  # Comprehensive documentation
│   ├── CHECK_REVIEW_CONSOLE_TECHNICAL_GUIDE.md
│   ├── BANK_ONBOARDING_GUIDE.md
│   ├── CONNECTOR_SETUP.md
│   ├── SECURITY_ARCHITECTURE.md
│   └── ... (20+ documentation files)
└── .github/workflows/     # CI/CD pipelines
    ├── ci.yml             # Linting, testing, Docker builds
    ├── deploy.yml         # Container registry deployment
    └── security-scan.yml  # Dependency audits, SAST, secret detection
```

## User Roles (6-Role RBAC)

| Role | Key Permissions |
|------|-----------------|
| **System Admin** | Full system access, user management, all tenants |
| **Tenant Admin** | Manage users/policies within tenant, configure queues |
| **Supervisor** | Override decisions, manage team, view reports |
| **Reviewer** | View items, make recommendations, create decisions |
| **Auditor** | Read-only access to all data, audit logs, reports |
| **Read Only** | View dashboards and reports only |

## API Documentation

Interactive API documentation available at `/api/v1/docs` (Swagger UI) or `/api/v1/redoc` (ReDoc).

### Key Endpoints

| Endpoint | Description |
|----------|-------------|
| `POST /api/v1/auth/login` | User authentication |
| `GET /api/v1/checks` | List check items with filtering |
| `GET /api/v1/checks/{id}` | Get check item with images and history |
| `POST /api/v1/decisions` | Create review decision |
| `GET /api/v1/queues` | List available queues |
| `GET /api/v1/fraud/network/alerts` | Network intelligence alerts |
| `GET /api/v1/reports/dashboard` | Dashboard statistics |
| `POST /api/v1/audit/search` | Search audit logs |

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | Required |
| `SECRET_KEY` | JWT signing key (32+ chars) | Required in production |
| `REDIS_URL` | Redis connection string | `redis://localhost:6379/0` |
| `ENVIRONMENT` | `development` or `production` | `development` |
| `DEMO_MODE` | Enable demo mode with synthetic data | `false` |
| `DEMO_DATA_COUNT` | Number of demo items to seed | `60` |
| `CORS_ORIGINS` | Allowed CORS origins (JSON array) | `["http://localhost:3000"]` |
| `DUAL_CONTROL_THRESHOLD` | Amount requiring dual control | `5000.0` |
| `IMAGE_SIGNED_URL_TTL_SECONDS` | Signed URL expiration | `3600` |

## Testing

### Backend Tests

```bash
cd backend
pip install pytest pytest-asyncio pytest-cov

# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ -v --cov=app --cov-report=html
```

### Frontend Tests

```bash
cd frontend
npm install

# Run tests
npm test

# Run linting
npm run lint
```

## CI/CD Pipeline

The repository includes GitHub Actions workflows:

- **CI (`ci.yml`)**: Runs on push/PR to main
  - Backend: black, isort formatting checks + pytest
  - Frontend: ESLint + vitest
  - Docker: Build validation for both images

- **Security Scan (`security-scan.yml`)**: Daily + on push
  - Python dependency audit (pip-audit)
  - Node.js dependency audit (npm audit)
  - Container scanning (Trivy)
  - Secret detection (Gitleaks)
  - SAST analysis (Semgrep, CodeQL)

- **Deploy (`deploy.yml`)**: On push to main/tags
  - Builds and pushes to GitHub Container Registry

## Deployment

### Production Deployment

See `docs/DEPLOYMENT.md` and `docs/PILOT_RUNBOOK.md` for detailed instructions.

```bash
# Use production compose file
cd docker
docker compose -f docker-compose.pilot.yml up -d

# Required environment variables for production:
# - POSTGRES_USER, POSTGRES_PASSWORD (strong credentials)
# - SECRET_KEY (generate with: python -c "import secrets; print(secrets.token_urlsafe(32))")
# - CSRF_SECRET_KEY, NETWORK_PEPPER (additional secrets)
```

### Security Checklist

- [ ] Use strong, unique secrets (SECRET_KEY, CSRF_SECRET_KEY, NETWORK_PEPPER)
- [ ] Enable TLS/HTTPS via nginx
- [ ] Configure IP allowlists if required
- [ ] Set up proper network segmentation
- [ ] Enable database encryption at rest
- [ ] Configure appropriate session timeouts
- [ ] Review and configure audit retention policies

## Documentation

Comprehensive documentation is available in the `docs/` directory:

| Document | Description |
|----------|-------------|
| `CHECK_REVIEW_CONSOLE_TECHNICAL_GUIDE.md` | Complete technical specification |
| `BANK_ONBOARDING_GUIDE.md` | Step-by-step bank integration guide |
| `CONNECTOR_SETUP.md` | Connector A, B, C configuration |
| `SECURITY_ARCHITECTURE.md` | Security design and controls |
| `RBAC.md` | Role-based access control details |
| `AUDIT_EVIDENCE_MODEL.md` | Audit trail and evidence sealing |
| `PILOT_RUNBOOK.md` | Production deployment checklist |
| `DISASTER_RECOVERY_DRILL.md` | DR testing procedures |

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Run tests and linting (`pytest`, `npm run lint`)
5. Commit with conventional commits (`fix:`, `feat:`, `docs:`, etc.)
6. Push to your branch
7. Open a Pull Request

## License

Proprietary - All rights reserved.
