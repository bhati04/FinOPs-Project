# CloudWise EC2 Setup and Full-Functionality Checklist

This document separates:

1. Infrastructure and deployment work required to run CloudWise on EC2.
2. Product development still required before CloudWise becomes a complete
   AWS FinOps platform.

> EC2 setup alone will run only the currently implemented Milestone 0
> foundation. Authentication, AWS account onboarding, inventory, cost analysis,
> and recommendations require the later development milestones listed below.

## 1. EC2 infrastructure

For a demonstration environment, provision:

- Ubuntu 24.04 LTS.
- At least 2 vCPU and 4 GB RAM, with additional capacity for real scans.
- A 40–60 GB encrypted gp3 EBS volume.
- An Elastic IP or Application Load Balancer.
- A Route 53 domain.
- An EC2 instance IAM role instead of AWS access keys stored on disk.
- IMDSv2 with tokens required and a metadata hop limit of `2` for containers.
- Systems Manager Session Manager where possible.

### Security-group rules

Allow:

- TCP `443` publicly for HTTPS.
- TCP `80` publicly only to redirect HTTP to HTTPS.
- TCP `22` only from an approved administrator IP, or omit it when using
  Session Manager.

Do not expose these ports publicly:

- `5432` — PostgreSQL.
- `6379` — Redis.
- `8000` — FastAPI.
- `8080` — frontend container.

References:

- [AWS IMDSv2 configuration](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/configuring-IMDS-new-instances.html)
- [AWS EC2 security groups](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/creating-security-group.html)

## 2. EC2 operating-system prerequisites

Install and configure:

- Operating-system security updates.
- Git.
- Docker Engine.
- Docker Buildx.
- Docker Compose plugin.
- AWS CLI v2.
- CloudWatch Agent.
- Automatic security updates.
- Docker log rotation.
- A dedicated deployment user.
- An application directory such as `/opt/cloudwise`.

Install Docker using the official repository rather than the convenience script
for a long-lived environment.

References:

