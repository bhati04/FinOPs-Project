# Terraform foundation

This root module contains the first approved Milestone 8 production foundation.
It provisions a multi-AZ VPC with public, private application, and isolated data
subnets; one NAT gateway per Availability Zone; a rotating KMS key; a private,
versioned report bucket; immutable ECR repositories; and retained CloudWatch log
groups.

```bash
terraform init -backend=false
terraform fmt -check -recursive
terraform validate
```

Create an environment-specific variable file outside source control, review the
cost impact of the NAT gateways, and save plans before applying:

```bash
terraform plan -var="environment=staging" -out=staging.tfplan
terraform apply staging.tfplan
```

Terraform state must use an encrypted remote backend with locking before a
shared environment is created. The runtime slice now adds ECS Fargate services,
RDS PostgreSQL, encrypted Redis, ALB/ACM/Route 53 ingress, runtime secrets, and
least-privilege task roles. Alarms, autoscaling, WAF, restore exercises, and load
testing remain subsequent Milestone 8 work.
