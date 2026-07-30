# Known limitations

- Registration, login, rotating refresh sessions, an initial organization
  owner role, and protected AWS views are implemented. Password recovery, team
  management, rate limiting, and multi-organization switching are not.
- Customer roles can be verified and scanned. Inventory currently covers EC2
  in one selected Region per scan; multi-Region scheduling and other AWS
  resource types are not implemented.
- No costs, metrics, recommendations, reports, notifications, or audit events
  are collected.
- Compose checks worker health through Celery control ping, but the public
  readiness API does not yet expose worker status.
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
