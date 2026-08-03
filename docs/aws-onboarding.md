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

## Milestones 4 and 5 read policy

The customer-managed role needs only read actions used by the selected-Region
inventory scan and Cost Explorer synchronization:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "CloudWiseInventoryRead",
      "Effect": "Allow",
      "Action": [
        "ec2:DescribeAddresses",
        "ec2:DescribeInstances",
        "ec2:DescribeNatGateways",
        "ec2:DescribeSnapshots",
        "ec2:DescribeVolumes",
        "rds:DescribeDBInstances",
        "lambda:ListFunctions",
        "elasticloadbalancing:DescribeLoadBalancers",
        "ecs:ListClusters",
        "ecs:DescribeClusters",
        "ecs:ListTagsForResource",
        "eks:ListClusters",
        "eks:DescribeCluster",
        "s3:ListAllMyBuckets",
        "s3:GetBucketLocation",
        "ce:GetCostAndUsage",
        "ce:GetCostForecast"
      ],
      "Resource": "*"
    }
  ]
}
```

CloudWise runs collectors independently. Missing permissions produce a
`partial` scan and a safe list of affected service names; successfully queried
services are still persisted. No action in this policy modifies a customer
resource.
