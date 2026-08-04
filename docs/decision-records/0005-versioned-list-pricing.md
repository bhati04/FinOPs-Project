# ADR-0005: Versioned recommendation list pricing

## Status

Accepted

## Context

Deterministic eligibility alone cannot quantify a recommendation. Hard-coded
prices would become stale, raw Cost Explorer aggregates cannot always be
attributed to one resource, and a language model is not a trustworthy source
of financial values.

## Decision

Production recommendation evaluation queries the AWS Price List Query API
through the CloudWise platform execution role. Customer roles are not used for
pricing. Regional on-demand price dimensions are normalized into tiered
components and combined only with persisted inventory facts.

Every calculation stores its source, version fingerprint, effective and
retrieval timestamps, currency, quantities, tier rates, and safe availability
state. List-price results are usage-based estimates because discounts, credits,
taxes, free-tier benefits, and partial-month usage are not included.

Local and test environments may use a visibly labelled deterministic mock
catalog. Production configuration rejects that provider. A failed refresh
retains an existing amount as stale; missing or ambiguous inputs produce no
numeric estimate.

## Consequences

- Financial outputs remain deterministic and inspectable.
- The platform execution role requires `pricing:GetProducts` on `*`.
- Pricing availability cannot prevent eligibility findings from being shown.
- A fresh inventory scan is required before gp3 and public IPv4 ownership
  evidence can be priced safely.
- Billed actual and realized savings remain separate future capabilities.
