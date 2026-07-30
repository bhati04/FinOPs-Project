# Testing

Milestone 0 tests focus on configuration, health contracts, middleware safety,
dependency failure behavior, UI response validation, and production builds.

## Backend

```bash
docker compose run --rm backend sh -c \
  "ruff format --check . && ruff check . && mypy src && pytest"
```

## Frontend

```bash
docker compose --profile dev run --rm frontend-dev sh -c \
  "npm run format:check && npm run lint && npm run typecheck && npm test -- --run && npm run build"
```

## Stack

```bash
docker compose config --quiet
docker compose up --build -d
docker compose ps
```

Later milestones must add PostgreSQL and Redis integration tests, migration
tests, tenant-isolation tests, AWS Stubber and moto tests, Celery task tests,
contract tests, and mock-mode end-to-end workflows.

