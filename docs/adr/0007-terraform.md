# ADR 0007: Migration from CloudFormation to Terraform

## Context
Previously, infrastructure components (Cognito Auth, Reports Bucket, Bedrock Lambda IAM) were managed via CloudFormation YAML templates (`infra/auth.yml`, `infra/reports.yml`, `infra/ai.yml`).

## Decision
We migrated infrastructure management to **Terraform** using **HCP Terraform (Terraform Cloud)** for remote state locking and execution.

## Consequences
* **Why Terraform:** Provides multi-provider support, clear `terraform plan` previews, and explicit environment state separation.
* **Workflow:** Infrastructure changes are submitted via PRs, validated via plan checks, and automatically applied upon merge to `main` using dynamic OIDC credentials.