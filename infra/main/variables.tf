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

variable "alert_email" {
  description = "Where budget and alarm notifications go. Set in terraform.tfvars (git-ignored)."
  type        = string

  validation {
    condition     = can(regex("^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$", var.alert_email))
    error_message = "alert_email must be an email address."
  }
}

variable "access_code_sha256" {
  description = "SHA-256 hex of the shared access code (ADR 0004): python -m olist_nlsql.api hash-code. Only the hash reaches AWS."
  type        = string
  sensitive   = true

  validation {
    condition     = can(regex("^[0-9a-f]{64}$", var.access_code_sha256))
    error_message = "access_code_sha256 must be 64 lowercase hex characters."
  }
}

# Database (ADR 0001)

variable "aurora_engine_version" {
  description = "Aurora PostgreSQL version. 16.3+ supports pausing at 0 ACU."
  type        = string
  default     = "16.15"
}

variable "aurora_max_acu" {
  description = "Upper bound on Aurora Serverless v2 capacity (cost ceiling for the database)."
  type        = number
  default     = 2
}

variable "seconds_until_auto_pause" {
  description = "Idle time before the cluster pauses at 0 ACU. 30 min keeps a demo session warm."
  type        = number
  default     = 1800

  validation {
    condition     = var.seconds_until_auto_pause >= 300 && var.seconds_until_auto_pause <= 86400
    error_message = "AWS allows 300 to 86400 seconds."
  }
}

variable "database_name" {
  type    = string
  default = "olist"
}

# Lambda and API

variable "lambda_zip" {
  description = "Path to the package from backend/scripts/build_lambda.py."
  type        = string
  default     = "../../backend/build/lambda.zip"
}

variable "bedrock_model_id" {
  description = "Bedrock inference profile (ADR 0019). Changing it also changes the IAM policy."
  type        = string
  default     = "us.anthropic.claude-sonnet-4-6"
}

variable "bedrock_destination_regions" {
  description = "Regions the US geo inference profile routes to from us-east-1 (ADR 0019)."
  type        = list(string)
  default     = ["us-east-1", "us-east-2", "us-west-2"]
}

variable "lambda_memory_mb" {
  type    = number
  default = 512
}

variable "reserved_concurrency" {
  description = "Reserved concurrency (ADR 0004). Null until the account limit is above 10 (amendment 2026-10-13)."
  type        = number
  default     = null
}

variable "cors_allow_origins" {
  description = "Browser origins allowed to call the API: the local dev server now, CloudFront in Phase 8."
  type        = list(string)
  default     = ["http://localhost:5173"]
}

variable "throttle_rate_per_second" {
  description = "Steady-state requests per second for the whole API (ADR 0004: start low)."
  type        = number
  default     = 2
}

variable "throttle_burst" {
  type    = number
  default = 5
}

variable "query_throttle_rate_per_second" {
  description = "/query is the expensive route (Bedrock + database): tighter than /status."
  type        = number
  default     = 1
}

variable "query_throttle_burst" {
  type    = number
  default = 3
}

variable "log_retention_days" {
  type    = number
  default = 14
}
