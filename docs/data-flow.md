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
