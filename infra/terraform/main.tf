locals {
  name_prefix = "cloudwise-${var.environment}"

  required_tags = {
    Application = "cloudwise"
    Environment = var.environment
    ManagedBy   = "terraform"
    Owner       = var.owner
  }
}

# Milestone 0 intentionally provisions no resources. Network, ECS, RDS, Redis,
# ALB, DNS, certificate, observability, budget, and optional WAF modules are
# introduced and tested during Milestone 8 production hardening.

