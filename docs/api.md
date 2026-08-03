# API

All application endpoints are versioned under `/api/v1`. Interactive OpenAPI is
available at `/api/docs`; the machine-readable document is `/api/openapi.json`.

## Health endpoints

`GET /api/v1/health/live`

Returns `200 {"status":"ok"}` when the API process can serve requests. It does
not check external dependencies.

`GET /api/v1/health/ready`

Returns `200` when PostgreSQL and Redis respond within the probe deadline, or
`503` when either is unavailable.

```json
{
  "status": "ready",
  "checks": {
    "database": { "status": "up" },
    "redis": { "status": "up" }
  }
}
```

Every HTTP response includes `X-Correlation-ID`. A caller-supplied value is
accepted only when it is a valid UUID; otherwise the API generates a new one.

## Identity endpoints

`POST /api/v1/auth/register` creates a user, organization, and owner
membership. `POST /api/v1/auth/login` issues a short-lived access token and an
opaque rotating refresh token. Refresh tokens are stored only as SHA-256
digests and can be revoked through `POST /api/v1/auth/logout`.

`GET /api/v1/auth/me` and all AWS account routes require an
`Authorization: Bearer <access-token>` header. The access token carries the
user, organization, and role identifiers; the API also verifies that the
membership remains active in PostgreSQL before authorizing a request.

## Inventory scan endpoints

`POST /api/v1/aws-accounts/connections/{connection_id}/scans?region=us-east-1`
queues a read-only AWS inventory scan for a verified connection. Owners,
administrators, and analysts may start scans. Only one queued or running scan
is allowed per connection. The selected-Region collectors cover EC2 instances,
EBS volumes and snapshots, Elastic IPs, NAT gateways, RDS instances, Lambda
functions, load balancers, ECS and EKS clusters, and S3 buckets.

`GET /api/v1/scans` returns the authenticated organization's scan history.
An optional `connection_id` query parameter filters the result.

`GET /api/v1/inventory/resources?region=us-east-1` returns active normalized
resources for the authenticated organization. An optional `connection_id`
query parameter narrows the result. Set `include_inactive=true` to include
previously discovered resources that disappeared from a later successful
service scan.

The Celery worker assumes the verified customer role with its encrypted
External ID, uses only short-lived STS credentials, and records safe error
codes rather than AWS credentials or environment values. A scan is `partial`
when one or more service collectors are denied or unavailable; its
`failed_services` field lists safe service labels.

## Cost management endpoints

`POST /api/v1/costs/connections/{connection_id}/sync` queues a read-only Cost
Explorer synchronization for a verified, organization-scoped connection.
Owners, administrators, and analysts may start a sync. Only one queued or
running cost sync is allowed per connection.

`GET /api/v1/costs/syncs` returns the authenticated organization's cost sync
history. `GET /api/v1/costs/aggregates` returns stored UnblendedCost actuals;
use `granularity=daily|monthly`, `grouping=service_region|usage_type|tag`, and
an optional `connection_id` filter. Tag results exist only when
`CLOUDWISE_COST_ALLOCATION_TAG_KEY` is configured and activated in AWS Cost
Explorer.

`GET /api/v1/costs/forecasts` returns AWS Cost Explorer mean, lower-bound, and
upper-bound forecast values. It accepts `granularity=daily|monthly` and an
optional `connection_id`. Actual and forecast responses always retain their
source currency; callers must not add values with different currencies.

The worker stores safe lifecycle error codes and facet names. It never stores
temporary AWS credentials or exposes raw provider errors through these routes.
