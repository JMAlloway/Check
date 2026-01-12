# Check Review Console

A bank-grade web application for community bank operations teams to review presented checks in a faster, more consistent, and audit-defensible way. The system is human-in-the-loop: reviewers and approvers make final decisions while the system provides workflow, context, and assistive analytics.

## Features

### Core Functionality
- **Check Image Viewer**: Bank-grade UX with zoom, pan, magnifier, brightness/contrast controls
- **ROI Overlays**: User-defined regions of interest for amount box, signature, MICR line, etc.
- **Side-by-Side Comparison**: Compare current check with historical checks from the same account
- **Context Panel**: Account tenure, balance, check behavior stats, returned item history
- **AI Flags**: Explainable rule-based flags with confidence levels and explanations

### Workflow
- **Dual Control**: Configurable thresholds for two-person approval
- **Queue Management**: Priority-based queues with SLA tracking
- **Policy Engine**: Versioned, configurable business rules
- **Full Audit Trail**: Every action logged for compliance

### Security
- **Role-Based Access Control (RBAC)**: Granular permissions
- **Session Management**: Secure token-based authentication
- **IP Restrictions**: Configurable allowed IP addresses
- **Signed URLs**: Time-limited secure image access

## Tech Stack

- **Backend**: Python 3.11, FastAPI, SQLAlchemy, PostgreSQL
- **Frontend**: React 18, TypeScript, TailwindCSS, React Query
- **Infrastructure**: Docker, Redis, Nginx
- **CI/CD**: GitHub Actions

## Quick Start

### Prerequisites
- Docker and Docker Compose
- Node.js 20+ (for local frontend development)
- Python 3.11+ (for local backend development)

### Running with Docker

```bash
# Clone the repository
git clone <repository-url>
cd Check

# Copy environment file
cp docker/.env.example docker/.env
# Edit docker/.env with your configuration

# Start all services
cd docker
docker-compose up -d

# The application will be available at:
# - Frontend: http://localhost:3000
# - Backend API: http://localhost:8000
# - API Docs: http://localhost:8000/api/v1/docs
```

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
export DEBUG=true

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
│   │   ├── api/           # API endpoints
│   │   ├── core/          # Configuration and security
│   │   ├── db/            # Database configuration
│   │   ├── models/        # SQLAlchemy models
│   │   ├── schemas/       # Pydantic schemas
│   │   ├── services/      # Business logic
│   │   ├── integrations/  # External system adapters
│   │   ├── policy/        # Policy engine
│   │   ├── audit/         # Audit logging
│   │   └── demo/          # Demo mode (synthetic data, mock providers)
│   ├── alembic/           # Database migrations
│   └── tests/             # Test suites
├── frontend/
│   ├── src/
│   │   ├── components/    # React components
│   │   ├── pages/         # Page components
│   │   ├── services/      # API services
│   │   ├── stores/        # State management
│   │   └── types/         # TypeScript types
│   └── public/
├── docker/                # Docker configuration
├── docs/                  # Documentation
└── .github/               # CI/CD workflows
```

## API Documentation

The API documentation is available at `/api/v1/docs` when the backend is running.

### Key Endpoints

- `POST /api/v1/auth/login` - User authentication
- `GET /api/v1/checks` - List check items
- `GET /api/v1/checks/{id}` - Get check item details
- `POST /api/v1/decisions` - Create a decision
- `GET /api/v1/queues` - List queues
- `GET /api/v1/reports/dashboard` - Dashboard statistics

## Demo Mode

The application includes a comprehensive Demo Mode for demonstrations, training, and sales purposes. Demo mode uses synthetic data and never connects to external systems.

### Enabling Demo Mode

```bash
# Set environment variables
export DEMO_MODE=true
export ENVIRONMENT=development  # Required - Demo mode is blocked in production

# Or in docker/.env
DEMO_MODE=true
ENVIRONMENT=development
```

### Demo Credentials

When demo mode is enabled, the following credentials are available:

| Username | Password | Role | Description |
|----------|----------|------|-------------|
| `reviewer_demo` | `DemoReviewer123!` | Reviewer | Can view and review check items |
| `approver_demo` | `DemoApprover123!` | Approver | Can approve dual-control decisions |
| `admin_demo` | `DemoAdmin123!` | Admin | Full system access |

### Seeding Demo Data

```bash
# Seed demo data via API (requires admin auth)
POST /api/v1/system/demo/seed
{
  "count": 60,
  "reset_existing": false
}

# Or via CLI
cd backend
python -m app.demo.seed --reset --count 60
```

### Demo Features

- **Synthetic Check Items**: 60+ check items with various scenarios (routine, suspicious, fraud)
- **Mock AI Analysis**: Deterministic AI recommendations based on scenarios
- **Demo Images**: Watermarked check images clearly marked as "DEMO - NOT A REAL CHECK"
- **Sample Workflows**: Items in various workflow states for demonstration
- **Visual Indicators**: Banner and badges clearly indicate demo mode

### Safety Requirements

- Demo mode **cannot** be enabled in production (`ENVIRONMENT=production`)
- All demo data is marked with `is_demo=true` in the database
- Demo data can be cleared without affecting real data
- No real PII or external system connections

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | Required |
| `SECRET_KEY` | JWT signing key | Required |
| `REDIS_URL` | Redis connection string | `redis://localhost:6379/0` |
| `DEBUG` | Enable debug mode | `false` |
| `CORS_ORIGINS` | Allowed CORS origins | `["http://localhost:3000"]` |
| `DUAL_CONTROL_THRESHOLD` | Amount requiring dual control | `5000.0` |
| `AI_ENABLED` | Enable AI features | `false` |
| `DEMO_MODE` | Enable demo mode with synthetic data | `false` |
| `DEMO_DATA_COUNT` | Number of demo items to seed | `60` |

