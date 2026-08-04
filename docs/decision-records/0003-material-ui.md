# ADR-0003: Material UI component system

- Status: Accepted
- Date: 2026-07-29

## Context

The dashboard needs accessible, consistent, data-dense controls without
maintaining a custom component library.

## Decision

Use Material UI for application components and theming. Recharts remains the
charting library. The platform defaults to a calm neutral light palette,
provides a persistent accessible light/dark switch, and uses restrained
green/ochre chart accents instead of a blue-dominant dashboard treatment.

## Consequences

Complex screens can be built quickly and consistently. Bundle size is larger
than a minimal custom system, so route-level loading and bundle monitoring will
be required as the product grows.
