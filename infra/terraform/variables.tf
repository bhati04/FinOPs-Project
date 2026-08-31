variable "aws_region" {
  description = "AWS Region for platform infrastructure."
  type        = string
  default     = "us-east-1"

  validation {
    condition     = can(regex("^[a-z]{2}(-[a-z]+)+-[0-9]$", var.aws_region))
    error_message = "aws_region must be a valid AWS Region identifier."
  }
}

variable "environment" {
  description = "CloudWise deployment environment."
  type        = string

  validation {
    condition     = contains(["development", "staging", "production"], var.environment)
    error_message = "environment must be development, staging, or production."
  }
}

variable "owner" {
  description = "Team responsible for the platform resources."
  type        = string
  default     = "cloudwise-platform"
}

variable "vpc_cidr" {
  description = "IPv4 CIDR for the CloudWise VPC."
  type        = string
  default     = "10.42.0.0/16"

  validation {
    condition     = can(cidrnetmask(var.vpc_cidr))
    error_message = "vpc_cidr must be a valid IPv4 CIDR."
  }
}

variable "availability_zone_count" {
  description = "Number of Availability Zones used by the platform."
  type        = number
  default     = 2

  validation {
    condition     = var.availability_zone_count >= 2 && var.availability_zone_count <= 3
    error_message = "availability_zone_count must be between 2 and 3."
  }
}

variable "log_retention_days" {
  description = "CloudWatch application log retention."
  type        = number
  default     = 30

  validation {
    condition     = contains([14, 30, 60, 90, 120, 150, 180, 365, 400, 545, 731, 1096, 1827, 2192, 2557, 2922, 3288, 3653], var.log_retention_days)
    error_message = "log_retention_days must be a CloudWatch-supported retention value of at least 14 days."
  }
}

variable "domain_name" {
  description = "Public DNS name for the CloudWise application."
  type        = string
}

variable "route53_zone_id" {
  description = "Route 53 hosted-zone identifier containing domain_name."
  type        = string
}

variable "backend_image_tag" {
  description = "Immutable backend image tag, normally the Git commit SHA."
  type        = string
}

variable "frontend_image_tag" {
  description = "Immutable frontend image tag, normally the Git commit SHA."
  type        = string
}

variable "database_instance_class" {
  description = "RDS PostgreSQL instance class."
  type        = string
  default     = "db.t4g.small"
}

variable "redis_node_type" {
  description = "ElastiCache Redis node type."
  type        = string
  default     = "cache.t4g.small"
}

variable "api_desired_count" {
  description = "Number of API tasks."
  type        = number
  default     = 2
}

variable "frontend_desired_count" {
  description = "Number of frontend tasks."
  type        = number
  default     = 2
}

variable "database_password" {
  description = "RDS application password supplied through the protected deployment environment."
  type        = string
  sensitive   = true

  validation {
    condition     = length(var.database_password) >= 16 && length(var.database_password) <= 128 && can(regex("^[A-Za-z0-9_-]+$", var.database_password))
    error_message = "database_password must be 16-128 URL-safe characters."
  }
}

variable "redis_auth_token" {
  description = "ElastiCache authentication token supplied through the protected deployment environment."
  type        = string
  sensitive   = true

  validation {
    condition     = length(var.redis_auth_token) >= 16 && length(var.redis_auth_token) <= 128 && can(regex("^[A-Za-z0-9_-]+$", var.redis_auth_token))
    error_message = "redis_auth_token must be 16-128 URL-safe characters."
  }
}

variable "auth_secret_key" {
  description = "Application token-signing key supplied through the protected deployment environment."
  type        = string
  sensitive   = true

  validation {
    condition     = length(var.auth_secret_key) >= 64
    error_message = "auth_secret_key must contain at least 64 characters."
  }
}

variable "external_id_encryption_key" {
  description = "Fernet key used to encrypt customer External IDs."
  type        = string
  sensitive   = true

  validation {
    condition     = can(regex("^[A-Za-z0-9_-]{43}=$", var.external_id_encryption_key))
    error_message = "external_id_encryption_key must be a URL-safe base64-encoded 32-byte Fernet key."
  }
}
