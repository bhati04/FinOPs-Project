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

