variable "aws_region" {
  description = "AWS region for all resources (ADR 0003)."
  type        = string
  default     = "us-east-1"
}

variable "project" {
  description = "Project name, used in resource names and tags."
  type        = string
  default     = "olist-nlsql"
}

variable "environment" {
  description = "Deployment environment. Only dev exists for the MVP (ADR 0009)."
  type        = string
  default     = "dev"

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{1,15}$", var.environment))
    error_message = "environment must be 2-16 lowercase alphanumeric/hyphen characters."
  }
}

variable "monthly_budget_usd" {
  description = "AWS Budget alert threshold in USD. An alert, not a spending cap (ADR 0004)."
  type        = number
  default     = 20
}
