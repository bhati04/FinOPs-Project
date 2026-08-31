# Deployment

Production hardening is now in progress under the approved Milestone 8 scope.

The target for Milestone 8 is immutable API, worker, and frontend images on ECS
Fargate, an internet-facing ALB, private tasks and data stores, encrypted RDS
PostgreSQL, Redis, CloudWatch, ACM, Route 53, and optional WAF. Secrets will come
from Secrets Manager or SSM Parameter Store.

The current production runtime is an existing EC2 instance running Docker
Compose. Deployment uses commit-SHA image tags, a guarded migration container,
service rollout, smoke tests, and rollback to the previous locally tagged images. The current
Dockerfiles are multi-stage and run application processes as non-root.

## Infrastructure delivery status

The first Terraform slice establishes multi-AZ networking, isolated data
subnets, per-AZ egress, KMS, private report storage, immutable ECR repositories,
and CloudWatch log groups. The second slice adds the ECS runtime, RDS,
ElastiCache, HTTPS ingress, secrets, guarded migrations, smoke tests, and service
rollback. Do not direct production traffic to it until hosted validation passes,
the required GitHub environment is protected and configured, and the remaining
alarm, restore, and load/failure exercises are complete.

## Continuous deployment

`.github/workflows/deploy-production.yml` runs after the `CI` workflow succeeds
on `main`, or through a manual dispatch. The `production` GitHub environment
should require an approver. The workflow assumes an AWS role through GitHub
OIDC and sends a deployment command to the existing EC2 instance through
Systems Manager. On EC2, the command fetches and checks out the exact CI-validated
commit, builds commit-tagged production images, preserves the existing named
PostgreSQL, Redis, and report volumes, runs Alembic, recreates application
containers, and calls the local liveness and readiness endpoints. A failed
rollout restores the previously tagged backend and frontend images. Database
migrations must remain backward compatible because image rollback does not
reverse a completed schema migration.

Configure these GitHub production environment values:

| Kind | Name | Purpose |
| --- | --- | --- |
| Secret | `AWS_DEPLOY_ROLE_ARN` | AWS IAM role trusted for this repository and production environment |
| Variable | `AWS_REGION` | AWS deployment Region |
| Variable | `EC2_INSTANCE_ID` | Existing SSM-managed instance identifier |
| Variable | `EC2_DEPLOY_PATH` | Absolute application directory, currently expected to be `/home/ubuntu/FinOPs-Project` |
| Variable | `APPLICATION_BASE_URL` | Optional public origin such as `http://203.0.113.10`; when omitted, EC2 discovers its public IPv4 address through IMDSv2 |

Do not configure static `AWS_ACCESS_KEY_ID` or `AWS_SECRET_ACCESS_KEY` values.
The deploy role should trust only the repository's GitHub OIDC subject and have
only SSM command permissions for the named instance. The EC2 instance profile
must allow SSM management. Git, the SSM agent, Docker, and Docker Compose v2 must
be installed on the instance, and the existing checkout must be able to fetch
the GitHub repository non-interactively. Runtime secrets remain in the
instance's restricted `.env`; the workflow never transfers or prints them.

## Milestone 7 runtime additions

The worker and API must share the configured local report volume outside
production. Production must set `CLOUDWISE_REPORT_STORAGE_PROVIDER=s3` and
`CLOUDWISE_REPORT_S3_BUCKET`. Run exactly one Celery beat scheduler using
`cloudwise.worker:celery_app`; it dispatches scheduled reports and expiration
cleanup. The scheduler stores its local Celery Beat state under `/tmp` because
the production image runs as a non-root user and `/app` is intentionally not
writable.

SES delivery is optional. Enable it with
`CLOUDWISE_NOTIFICATION_PROVIDER=ses`,
`CLOUDWISE_NOTIFICATION_FROM_EMAIL`, and
`CLOUDWISE_NOTIFICATION_SES_REGION`. The platform role then requires
`ses:SendEmail`. S3 report storage requires least-privilege GetObject,
PutObject, and DeleteObject access only under the configured report prefix.
