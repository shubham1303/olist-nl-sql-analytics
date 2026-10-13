# HTTP API in front of the function (ADR 0004): two routes, throttling, CORS for the
# browser origins, access logs. The access code is checked in the function.

resource "aws_apigatewayv2_api" "main" {
  name          = "${local.name}-api"
  protocol_type = "HTTP"

  cors_configuration {
    allow_origins = var.cors_allow_origins
    allow_methods = ["GET", "POST"]
    allow_headers = ["content-type", "x-access-code"]
    max_age       = 3600
  }
}

resource "aws_apigatewayv2_integration" "function" {
  api_id                 = aws_apigatewayv2_api.main.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.api.invoke_arn
  payload_format_version = "2.0"
  timeout_milliseconds   = 29000
}

resource "aws_apigatewayv2_route" "status" {
  api_id    = aws_apigatewayv2_api.main.id
  route_key = "GET /status"
  target    = "integrations/${aws_apigatewayv2_integration.function.id}"
}

resource "aws_apigatewayv2_route" "query" {
  api_id    = aws_apigatewayv2_api.main.id
  route_key = "POST /query"
  target    = "integrations/${aws_apigatewayv2_integration.function.id}"
}

resource "aws_cloudwatch_log_group" "api_access" {
  name              = "/aws/apigateway/${local.name}-api"
  retention_in_days = var.log_retention_days
}

resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.main.id
  name        = "$default"
  auto_deploy = true

  default_route_settings {
    throttling_rate_limit  = var.throttle_rate_per_second
    throttling_burst_limit = var.throttle_burst
  }

  # /query costs a Bedrock call and a database query: throttled tighter.
  route_settings {
    route_key              = aws_apigatewayv2_route.query.route_key
    throttling_rate_limit  = var.query_throttle_rate_per_second
    throttling_burst_limit = var.query_throttle_burst
  }

  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.api_access.arn
    format = jsonencode({
      requestId          = "$context.requestId"
      ip                 = "$context.identity.sourceIp"
      routeKey           = "$context.routeKey"
      status             = "$context.status"
      responseLatency    = "$context.responseLatency"
      integrationLatency = "$context.integrationLatency"
      integrationError   = "$context.integrationErrorMessage"
    })
  }
}

resource "aws_lambda_permission" "api_gateway" {
  statement_id  = "AllowHttpApiInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.api.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.main.execution_arn}/*/*"
}
