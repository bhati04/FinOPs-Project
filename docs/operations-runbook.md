# Operations runbook

## Local service triage

1. Run `docker compose ps` and identify unhealthy services.
2. Inspect scoped logs with `docker compose logs --tail=200 <service>`.
3. Call `/api/v1/health/live`; failure indicates an API process issue.
4. Call `/api/v1/health/ready`; a `503` identifies PostgreSQL or Redis as down
   without leaking connection data.
5. Validate configuration with `docker compose config --quiet`.

Do not paste environment dumps into tickets.

## Restart

Use `docker compose restart <service>` for a local process restart. Avoid volume
deletion during routine troubleshooting.

Production alert thresholds, queue recovery, failed-job handling, and escalation
contacts will be defined with Milestone 8 observability.

