# ADR-0001: Modular monolith and separate worker

- Status: Accepted
- Date: 2026-07-29

## Context

CloudWise needs strong domain boundaries but does not yet need the operational
cost of independently deployed microservices.

## Decision

Use one FastAPI modular monolith and one Celery worker built from the same
backend package. Domain code remains organized by business capability.

## Consequences

Deployment and transactions remain simple. Modules must avoid reaching into
other domains' persistence internals. A high-load domain can later be extracted
behind its existing service contract.

