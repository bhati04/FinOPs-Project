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

