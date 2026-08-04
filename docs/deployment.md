# Deployment

Production deployment is intentionally not available in Milestone 0.

The target for Milestone 8 is immutable API, worker, and frontend images on ECS
Fargate, an internet-facing ALB, private tasks and data stores, encrypted RDS
PostgreSQL, Redis, CloudWatch, ACM, Route 53, and optional WAF. Secrets will come
from Secrets Manager or SSM Parameter Store.

Deployment will use commit-SHA image tags, a guarded migration task, service
rollout, smoke tests, and rollback to the previous ECS task definition. The
current Dockerfiles are multi-stage and run application processes as non-root.

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
