# Terraform foundation

This root module validates the Terraform, AWS provider, environment, Region,
naming, and tagging contracts. It intentionally provisions no resources during
Milestone 0.

```bash
terraform init -backend=false
terraform fmt -check -recursive
terraform validate
```

Production modules are scheduled for Milestone 8.

