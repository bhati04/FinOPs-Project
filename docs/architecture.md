# Architecture

CloudWise uses a modular monolith for its HTTP API and a separate Celery worker.
Domain modules share one deployable codebase while maintaining explicit service,
schema, and persistence boundaries. This keeps early operations simple and
allows high-load domains to be extracted later.

## Runtime components

```text
Browser -> Frontend (nginx) -> FastAPI
                              |-> PostgreSQL
                              |-> Redis <- Celery worker
                              |            ^ Celery beat scheduler
                              |-> private report storage
```

The API and worker access customer AWS accounts only through provider
interfaces backed by short-lived STS AssumeRole sessions.

The optional `ai_advisor` module is a future-facing outbound provider boundary.
It is disabled by default and currently has no route, task, or persistence. A
future authenticated recommendation action can invoke it on demand after tenant
authorization. It cannot initiate AWS changes.

## Backend module contract

Each business domain belongs under `backend/src/cloudwise/<domain>/` and should
contain explicit public schemas, application services, persistence models and
repositories, and API routes or worker tasks as needed. Cross-domain imports
must flow through public service contracts rather than persistence internals.

Business domains include identity, organizations, aws_accounts, scans,
inventory, cost_management, metrics, recommendations, reports, notifications,
audit, and platform_health. `ai_advisor` is a disabled optional qualitative
explanation service owned by the recommendations domain; it is not a source of
cost facts.

Recommendation pricing is owned by the recommendations domain behind a provider
contract. Production reads the global AWS Price List with platform credentials;
it never expands the customer assumed-role boundary.

Cost Optimization Hub and Compute Optimizer imports remain behind normalized
read-only provider contracts. Reports, schedules, notification deliveries, and
audit events are owned by the `reports` domain. Production report objects use
private S3 storage; SES and storage use platform credentials rather than a
customer assumed role.

## Deployment direction

The first production target is ECS Fargate across private subnets, behind an
ALB, with RDS PostgreSQL and Redis. Terraform deployment resources are
intentionally deferred to Milestone 8; the current skeleton pins the tool and
provider contract without pretending to be production-ready.

See the decision records for trade-offs and `docs/data-flow.md` for request
boundaries.
