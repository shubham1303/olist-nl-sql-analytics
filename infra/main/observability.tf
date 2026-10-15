# Alarms, dashboard and the email topic they notify (plan §3). The application metrics
# come from the function's EMF log lines (namespace OlistNlSql, see
# backend/src/olist_nlsql/api/metrics.py). The subscription needs one confirmation
# click in the email AWS sends.

locals {
  app_namespace = "OlistNlSql"
  function_name = aws_lambda_function.api.function_name
}

resource "aws_sns_topic" "alerts" {
  name = "${local.name}-alerts"
}

resource "aws_sns_topic_subscription" "email" {
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email
}

resource "aws_cloudwatch_metric_alarm" "function_errors" {
  alarm_name          = "${local.name}-function-errors"
  alarm_description   = "Unhandled errors in the API function (the handler catches everything, so any is a bug)."
  namespace           = "AWS/Lambda"
  metric_name         = "Errors"
  dimensions          = { FunctionName = local.function_name }
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 0
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.alerts.arn]
  ok_actions          = [aws_sns_topic.alerts.arn]
}

resource "aws_cloudwatch_metric_alarm" "function_throttles" {
  alarm_name          = "${local.name}-function-throttles"
  alarm_description   = "The function was throttled: the account-wide concurrency cap was reached (ADR 0004 amendment)."
  namespace           = "AWS/Lambda"
  metric_name         = "Throttles"
  dimensions          = { FunctionName = local.function_name }
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 0
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.alerts.arn]
}

resource "aws_cloudwatch_metric_alarm" "api_5xx" {
  alarm_name          = "${local.name}-api-5xx"
  alarm_description   = "3+ server errors in 5 minutes (includes 503 while the database resumes, so a single cold start doesn't page)."
  namespace           = "AWS/ApiGateway"
  metric_name         = "5xx"
  dimensions          = { ApiId = aws_apigatewayv2_api.main.id, Stage = "$default" }
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 3
  comparison_operator = "GreaterThanOrEqualToThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.alerts.arn]
}

resource "aws_cloudwatch_metric_alarm" "model_failures" {
  alarm_name          = "${local.name}-model-failures"
  alarm_description   = "3+ questions in 15 minutes where Bedrock failed or its reply could not be parsed."
  namespace           = local.app_namespace
  metric_name         = "Requests"
  dimensions          = { Route = "query", Outcome = "generation_failed" }
  statistic           = "Sum"
  period              = 900
  evaluation_periods  = 1
  threshold           = 3
  comparison_operator = "GreaterThanOrEqualToThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.alerts.arn]
}

resource "aws_cloudwatch_metric_alarm" "slow_queries" {
  alarm_name          = "${local.name}-slow-queries"
  alarm_description   = "p95 /query latency over 20 s for 15 minutes: close to the 29 s function timeout."
  namespace           = local.app_namespace
  metric_name         = "LatencyMs"
  dimensions          = { Route = "query" }
  extended_statistic  = "p95"
  period              = 900
  evaluation_periods  = 1
  threshold           = 20000
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.alerts.arn]
}

resource "aws_cloudwatch_dashboard" "main" {
  dashboard_name = local.name
  dashboard_body = jsonencode({
    widgets = [
      {
        type = "metric", x = 0, y = 0, width = 12, height = 6
        properties = {
          title  = "Requests by route"
          region = var.aws_region
          stat   = "Sum"
          period = 300
          metrics = [
            [local.app_namespace, "Requests", "Route", "query"],
            [local.app_namespace, "Requests", "Route", "status"],
          ]
        }
      },
      {
        type = "metric", x = 12, y = 0, width = 12, height = 6
        properties = {
          title  = "/query latency (ms)"
          region = var.aws_region
          period = 300
          metrics = [
            [local.app_namespace, "LatencyMs", "Route", "query", { stat = "p50", label = "p50" }],
            [local.app_namespace, "LatencyMs", "Route", "query", { stat = "p95", label = "p95" }],
            [local.app_namespace, "ModelMs", "Route", "query", { stat = "p50", label = "model p50" }],
          ]
        }
      },
      {
        type = "metric", x = 0, y = 6, width = 12, height = 6
        properties = {
          title  = "/query outcomes"
          region = var.aws_region
          stat   = "Sum"
          period = 300
          metrics = [
            for outcome in ["answered", "unanswerable", "rejected", "execution_failed", "generation_failed", "invalid_question", "database_resuming"] :
            [local.app_namespace, "Requests", "Route", "query", "Outcome", outcome]
          ]
        }
      },
      {
        type = "metric", x = 12, y = 6, width = 12, height = 6
        properties = {
          title  = "Function errors, throttles and API 5xx"
          region = var.aws_region
          stat   = "Sum"
          period = 300
          metrics = [
            ["AWS/Lambda", "Errors", "FunctionName", local.function_name],
            ["AWS/Lambda", "Throttles", "FunctionName", local.function_name],
            ["AWS/ApiGateway", "5xx", "ApiId", aws_apigatewayv2_api.main.id, "Stage", "$default"],
            ["AWS/ApiGateway", "4xx", "ApiId", aws_apigatewayv2_api.main.id, "Stage", "$default"],
          ]
        }
      },
      {
        type = "metric", x = 0, y = 12, width = 12, height = 6
        properties = {
          title  = "Aurora capacity (ACU; 0 = paused)"
          region = var.aws_region
          stat   = "Maximum"
          period = 300
          metrics = [
            ["AWS/RDS", "ServerlessDatabaseCapacity", "DBInstanceIdentifier", aws_rds_cluster_instance.writer.identifier],
          ]
        }
      },
      {
        type = "metric", x = 12, y = 12, width = 12, height = 6
        properties = {
          title  = "Model calls and tokens per 5 min"
          region = var.aws_region
          stat   = "Sum"
          period = 300
          metrics = [
            [local.app_namespace, "ModelCalls", "Route", "query"],
            [local.app_namespace, "Repairs", "Route", "query"],
            [local.app_namespace, "OutputTokens", "Route", "query"],
          ]
        }
      },
    ]
  })
}

# ADR 0004: an alert, not a cap. The throttles and request limits are the real controls.
resource "aws_budgets_budget" "monthly" {
  name         = "${local.name}-monthly"
  budget_type  = "COST"
  limit_amount = tostring(var.monthly_budget_usd)
  limit_unit   = "USD"
  time_unit    = "MONTHLY"

  dynamic "notification" {
    for_each = [50, 80, 100]
    content {
      comparison_operator        = "GREATER_THAN"
      threshold                  = notification.value
      threshold_type             = "PERCENTAGE"
      notification_type          = "ACTUAL"
      subscriber_email_addresses = [var.alert_email]
    }
  }

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 100
    threshold_type             = "PERCENTAGE"
    notification_type          = "FORECASTED"
    subscriber_email_addresses = [var.alert_email]
  }
}

# Lets Cost Explorer split this project's costs from anything else in the account
# (docs/costs.md). Every resource carries Project = var.project through the provider's
# default_tags. This is an account-wide billing setting; data appears within a day.
# Deleting the resource deactivates the tag again.
resource "aws_ce_cost_allocation_tag" "project" {
  tag_key = "Project"
  status  = "Active"
}
