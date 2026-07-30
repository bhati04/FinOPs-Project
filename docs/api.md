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
