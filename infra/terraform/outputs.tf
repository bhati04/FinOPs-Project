output "name_prefix" {
  description = "Validated resource-name prefix for future modules."
  value       = local.name_prefix
}

output "required_tags" {
  description = "Mandatory tags inherited by future AWS resources."
  value       = local.required_tags
}

