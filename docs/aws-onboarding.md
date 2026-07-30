# AWS account onboarding

AWS onboarding is implemented as a two-step organization-scoped workflow.

The approved design uses a unique encrypted External ID per connection and a
customer-managed read-only IAM role. CloudWise will accept a role ARN and alias,
call STS AssumeRole followed by GetCallerIdentity, confirm the expected account
ID, and persist the connection only after verification. Long-lived customer AWS
keys are forbidden.

`POST /api/v1/aws-accounts/connections` creates a pending connection and returns
its unique External ID once for trust-policy setup. Owners and Admins can then
call `POST /api/v1/aws-accounts/connections/{id}/verify`. Verification uses
temporary STS credentials and activates the connection only when
`GetCallerIdentity` matches the expected 12-digit account ID.

External IDs are encrypted with
`CLOUDWISE_EXTERNAL_ID_ENCRYPTION_KEY`. The platform role also needs an
identity policy allowing `sts:AssumeRole` only for approved customer-role ARNs.
Long-lived customer AWS keys remain forbidden.
