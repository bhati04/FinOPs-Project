# ADR-0002: Docker-first local environment

- Status: Accepted
- Date: 2026-07-29

## Context

Developers need consistent Python, PostgreSQL, Redis, worker, and Node runtimes
across operating systems.

## Decision

Docker Compose is the canonical local workflow. Native workflows remain
documented for faster iteration.

## Consequences

Onboarding needs only Docker, and CI closely matches local checks. Initial image
builds are slower and file-watching behavior can vary across host platforms.

