# Known limitations

- Milestone 0 provides no authentication, RBAC, or tenant data.
- No AWS account can be connected.
- No resources, costs, metrics, recommendations, reports, notifications, or
  audit events are collected.
- Compose checks worker health through Celery control ping, but the public
  readiness API does not expose worker status. A scalable heartbeat-backed API
  check is deferred until job orchestration.
- Local PostgreSQL and Redis credentials are intentionally simple and must not
  be used outside local development.
- Terraform defines validation and naming contracts only; it provisions no
  infrastructure.
- Request-size enforcement currently rejects oversized declared
  `Content-Length`; streaming byte enforcement will be added with write APIs.
- Production observability, backup, restore, scaling, and SLOs are not yet
  implemented.
- React Router's current release has an upstream RSC-only CSRF advisory. RSC is
  not enabled, and CI tracks a narrowly scoped temporary exception documented
  in `docs/security.md`.
