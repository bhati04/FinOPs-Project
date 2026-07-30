# AWS account onboarding

AWS onboarding is scheduled for Milestone 2 and is not implemented.

The approved design uses a unique encrypted External ID per connection and a
customer-managed read-only IAM role. CloudWise will accept a role ARN and alias,
call STS AssumeRole followed by GetCallerIdentity, confirm the expected account
ID, and persist the connection only after verification. Long-lived customer AWS
keys are forbidden.

Onboarding templates, trust-policy details, least-privilege permissions, failure
handling, and audit events will be documented with the implementation.

