# Project progress

This file is the durable restart point for CloudWise. Update it at the end of
each work session so the next session begins with a verified status, not an
assumption.

## Current snapshot

| Item | Status |
| --- | --- |
| Last reviewed | 2026-08-31 |
| Last repository commit | `2bd165e` on 2026-08-04 17:35 IST |
| Current phase | Milestone 8 - production hardening |
| Next build session | After local Docker/Python tooling is restored |
| Current blocker | Baseline cannot be fully rerun locally because Docker/Python tooling is unavailable |

The README reports Milestones 0-3 and 5-7 as implemented, Milestone 4 as in
progress, and Milestone 8 as in progress. The implementation supports that the
repository has advanced beyond the foundation: it contains 10 Alembic
migrations, 29 backend/frontend test files, and API/UI modules for identity,
AWS accounts, scans, costs, metrics, recommendations, and reports.

The restart audit found two issues that must be handled before adding more
product scope:

1. The missing root CI pipeline was added on 2026-08-31 and awaits its first
   hosted GitHub Actions run.
2. Milestone 8 was explicitly approved on 2026-08-31 and `AGENTS.md` now records
   that authorization.

Existing later-milestone code must be preserved. New work may now proceed within
the production-hardening scope defined for Milestone 8.

## Milestone status

| Milestone | Repository-reported state | Restart assessment |
| --- | --- | --- |
| 0 - foundation, runtime, health, CI, docs | Implemented | CI added; baseline checks still need a complete clean run |
| 1 - identity and organizations | Implemented | Present; no new work currently authorized |
| 2 - AWS account onboarding | Implemented | Present; no new work currently authorized |
| 3 - inventory persistence and orchestration | Implemented | Present; no new work currently authorized |
| 4 - broader AWS inventory | In progress | Paused pending explicit approval; one Region per scan remains a known limit |
| 5 - costs and metrics | Implemented | Present; no new work currently authorized |
| 6 - recommendations | Implemented | Present; no new work currently authorized |
| 7 - reports, notifications, audit | Implemented | Present; no new work currently authorized |
| 8 - production hardening and deployment | In progress | Approved 2026-08-31; infrastructure foundation is the first slice |

## Next build checklist

Work in this order in the next session:

- [ ] Restore local Docker/Python tooling and confirm the baseline validation
  results recorded below are reproducible.
- [x] Add a root GitHub Actions workflow for Compose validation, backend
  formatting/lint/type/tests, and frontend formatting/lint/type/tests/build.
- [x] Keep CI aligned with the commands in `Makefile` and `docs/testing.md`.
- [ ] Run all checks locally and record the exact result in this file.
- [ ] Update the README Milestone 0 status only after CI is present and green.
- [x] Approve Milestone 8 and update `AGENTS.md` before implementing it.

Definition of done for the session: the root CI workflow exists, its local
equivalent passes, documentation agrees with reality, and the next authorized
milestone is recorded.

## Validation log

| Date | Baseline | Result | Notes |
| --- | --- | --- | --- |
| 2026-08-21 | Restart audit | Passed | Structure, routes, migrations, tests, milestone docs, and Git metadata reviewed |
| 2026-08-21 | `docker compose config --quiet` | Pending | Run during restart preparation |
| 2026-08-21 | Backend quality and tests | Pending | Run during restart preparation |
| 2026-08-21 | Frontend quality, tests, and build | Pending | Run during restart preparation |
| 2026-08-31 | `docker compose config --quiet` | Passed with warning | Compose config is valid; Docker could not read the user-level config file in the restricted environment |
| 2026-08-31 | Backend quality and tests | Blocked | Checked-in `.venv` points to missing `D:\\PROGRAMING\\python.exe`; Docker Desktop daemon is not running |
| 2026-08-31 | Frontend format/lint/type | Passed | Prettier, ESLint, and both TypeScript configurations completed successfully |
| 2026-08-31 | Frontend tests/build | Incomplete | Seven test files passed before the run stalled; retry hit `EPERM` writing `node_modules/.vite-temp`, so build was not reached |
| 2026-08-31 | Milestone 8 infrastructure slice 1 | Implemented, awaiting CI | Multi-AZ VPC, isolated data subnets, NAT, KMS, S3 reports, ECR, and CloudWatch logs added; Terraform is not installed locally |
| 2026-08-31 | Milestone 8 runtime and CD slice | Implemented, awaiting CI | Future ECS/RDS infrastructure remains defined; active CD now targets the existing EC2 Compose stack through SSM with ECR images, guarded migration, smoke tests, and image rollback |
| 2026-08-31 | Terraform format/validation | Partial | Terraform 1.9.8 formatting passed; provider-backed validation was blocked by interrupted HashiCorp provider downloads, so hosted CI must validate |

## Session update template

Copy this block to the top of a new dated entry after each build session:

```text
Date:
Goal:
Completed:
Checks run and results:
Decisions made:
Blockers:
Exact next task:
```
