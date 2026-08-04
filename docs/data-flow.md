# Data flow

## Milestone 0

1. The browser requests the static React application from nginx.
2. TanStack Query calls `GET /api/v1/health/ready`.
3. FastAPI attaches a correlation ID and performs bounded PostgreSQL and Redis
   probes.
4. The API returns only `up` or `down` component states.
5. The UI validates the response with Zod before rendering it.

Connection strings and underlying exception messages never leave the backend.

## AWS scan boundary

1. An owner, administrator, or analyst requests a scan for a verified
   organization-scoped connection.
2. FastAPI persists a queued scan and sends only its UUID to Celery.
3. The worker acquires a per-connection Redis lock and decrypts the External ID
   in memory.
4. STS returns short-lived role credentials. Independent providers paginate
   supported AWS services in the selected Region using adaptive retries.
5. The worker normalizes and upserts tenant-scoped resources, marks resources
   absent from a successful collector as inactive, and completes or partially
   completes the scan.

Raw credentials, session tokens, External IDs, and environment values never
enter logs or persistent scan records.

## Cost Explorer boundary

1. An owner, administrator, or analyst requests a cost sync for a verified
   organization-scoped connection.
2. FastAPI persists a queued sync and sends only its UUID to Celery.
3. The worker atomically claims the sync, decrypts the connection's External ID
   in memory, and assumes the customer role with short-lived STS credentials.
4. The Cost Explorer provider paginates daily and monthly UnblendedCost views
   and requests daily and monthly forecasts.
5. The worker idempotently upserts tenant-scoped aggregates and forecast bounds,
   then marks the sync completed, partial, or failed with safe facet labels and
   error codes.

Different currencies remain separate. AWS credentials, External IDs, raw AWS
errors, and environment values never enter logs or cost records.

## CloudWatch metric boundary

1. An authorized organization member requests metrics for a verified
   connection, Region, and bounded 7-to-30-day window.
2. FastAPI persists a queued metric sync and sends only its UUID to Celery.
3. The worker claims the sync, loads active tenant-scoped inventory resources,
   decrypts the External ID in memory, and assumes the customer role.
4. The provider maps supported resource types to explicit CloudWatch namespaces
   and dimensions, then paginates `GetMetricData` in batches of at most 500
   queries.
5. Hourly datapoints are idempotently upserted by resource, metric, statistic,
   and timestamp. Safe batch failures produce a partial or failed sync.

Raw AWS resource identifiers are used only to construct the outbound CloudWatch
request. They are not written to logs or metric API responses.

## Deterministic recommendation boundary

1. An owner, administrator, or analyst starts an evaluation for all active
   organization inventory or one organization-scoped connection.
2. FastAPI loads persisted active inventory and applies the versioned rule set
   in process; no customer AWS API or language model is called.
3. Eligible findings are idempotently created or updated with their evidence,
   confidence, rule version, risks, and verification steps. The configured
   pricing provider retrieves a regional AWS list-price quote using the
   CloudWise platform role; local development uses a labelled mock catalog.
4. Complete prices are calculated from persisted resource configuration and
   saved with source, version, timestamps, tier inputs, currency, and an
   available/stale/unavailable state. Findings that no longer qualify are
   resolved.
5. Authorized reviewers acknowledge, dismiss, resolve, or reopen findings and
   add comments. Every change creates an append-only activity record.
6. The authenticated dashboard renders rule and pricing provenance. Missing or
   ambiguous pricing is displayed as pending, never inferred as savings.

## AWS-native recommendation boundary

1. An authorized member queues a source sync for a verified connection.
2. The worker assumes the customer role, reads the global Cost Optimization
   Hub endpoint and the selected Region's EC2/EBS Compute Optimizer APIs, and
   records partial failures without logging provider payloads.
3. Normalized findings are matched only to active inventory in the same
   organization and connection.
4. CloudWise merges observations by resource and canonical action, preserving
   every contributing source while showing a single workflow item.

## Report and audit boundary

1. An authorized member queues an on-demand report or creates a database-backed
   schedule. The API never generates report bytes inline.
2. Celery renders CSV or PDF from tenant-scoped persisted facts and writes the
   object to private local or S3 storage with a checksum and expiration.
3. Scheduled reports optionally send a non-attached SES notice and persist each
   delivery outcome. A separate task expires private objects.
4. Authenticated mutation middleware appends a bounded audit event after
   authorization. PostgreSQL rejects audit-event updates and deletes.
