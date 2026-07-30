# ADR-0004: On-demand, advisory-only language model

## Status

Accepted

## Context

CloudWise can use a language model to make deterministic FinOps
recommendations easier to understand. Letting a model calculate savings or
operate customer resources would weaken explainability, auditability, safety,
and cost control. Automatic generation would also create provider spend when a
user may never read the explanation.

Identity, tenant-scoped recommendation persistence, and the recommendation
engine are not implemented yet.

## Decision

Add a disabled-by-default provider and application-service foundation, but no
route, worker task, scheduled job, UI action, or database table.

In the future, an authenticated user may click **Generate AI suggestion** for
one authorized recommendation. CloudWise rules remain the source of eligibility,
evidence, cost, and savings calculations. Amazon Bedrock produces only a
strictly validated qualitative explanation.

The Bedrock request includes no tools or remediation functions. The application
rejects invented evidence references and returns authoritative financial values
outside the model-owned response.

## Consequences

- No model cost is incurred from scans, schedulers, page loads, or merely viewing
  a recommendation.
- Milestone 6 must add authorization, throttling, tenant-scoped caching, budgets,
  audit history, and retention before exposing the feature.
- Bedrock model access and least-privilege IAM configuration are deployment
  responsibilities.
- A provider failure cannot alter the underlying recommendation or any AWS
  resource.
