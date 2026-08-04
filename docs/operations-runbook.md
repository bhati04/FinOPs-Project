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

## Reports and scheduler

Monitor the worker queue for `cloudwise.reports.generate_report` and ensure
exactly one Celery beat scheduler is active. Failed jobs retain a safe
`error_code`; report contents and recipients must not appear in logs. The
hourly expiration task should transition completed expired reports to
`expired` after deleting their private object.

## Queued inventory scans

The worker disposes its async database pool after each synchronous Celery task
entrypoint so connections are never reused by a later task's event loop. An
unexpected inventory task failure records `INVENTORY_WORKER_FAILED` instead of
leaving the scan indefinitely queued. Confirm that
`cloudwise.scans.run_inventory_scan` is registered before redispatching a task
that was lost during an earlier worker outage.
