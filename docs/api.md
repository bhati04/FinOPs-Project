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

## Resource metric endpoints

`POST /api/v1/metrics/connections/{connection_id}/sync` queues a read-only
CloudWatch synchronization for active inventory resources. It accepts a
`region` and a history window of `days=7..30` (default 14). Owners,
administrators, and analysts may start a sync. One queued or running sync is
allowed per connection and Region.

`GET /api/v1/metrics/syncs` returns the organization's metric sync history.
`GET /api/v1/metrics/resources/{inventory_resource_id}` returns up to 30 days
of organization-scoped hourly datapoints for one resource. It accepts `days`
and an optional `metric_name` filter.

CloudWatch queries are batched at 500 metrics per request and paginated. The
worker records only safe batch counts and lifecycle error codes; resource IDs,
provider errors, credentials, and External IDs never enter logs.

## Recommendation endpoints

`POST /api/v1/recommendations/evaluate` runs the current deterministic rule set
against active inventory belonging to the authenticated organization. An
optional `connection_id` limits the evaluation to one organization-scoped AWS
connection. Owners, administrators, and analysts may evaluate.

`GET /api/v1/recommendations` returns organization-scoped findings. Optional
`status`, `severity`, and `connection_id` query parameters filter the result.

`PATCH /api/v1/recommendations/{recommendation_id}/status` changes a finding's
review state and may include a comment. `POST
/api/v1/recommendations/{recommendation_id}/comments` appends a review comment.
Both operations require an owner, administrator, or analyst role.

`GET /api/v1/recommendations/{recommendation_id}/activities` returns the
finding's organization-scoped status and comment history. Recommendation
evaluation reads only persisted customer inventory and never performs
remediation. It may query the global AWS Price List with the CloudWise platform
role; it does not assume or call the customer role during evaluation.

Recommendation responses expose current monthly list cost, estimated monthly
savings, currency, estimate type, pricing status, source and version,
effective/retrieval timestamps, safe unavailable reason, and inspectable
calculation inputs. Callers must treat `stale` and `unavailable` pricing
explicitly and must not combine different currencies.

## AWS recommendation source endpoints

`POST /api/v1/recommendations/connections/{connection_id}/source-syncs` queues
read-only Cost Optimization Hub and Compute Optimizer imports. `GET
/api/v1/recommendations/source-syncs` lists tenant-scoped import history,
including matched, unmatched, deduplicated, completed-source, and failed-source
counts.

## Reports and audit

- `POST /api/v1/reports` queues an executive, cost-detail, or recommendation
  report in CSV or PDF format.
- `GET /api/v1/reports` lists tenant-scoped report history.
- `GET /api/v1/reports/{report_id}/download` downloads a completed,
  unexpired private report.
- `POST /api/v1/reports/schedules` creates a daily, weekly, or monthly
  recurring report.
- `GET /api/v1/reports/schedules` lists recurring definitions.
- `PATCH /api/v1/reports/schedules/{schedule_id}` enables or disables a
  recurring definition.
- `GET /api/v1/reports/audit` lists append-only audit history for owners and
  administrators.
