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

## Milestones 4 through 6 read policy

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
        "ce:GetCostForecast",
        "cloudwatch:GetMetricData",
        "cost-optimization-hub:ListRecommendations",
        "compute-optimizer:GetEC2InstanceRecommendations",
        "compute-optimizer:GetEBSVolumeRecommendations"
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

## Platform pricing permission

Recommendation pricing does not use the customer-managed role. The CloudWise
API execution role queries the global AWS Price List catalog and requires this
separate read permission:

```json
{
  "Effect": "Allow",
  "Action": "pricing:GetProducts",
  "Resource": "*"
}
```

AWS Price List does not support resource-level permissions for `GetProducts`.
No customer resource or billing record is sent to the pricing service.

Cost Optimization Hub must be enabled in the customer account before it
returns findings. Its API is queried through the documented us-east-1
endpoint and is requested with includeAllRecommendations=false, so AWS
returns one deduplicated recommendation per resource. Compute Optimizer is
queried in the selected Region as a fallback. Both integrations are read-only;
CloudWise persists only normalized evidence and never invokes remediation.

Report storage and SES notifications use the CloudWise platform execution
role, not the customer-managed role. No additional customer-account permission
is required for Milestone 7.
