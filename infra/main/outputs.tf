output "api_url" {
  description = "Base URL of the HTTP API (GET /status, POST /query)."
  value       = aws_apigatewayv2_stage.default.invoke_url
}

output "function_name" {
  value = aws_lambda_function.api.function_name
}

output "dashboard" {
  value = "https://${var.aws_region}.console.aws.amazon.com/cloudwatch/home?region=${var.aws_region}#dashboards/dashboard/${aws_cloudwatch_dashboard.main.dashboard_name}"
}

# Settings for `python -m olist_nlsql.dbsetup aws-build` and the live tests. Paste into
# .env (git-ignored): they contain the account ID.
output "env" {
  description = "NLSQL_* lines for .env (aws-build, live Data API tests)."
  value       = <<-EOT
    NLSQL_DB_CLUSTER_ARN=${aws_rds_cluster.main.arn}
    NLSQL_DB_MASTER_SECRET_ARN=${aws_rds_cluster.main.master_user_secret[0].secret_arn}
    NLSQL_DB_OWNER_SECRET_ARN=${aws_secretsmanager_secret.owner.arn}
    NLSQL_DB_SECRET_ARN=${aws_secretsmanager_secret.reader.arn}
    NLSQL_DATA_BUCKET=${aws_s3_bucket.data.bucket}
    NLSQL_DB_NAME=${var.database_name}
  EOT
}
