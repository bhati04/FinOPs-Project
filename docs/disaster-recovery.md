# Disaster recovery

Milestone 0 contains no production data and has no production recovery claim.

The production design will require encrypted automated RDS backups, point-in-time
recovery, tested snapshots before risky migrations, infrastructure recreation
through Terraform, immutable image retention, and documented RPO/RTO objectives.
Redis will not be the system of record.

Recovery exercises must verify tenant data, audit records, recommendation
history, and encryption-key access before traffic is restored.

