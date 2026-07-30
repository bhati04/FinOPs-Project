# CloudWise FinOps Platform

CloudWise is a production-oriented foundation for secure, explainable,
multi-account AWS cost visibility and governance. The current repository
implements the platform foundation, organization-scoped identity, secure AWS
role onboarding, and asynchronous read-only EC2 inventory scans.

> Cost analysis, recommendation rules, reports, and automated remediation are
> not implemented yet. A disabled, unexposed AI-advisor provider foundation
> exists for a future user-clicked recommendation explanation; it does not call
> a model during scans or page loads.

## Architecture at a glance

- `backend/` — Python 3.12, FastAPI modular monolith, SQLAlchemy-ready
  PostgreSQL access, Redis, and a separate Celery worker.
- `frontend/` — React 19-compatible TypeScript application built by Vite with
  Material UI, TanStack Query, React Router, Zod, and Vitest.
- `infra/terraform/` — validated production-infrastructure contract; deployable
  resources arrive during production hardening.
- `docs/` — architecture, security, operations, testing, and decision records.

## Quick start

Requirements: Docker Desktop with Docker Compose v2.

```bash
docker compose up --build -d
docker compose ps
```

Open:

- Web application: <http://localhost:8080>
- API documentation: <http://localhost:8000/api/docs>
- API liveness: <http://localhost:8000/api/v1/health/live>
- API readiness: <http://localhost:8000/api/v1/health/ready>

The default values are safe local-development values. To override them:

```bash
cp .env.example .env
docker compose up --build -d
```

Never reuse the example database password outside local development.

For frontend hot reload, run the development profile:

```bash
docker compose --profile dev up --build frontend-dev
```

## Brand assets

Browser icons live in `frontend/public/`. The favicon uses the CloudWise
navy-and-mint cloud insight mark, with PNG variants for browsers and Apple
devices plus an ICO fallback.

## Validation

```bash
docker compose config --quiet
docker compose build backend frontend
docker compose run --rm backend sh -c \
  "ruff format --check . && ruff check . && mypy src && pytest"
docker compose run --rm frontend-dev sh -c \
  "npm run format:check && npm run lint && npm run typecheck && npm test -- --run && npm run build"
```

See [local development](docs/local-development.md) and
[testing](docs/testing.md) for native commands and troubleshooting.

For the complete EC2 deployment and product-readiness checklist, see
[EC2 setup and full-functionality checklist](docs/ec2-full-setup-checklist.md).

## Milestones

| Milestone | Scope | Status |
| --- | --- | --- |
| 0 | Repository, containers, health, CI, docs | Implemented |
| 1 | Identity, organizations, RBAC, tenant isolation | Implemented |
| 2 | Secure AWS account onboarding | Implemented |
| 3 | Inventory persistence and scan orchestration | Implemented |
| 4 | Broader real AWS inventory | In progress: EC2, one Region per scan |
| 5 | Cost and metrics | Not started |
| 6 | Recommendation engine | Not started |
| 7 | Reports, notifications, and audit | Not started |
| 8 | Production hardening and deployment | Not started |

Each later milestone still requires review before its scope is expanded.
