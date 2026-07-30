# Deployment

Production deployment is intentionally not available in Milestone 0.

The target for Milestone 8 is immutable API, worker, and frontend images on ECS
Fargate, an internet-facing ALB, private tasks and data stores, encrypted RDS
PostgreSQL, Redis, CloudWatch, ACM, Route 53, and optional WAF. Secrets will come
from Secrets Manager or SSM Parameter Store.

Deployment will use commit-SHA image tags, a guarded migration task, service
rollout, smoke tests, and rollback to the previous ECS task definition. The
current Dockerfiles are multi-stage and run application processes as non-root.

