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
4. STS returns short-lived role credentials, and the provider paginates EC2 in
   the selected Region.
5. The worker normalizes and upserts tenant-scoped resources, removes stale EC2
   records for that connection and Region, and completes the scan.

Raw credentials, session tokens, External IDs, and environment values never
enter logs or persistent scan records.
