output "name_prefix" {
  description = "Validated resource-name prefix for future modules."
  value       = local.name_prefix
}

output "required_tags" {
  description = "Mandatory tags inherited by future AWS resources."
  value       = local.required_tags
}

output "vpc_id" {
  description = "CloudWise VPC identifier."
  value       = aws_vpc.main.id
}

output "public_subnet_ids" {
  description = "Public subnet identifiers for internet-facing load balancers."
  value       = values(aws_subnet.public)[*].id
}

output "private_subnet_ids" {
  description = "Private subnet identifiers for application tasks."
  value       = values(aws_subnet.private)[*].id
}

output "data_subnet_ids" {
  description = "Isolated subnet identifiers for managed data stores."
  value       = values(aws_subnet.data)[*].id
}

output "platform_kms_key_arn" {
  description = "KMS key used by CloudWise platform storage."
  value       = aws_kms_key.platform.arn
}

output "report_bucket_name" {
  description = "Private S3 bucket used for generated reports."
  value       = aws_s3_bucket.reports.id
}

output "ecr_repository_urls" {
  description = "Immutable container repositories keyed by service name."
  value       = { for name, repository in aws_ecr_repository.service : name => repository.repository_url }
}

output "ecs_cluster_name" {
  description = "ECS cluster used by deployment automation."
  value       = aws_ecs_cluster.main.name
}

output "api_task_definition_arn" {
  description = "API task definition used for guarded migration tasks."
  value       = aws_ecs_task_definition.backend["api"].arn
}

output "task_definition_arns" {
  description = "Task definitions keyed by deployable ECS service."
  value = merge(
    { for name, definition in aws_ecs_task_definition.backend : name => definition.arn },
    { frontend = aws_ecs_task_definition.frontend.arn }
  )
}

output "app_security_group_id" {
  description = "Security group used by ECS tasks."
  value       = aws_security_group.app.id
}

output "application_url" {
  description = "Public CloudWise URL."
  value       = "https://${var.domain_name}"
}
