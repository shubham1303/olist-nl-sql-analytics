# The API function (ADR 0001, 0004): outside the VPC, Python 3.13 on arm64, built by
# backend/scripts/build_lambda.py. Least privilege: its own log group, the Data API on
# this cluster with the analytics_reader secret only, and Bedrock on one inference
# profile (ADR 0019).

locals {
  # us.anthropic.claude-sonnet-4-6 -> anthropic.claude-sonnet-4-6
  foundation_model_id = replace(var.bedrock_model_id, "/^(us|eu|apac|global)\\./", "")
}

resource "aws_cloudwatch_log_group" "api_function" {
  name              = "/aws/lambda/${local.name}-api"
  retention_in_days = var.log_retention_days
}

resource "aws_iam_role" "api_function" {
  name = "${local.name}-api-function"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "api_function" {
  name = "least-privilege"
  role = aws_iam_role.api_function.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "OwnLogs"
        Effect   = "Allow"
        Action   = ["logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "${aws_cloudwatch_log_group.api_function.arn}:*"
      },
      {
        Sid      = "DataApiThisCluster"
        Effect   = "Allow"
        Action   = ["rds-data:ExecuteStatement"]
        Resource = aws_rds_cluster.main.arn
      },
      {
        Sid      = "ReaderSecretOnly"
        Effect   = "Allow"
        Action   = ["secretsmanager:GetSecretValue"]
        Resource = aws_secretsmanager_secret.reader.arn
      },
      {
        Sid    = "BedrockOneModel"
        Effect = "Allow"
        Action = ["bedrock:InvokeModel"]
        Resource = concat(
          ["arn:aws:bedrock:${var.aws_region}:${local.account_id}:inference-profile/${var.bedrock_model_id}"],
          [for region in var.bedrock_destination_regions :
          "arn:aws:bedrock:${region}::foundation-model/${local.foundation_model_id}"],
        )
      },
    ]
  })
}

resource "aws_lambda_function" "api" {
  function_name    = "${local.name}-api"
  role             = aws_iam_role.api_function.arn
  runtime          = "python3.13"
  architectures    = ["arm64"]
  handler          = "olist_nlsql.api.lambda_handler.handler"
  filename         = var.lambda_zip
  source_code_hash = filebase64sha256(var.lambda_zip)
  memory_size      = var.lambda_memory_mb
  # API Gateway HTTP APIs stop waiting at 30 s; two model calls at 12 s each plus the
  # query fit inside 29 s (ADR 0003: at most 2 model calls).
  timeout = 29

  reserved_concurrent_executions = var.reserved_concurrency == null ? -1 : var.reserved_concurrency

  logging_config {
    log_format = "Text" # EMF metric lines are printed raw to stdout
    log_group  = aws_cloudwatch_log_group.api_function.name
  }

  environment {
    variables = {
      NLSQL_ACCESS_CODE_SHA256  = var.access_code_sha256
      NLSQL_DB_CLUSTER_ARN      = aws_rds_cluster.main.arn
      NLSQL_DB_SECRET_ARN       = aws_secretsmanager_secret.reader.arn
      NLSQL_DB_NAME             = var.database_name
      NLSQL_AWS_REGION          = var.aws_region
      NLSQL_BEDROCK_MODEL_ID    = var.bedrock_model_id
      NLSQL_LLM_TIMEOUT_SECONDS = "12"
    }
  }

  depends_on = [aws_iam_role_policy.api_function]
}
