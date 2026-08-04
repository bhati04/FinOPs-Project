# ADR-0006: Canonical AWS findings and private scheduled reports

Status: accepted

## Context

AWS Cost Optimization Hub and Compute Optimizer can overlap with each other and
with CloudWise rules. Reports also contain tenant cost data that must not become
public through email links or object URLs. Milestones 6 and 7 need stable
workflow identities, source transparency, retention, and auditability.

## Decision

CloudWise uses organization, inventory resource, and canonical action as the
stable recommendation identity. Cost Optimization Hub is imported first with
AWS deduplication enabled; regional Compute Optimizer is a fallback. Source
observations enrich one finding and do not authorize remediation.

Reports are generated asynchronously, stored privately, downloaded only after
tenant authorization, and expired by a worker task. Scheduled email contains
no attachment. Authenticated mutations create bounded audit records, and a
database trigger makes those records append-only.

## Consequences

AWS findings without matching active inventory are visible only as unmatched
counts until inventory support exists. Cost Optimization Hub's short-lived
recommendation ID is provenance rather than identity. Production requires
private S3 report storage and exactly one scheduler. Email recipients must
authenticate separately to retrieve report contents.
