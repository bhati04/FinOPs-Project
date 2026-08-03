# Known limitations

- Registration, login, rotating refresh sessions, an initial organization
  owner role, and protected AWS views are implemented. Password recovery, team
  management, rate limiting, and multi-organization switching are not.
- Customer roles can be verified and scanned. Inventory covers EC2, EBS,
  snapshots, Elastic IPs, NAT, RDS, Lambda, load balancers, ECS, EKS, and S3 in
  one selected Region per scan. Multi-Region scheduling, RDS clusters, ECS
  services, EKS node groups, and deeper service metadata are not implemented.
- Cost Explorer UnblendedCost actuals and forecasts are collected on demand.
  Scheduled synchronization, amortized and net cost metrics, CloudWatch usage
  metrics, recommendations, reports, notifications, and audit events are not
  implemented. The optional grouping supports one configured cost-allocation
  tag, and AWS billing data can be delayed or revised.
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
