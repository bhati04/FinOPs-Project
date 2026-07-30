# Data flow

## Milestone 0

1. The browser requests the static React application from nginx.
2. TanStack Query calls `GET /api/v1/health/ready`.
3. FastAPI attaches a correlation ID and performs bounded PostgreSQL and Redis
   probes.
4. The API returns only `up` or `down` component states.
5. The UI validates the response with Zod before rendering it.

Connection strings and underlying exception messages never leave the backend.

## Future AWS scan boundary

Future scans will resolve the organization and account connection, acquire a
per-account lock, request an STS session, call AWS through a provider interface,
normalize and validate results, and persist organization-scoped records. Raw
credentials and session tokens must never enter logs or storage.