## Integration Adapters

The system supports multiple core banking integrations through an adapter layer:

- **Mock Adapter**: For development and testing
- **Q2 Adapter**: (Planned) For Q2 integration
- **Fiserv Adapter**: (Planned) For Fiserv integration

To implement a new adapter, implement the interfaces in `backend/app/integrations/interfaces/base.py`.

## User Roles

| Role | Permissions |
|------|-------------|
| Reviewer | View items, make review recommendations |
| Approver | All reviewer permissions + final approval |
| Manager | All approver permissions + manage queues and users |
| Admin | Full system access |
| Auditor | Read-only access to all data and audit logs |

## Compliance & Audit

- All user actions are logged to an immutable audit trail
- Policy versions are tracked and applied to each decision
- Audit packets can be generated for individual items
- Reports available for throughput, decisions, and reviewer performance

## Testing

### Backend Tests

```bash
cd backend
pytest tests/ -v --cov=app
```

### Frontend Tests

```bash
cd frontend
npm test
```

## Deployment

### Production Deployment

1. Build production Docker images:
```bash
docker build -f docker/Dockerfile.backend.prod -t check-review-backend:latest ./backend
docker build -f docker/Dockerfile.frontend.prod -t check-review-frontend:latest ./frontend
```

2. Configure environment variables for production
3. Set up PostgreSQL and Redis instances
4. Deploy using your orchestration platform (Kubernetes, ECS, etc.)

### Security Considerations

- Use strong, unique `SECRET_KEY` in production
- Enable TLS/HTTPS
- Configure IP allowlists if required
- Set up proper network segmentation
- Enable database encryption at rest
- Configure session timeouts appropriately

## Recent Development Updates

### January 2026 - MVP Development Session

This section documents the fixes and improvements made during the MVP development phase.

#### Issues Resolved

1. **PostgreSQL Enum Type Creation**
   - Fixed async enum type creation during database initialization
   - Added checks for existing enum types before creating them
   - Affected enums: `fraud_type`, `fraud_channel`, `amount_bucket`, `fraud_event_status`, `match_severity`

2. **Docker Configuration**
   - Re-enabled backend volume mount for development hot-reloading
   - Fixed SECRET_KEY mismatch between `docker-compose.yml` and `config.py` defaults
   - Both now use: `change-this-in-production-use-secure-random-key`

3. **Check Image Loading**
   - **Bearer Token Issue**: Removed `require_permission` dependency from `/api/v1/images/secure/{token}` endpoint - `<img>` tags cannot send Authorization headers, so the endpoint now self-authenticates via the signed URL token
   - **Signed URL TTL**: Increased `IMAGE_SIGNED_URL_TTL_SECONDS` from 60s to 3600s (1 hour) to prevent "Invalid or expired image URL" errors during review sessions
   - **Thumbnail URLs**: Added `resolveImageUrl()` to QueuePage for proper thumbnail URL resolution
   - **Error Handling**: Added loading states and error messages to CheckImageViewer component

4. **Database Schema Fixes**
   - Fixed `audit_logs.resource_id` column size from VARCHAR(36) to VARCHAR(255) to accommodate demo image IDs (format: `DEMO-IMG-{uuid}-front/back`)
   - Added automatic ALTER TABLE during startup for existing databases

5. **API Endpoint Fixes**
   - Fixed `get_check_history` endpoint: removed extraneous `tenant_id` argument that caused "got multiple values for argument 'limit'" error
   - Added `tenant_id` parameter to `get_check_item` calls for proper multi-tenant isolation

#### Files Modified

| File | Changes |
|------|---------|
| `backend/app/main.py` | Added enum type creation, ALTER TABLE for audit_logs |
| `backend/app/api/v1/endpoints/images.py` | Removed require_permission, added self-authentication |
| `backend/app/api/v1/endpoints/checks.py` | Fixed tenant_id and limit parameter handling |
| `backend/app/core/config.py` | Increased IMAGE_SIGNED_URL_TTL_SECONDS to 3600 |
| `backend/app/models/audit.py` | Changed resource_id to String(255) |
| `docker/docker-compose.yml` | Fixed SECRET_KEY default, re-enabled volume mount |
| `frontend/src/pages/QueuePage.tsx` | Added resolveImageUrl for thumbnails |
| `frontend/src/components/check/CheckImageViewer.tsx` | Added loading/error states |

#### Running the Application

After pulling the latest changes:

```bash
# Navigate to project
cd Check

# Start Docker containers
cd docker
docker-compose down
docker-compose up

# Access the application
# Frontend: http://localhost:3000
# Backend API: http://localhost:8000
# API Docs: http://localhost:8000/api/v1/docs
```

#### Troubleshooting

**Images not loading:**
1. Check browser console (F12) for error messages
2. Verify SECRET_KEY is consistent in docker-compose.yml
3. Restart containers after config changes: `docker-compose down && docker-compose up`

**401 Unauthorized on images:**
- The signed URL token may have expired (1 hour TTL)
- SECRET_KEY may have changed between signing and verification
- Solution: Refresh the page to get new signed URLs

**Database errors on startup:**
- If you see VARCHAR truncation errors, ensure you have the latest code with the audit_logs fix
- The backend auto-applies ALTER TABLE on startup in development mode

---

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests
5. Submit a pull request

## License

Proprietary - All rights reserved.