- [Install Docker Engine on Ubuntu](https://docs.docker.com/engine/install/ubuntu/)
- [Install the Docker Compose plugin](https://docs.docker.com/compose/install/linux/)

## 3. Production environment configuration

Create `/opt/cloudwise/.env` and restrict its permissions. Use values similar
to:

```dotenv
CLOUDWISE_ENVIRONMENT=production
CLOUDWISE_LOG_LEVEL=INFO

POSTGRES_DB=cloudwise
POSTGRES_USER=cloudwise
POSTGRES_PASSWORD=<strong-random-password>

CLOUDWISE_DATABASE_URL=postgresql+asyncpg://cloudwise:<url-encoded-password>@postgres:5432/cloudwise
CLOUDWISE_REDIS_URL=redis://redis:6379/0

CLOUDWISE_CORS_ORIGINS=["https://cloudwise.example.com"]
CLOUDWISE_API_REQUEST_MAX_BYTES=1048576

# Keep disabled until Milestone 6 exposes an authenticated, tenant-scoped
# Generate AI suggestion action.
CLOUDWISE_AI_ADVISOR_ENABLED=false
CLOUDWISE_AI_ADVISOR_PROVIDER=bedrock
CLOUDWISE_AI_ADVISOR_MODEL_ID=
CLOUDWISE_AI_ADVISOR_AWS_REGION=us-east-1
CLOUDWISE_AI_ADVISOR_MAX_OUTPUT_TOKENS=800
CLOUDWISE_AI_ADVISOR_TIMEOUT_SECONDS=20

VITE_API_BASE_URL=https://cloudwise.example.com/api/v1
```

Requirements:

- Generate strong random credentials.
- URL-encode special characters in `CLOUDWISE_DATABASE_URL`.
- Never commit `.env`.
- Keep production secrets in AWS Secrets Manager or SSM Parameter Store.
- Rebuild the frontend when `VITE_API_BASE_URL` changes because Vite embeds it
  during the image build.

Later milestones will require additional configuration for:

- Access-token signing.
- Refresh-token encryption and revocation.
- External ID encryption.
- CSRF protection.
- Email notifications.
- Report storage and signing.

## 4. Domain, HTTPS, and reverse proxy

Use one public origin, for example:

```text
https://cloudwise.example.com
```

Configure an Application Load Balancer or host-level reverse proxy:

```text
/          -> 127.0.0.1:8080
/api/*     -> 127.0.0.1:8000
```

Configure:

- Route 53 DNS.
- An ACM certificate when using an ALB.
- An HTTPS listener.
- HTTP-to-HTTPS redirection.
- Secure response headers.
- Request-size limits.
- A load-balancer health check using `/api/v1/health/live`.

Keep FastAPI, PostgreSQL, and Redis inaccessible from the public internet.

## 5. Application deployment

From `/opt/cloudwise`:

```bash
docker compose config
docker compose build
docker compose run --rm backend alembic upgrade head
docker compose up -d
docker compose ps
```

Verify:

```bash
curl https://cloudwise.example.com/api/v1/health/live
curl https://cloudwise.example.com/api/v1/health/ready
```

Expected readiness response:

```json
{
  "status": "ready",
  "checks": {
    "database": { "status": "up" },
    "redis": { "status": "up" }
  }
}
```

Create a systemd service so the stack starts after an instance restart. Add a
production Compose override for resource limits, immutable images, production
commands, restart policies, and removal of development source mounts.

Reference:

- [Use Docker Compose in production](https://docs.docker.com/compose/how-tos/production/)

## 6. PostgreSQL and Redis

### Demonstration environment

PostgreSQL and Redis may run in Docker Compose for a portfolio demonstration.
Back up their Docker volumes and verify restoration.

### Production environment

Use Amazon RDS PostgreSQL with:

- Encryption at rest.
- TLS connections.
- Automated backups.
- Point-in-time recovery.
- Private subnets.
- Deletion protection.
- Multi-AZ for production workloads.

Use Amazon ElastiCache for Redis with:

- Private subnets.
- Encryption in transit.
- Encryption at rest.
- Authentication.
- Automatic failover where required.

RDS encryption covers storage, logs, automated backups, snapshots, and read
replicas.

Reference:

- [Encrypting Amazon RDS resources](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/Overview.Encryption.html)

## 7. CloudWise platform IAM role

The application compute role will eventually require:

- `sts:AssumeRole` for explicitly approved customer-role ARNs.
- `bedrock:InvokeModel` for the single approved AI model or inference profile
  only when the on-demand AI advisor is enabled.
- Read access to application secrets.
- KMS decrypt permission for the application encryption key.
- CloudWatch Logs and custom-metric permissions.
- Access to the report S3 bucket.
- SES permissions if email delivery is enabled.

Do not grant administrator access. Restrict actions and resources to those
required by CloudWise. The AI advisor uses the EC2 instance role; do not place
static AWS credentials in the environment file. Apply an AWS Budget and
CloudWatch billing alarm before enabling model calls, and confirm that the
selected model is available in `CLOUDWISE_AI_ADVISOR_AWS_REGION`.

## 8. Customer AWS account role

Each connected AWS account requires a dedicated CloudWise read-only IAM role.

The role must:

- Trust only the CloudWise platform IAM role.
- Require a unique CloudWise-generated `ExternalId`.
- Grant only discovery and analysis permissions.
- Deny destructive remediation capabilities.
- Be created through the future CloudFormation or Terraform onboarding
  template.

AWS recommends that a third-party service generate and control a unique
External ID for each customer to prevent confused-deputy access.

Reference:

- [AWS confused-deputy guidance](https://docs.aws.amazon.com/IAM/latest/UserGuide/confused-deputy.html)

The read-only policy will cover:

- STS and account identity.
- EC2 instances.
- EBS volumes and snapshots.
- Elastic IP addresses.
- RDS instances and clusters.
- S3 metadata and lifecycle configuration.
- Lambda functions and versions.
- Application and Network Load Balancers.
- NAT gateways and VPC metadata.
- ECS clusters and services.
- EKS clusters.
- CloudWatch metrics.
- Cost Explorer.
- Compute Optimizer when enabled.
- Resource tags.

## 9. Remaining product development

### Milestone 1 — Identity and multi-tenancy

- User registration and login.
- Password recovery.
- Argon2id password hashing.
- Short-lived access tokens.
- Rotating and revocable refresh tokens.
- Organizations and memberships.
- Owner, Admin, Analyst, and Viewer roles.
- Tenant isolation.
- Rate limiting and CSRF protection.
- Team-management interface.

### Milestone 2 — AWS account onboarding

- AWS account connection records.
- Unique encrypted External IDs.
- CloudFormation and Terraform onboarding templates.
- Role ARN validation.
- STS AssumeRole verification.
- GetCallerIdentity confirmation.
- Onboarding audit records.

### Milestone 3 — Mock inventory and scan orchestration

- AWS provider interfaces.
- Realistic fixture accounts and resources.
- Scan state machine.
- Celery scan jobs.
- Per-account distributed locks.
- Inventory persistence.
- Scan history and failure interface.
- Throttling and partial-failure fixtures.

### Milestone 4 — Real AWS inventory

- EC2, EBS, snapshots, and Elastic IP discovery.
- RDS, S3, Lambda, and ELB discovery.
- NAT, ECS, and EKS discovery.
- Multi-Region scans.
- Pagination.
- Backoff, jitter, and throttling handling.
- Partial-success persistence.
- Idempotent resource updates.
- Inactive-resource history.

### Milestone 5 — Cost and metrics

- Cost Explorer synchronization.
- Daily and monthly cost aggregates.
- Current-month forecasts.
- Service, account, Region, usage-type, and tag grouping.
- CloudWatch GetMetricData batching.
- Cost charts.
- Resource metrics.
- Multi-currency handling.

### Milestone 6 — Recommendation engine

- Versioned rule framework.
- Initial recommendation rules.
- Pricing-provider abstraction.
- Evidence and calculation inputs.
- Confidence and severity.
- Exact, usage-based, and advisory estimates.
- Recommendation lifecycle.
- Status history and comments.

### Milestone 7 — Reports, notifications, and audit

- CSV reports.
- PDF reports.
- Scheduled report generation.
- Email notifications.
- Append-only audit records.
- Report storage and expiration.
- Audit-log interface.

### Milestone 8 — Production hardening

- Complete Terraform infrastructure.
- ECS Fargate services.
- RDS and ElastiCache.
- ALB, ACM, and Route 53.
- Optional WAF.
- Secrets Manager and KMS.
- CloudWatch dashboards and alarms.
- OpenTelemetry tracing.
- Backup and restore exercises.
- Load and failure testing.
- ECR image publishing.
- Migration jobs and deployment rollback.

## 10. Operational readiness

Before production use, implement:

- Automated encrypted backups.
- Regular restoration testing.
- CloudWatch logs and alarms.
- CPU, memory, disk, and queue-depth monitoring.
- Scan-failure alerts.
- Database-connectivity alerts.
- Worker heartbeat monitoring.
- Log-retention policies.
- AWS Budget alerts.
- Patch-management procedures.
- Dependency, secret, container, and IaC scanning.
- Incident-response procedures.
- Disaster-recovery exercises.
- Immutable image versioning.
- Safe database migration and rollback procedures.

## 11. Recommended final architecture

```text
Route 53
   |
ACM + Application Load Balancer
   |
   +-- Frontend container
   |
   +-- FastAPI containers
          |
          +-- RDS PostgreSQL
          +-- ElastiCache Redis
          +-- Celery workers
          +-- Secrets Manager and KMS
          +-- S3 reports
          +-- CloudWatch and OpenTelemetry
          +-- STS AssumeRole -> Customer AWS accounts
```

A single EC2 Compose deployment is appropriate for development and portfolio
demonstrations. A production deployment should move PostgreSQL and Redis off the
instance and remove the EC2 single point of failure.

## 12. Full-functionality acceptance checklist

CloudWise is fully functional only when:

- A user can register, log in, recover access, and refresh a session securely.
- Organization roles and tenant isolation are enforced.
- A customer account can be onboarded with STS and a unique External ID.
- Mock and real inventory scans complete with pagination and partial failures.
- Costs and required CloudWatch metrics synchronize.
- Recommendation rules produce explainable, auditable estimates.
- Recommendation lifecycle actions are authorized and recorded.
- CSV and PDF reports can be generated.
- Notifications are delivered and retried.
- Audit events are append-only.
- All containers and managed dependencies expose useful health signals.
- Backups can be restored.
- CI security and quality gates pass.
- Production deployment and rollback procedures are proven.
- No customer AWS resource is automatically modified or deleted.
