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
│   │   └── audit/         # Audit logging
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

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests
5. Submit a pull request

## License

Proprietary - All rights reserved.
