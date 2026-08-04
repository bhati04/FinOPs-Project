# Known limitations

- Registration, login, rotating refresh sessions, an initial organization
  owner role, and protected AWS views are implemented. Password recovery, team
  management, rate limiting, and multi-organization switching are not.
- Customer roles can be verified and scanned. Inventory covers EC2, EBS,
  snapshots, Elastic IPs, NAT, RDS, Lambda, load balancers, ECS, EKS, and S3 in
  one selected Region per scan. Multi-Region scheduling, RDS clusters, ECS
  services, EKS node groups, and deeper service metadata are not implemented.
- Cost Explorer UnblendedCost actuals and forecasts are collected on demand.
  Scheduled cost synchronization, amortized and net cost metrics, and
  CloudWatch usage beyond the supported resource set are not implemented.
  CloudWatch synchronization is on
  demand and currently covers EC2, EBS, NAT gateways, RDS instances, Lambda,
  and application load balancers at hourly granularity. The optional cost
  grouping supports one configured cost-allocation tag, and AWS billing data
  can be delayed or revised. The dashboard's monthly estimate is a simple
  daily run-rate projection and does not model seasonality or planned workload
  changes.
- Recommendation evaluation is on demand and currently covers only unattached
  EBS volumes and unassociated Elastic IPs using persisted inventory. Numeric
  savings use AWS on-demand list prices and do not account for discounts,
  credits, taxes, free-tier benefits, or partial-month usage. Scheduling,
  metric-driven CloudWise rules, realized-savings measurement, and the optional
  AI explanation endpoint are not implemented. Cost Optimization Hub and
  regional EC2/EBS Compute Optimizer imports require those AWS services to be
  enabled and only persist findings that match active CloudWise inventory.
- CSV/PDF reports, recurring schedules, private retention, SES-ready notices,
  and a platform-wide append-only mutation audit are implemented. The compact
  PDF is a summary (CSV is the full detail format), email is disabled until SES
  is configured, and production report storage requires an S3 bucket.
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
