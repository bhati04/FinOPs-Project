# Testing

Tests cover configuration, health contracts, authentication security,
organization boundaries, AWS provider responses, inventory normalization,
middleware safety, and production builds.

The root GitHub Actions workflow runs the same Compose validation and backend
and frontend quality gates on pushes to `main` and on pull requests. Milestone 8
also validates the Terraform configuration with:

```bash
cd infra/terraform
terraform fmt -check -recursive
terraform init -backend=false
terraform validate
```

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

Before a production release, add full PostgreSQL/Redis integration tests, AWS
Stubber task tests, migration round-trip tests, and a mock-mode end-to-end scan
workflow in addition to these unit and contract checks.
