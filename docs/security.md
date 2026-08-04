# Security

## Foundation controls

- Containers run as non-root users and set `no-new-privileges`.
- PostgreSQL and Redis bind only to loopback in the local Compose stack.
- Runtime configuration is environment-driven and validated at startup.
- API requests receive UUID correlation IDs and baseline response headers.
- Request bodies with an oversized declared content length are rejected.
- Readiness responses expose status only, not exception or configuration data.
- Logs are structured JSON and the design forbids secrets and authorization
  material.
- Credentialed CORS uses an explicit allowlist.
- CI includes secret, dependency, container, and IaC scanning.

## AI advisory controls

The optional AI advisor is disabled by default and has no HTTP route or
background task. Its Bedrock adapter is designed for explicit, on-demand
explanations only:

- A strict schema allowlists the recommendation and resource fields sent to the
  model. Credentials, account IDs, ARNs, free-form tags, and authorization data
  have no input fields.
- Resource and evidence strings are marked as untrusted data in a versioned
  prompt to reduce prompt-injection risk.
- Bedrock receives no `toolConfig`, AWS action, remediation function, shell
  command, or infrastructure deployment capability.
- Model output is parsed as strict JSON and rejected if it references evidence
  outside the supplied context.
- The model cannot populate financial fields; rule-engine calculations are
  carried through the service independently.
- Prompts and responses must not be logged. Future persisted results must be
  tenant-scoped, access controlled, auditable, and covered by retention rules.
- Provider errors exposed by a future route must be mapped to generic client
  messages without leaking model, request, configuration, or AWS details.

On EC2, use the instance role and a least-privilege `bedrock:InvokeModel`
permission scoped to the selected model or inference profile. Do not configure
static AWS access keys in `.env`.

## Accepted dependency advisory

React Router 7.18.2 has an upstream high-severity advisory
`GHSA-qwww-vcr4-c8h2` affecting React Server Components action processing. The
CloudWise frontend is a client-rendered browser application and does not enable
RSC mode or server actions, so the vulnerable execution path is absent.
`audit-ci` allowlists only this advisory and continues to fail on any other
high-severity dependency finding. Remove the exception as soon as a patched
React Router release is available.

## Required future controls

Milestone 1 must add Argon2id password hashing, short-lived access tokens,
rotating revocable refresh tokens, CSRF protections appropriate to token
transport, rate limiting, organization RBAC, and tenant isolation at route and
service boundaries.

Milestone 2 must encrypt External IDs using an application key backed by Secrets
Manager or KMS in production. Customer AWS access must use STS AssumeRole only.

Any future AI endpoint must add organization authorization, request throttling, generation
budgets, tenant-scoped caching, audit records, and retention controls before an
AI suggestion endpoint is exposed.

Milestone 7 mutation auditing is implemented by authenticated request
middleware and protected by a PostgreSQL trigger that rejects audit-event
updates and deletes. Audit context is deliberately bounded to safe route and
status metadata. Private report downloads recheck organization ownership and
expiration before reading local or S3 storage.

## Reporting

Do not include real secrets in issues or logs. Rotate an exposed value first,
then remove it from history using the repository owner's approved process.
