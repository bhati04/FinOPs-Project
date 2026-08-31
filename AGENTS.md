# CloudWise contributor guide

These instructions apply to the entire repository.

## Product boundary

CloudWise is a multi-tenant AWS FinOps platform. Milestones 0 through 7 are
implemented, and Milestone 8 production hardening was approved by the product
owner on 2026-08-31. Milestone 8 work may add production infrastructure,
deployment automation, observability, backup and recovery controls, and
security hardening. Product features outside the approved milestone roadmap
still require explicit approval.

## Engineering rules

- Keep the backend a modular monolith with domain packages under
  `backend/src/cloudwise/`.
- Keep API routes versioned under `/api/v1`.
- Keep public schemas separate from persistence models.
- Use UTC-aware timestamps, UUID primary keys, and Alembic for future schema
  changes.
- Never log secrets, credentials, authorization headers, cookies, raw external
  IDs, or environment values.
- Enforce organization scoping in services and routes once tenant data exists.
- Preserve mock and real AWS provider boundaries.
- Never automate destructive customer AWS actions.
- Add tests and documentation with every behavior change.

## Required checks

Run `make check` where Make is available. Equivalent Docker commands are
documented in `docs/testing.md`.
