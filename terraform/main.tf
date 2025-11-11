provider "aws" {
  region = var.aws_region
}

locals {
  name_prefix = "${var.project}-${var.environment}"
}

data "aws_caller_identity" "current" {}

# DynamoDB table for latest telemetry snapshot per charger
resource "aws_dynamodb_table" "telemetry_latest" {
  name           = "${locals.name_prefix}-latest"
  billing_mode   = "PAY_PER_REQUEST"
  hash_key       = "charger_id"
  stream_enabled = false

  attribute {
    name = "charger_id"
    type = "S"
  }

  tags = {
    Project     = var.project
    Environment = var.environment
  }
}

# Dead-letter queue for poison messages
resource "aws_sqs_queue" "telemetry_dlq" {
  name                      = "${locals.name_prefix}-dlq.fifo"
  fifo_queue                = true
  content_based_deduplication = true
  message_retention_seconds = 1209600

  tags = {
    Project     = var.project
    Environment = var.environment
  }
}

# Primary FIFO queue for telemetry events
resource "aws_sqs_queue" "telemetry_fifo" {
  name                        = "${locals.name_prefix}-ingest.fifo"
  fifo_queue                  = true
  content_based_deduplication = true
  visibility_timeout_seconds  = 60
  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.telemetry_dlq.arn
    maxReceiveCount     = 5
  })

  tags = {
    Project     = var.project
    Environment = var.environment
  }
}

# IAM role + policies for Ingest Lambda
data "aws_iam_policy_document" "lambda_assume" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "ingest" {
  name               = "${locals.name_prefix}-ingest-lambda"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume.json
}

resource "aws_iam_role_policy" "ingest" {
  name = "${locals.name_prefix}-ingest-inline"
  role = aws_iam_role.ingest.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["sqs:SendMessage", "sqs:GetQueueAttributes"]
        Resource = aws_sqs_queue.telemetry_fifo.arn
      },
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:${var.aws_region}:${data.aws_caller_identity.current.account_id}:log-group:/aws/lambda/${locals.name_prefix}-ingest:*"
      }
    ]
  })
}

# IAM role + policies for Processor Lambda
resource "aws_iam_role" "processor" {
  name               = "${locals.name_prefix}-processor-lambda"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume.json
}

resource "aws_iam_role_policy" "processor" {
  name = "${locals.name_prefix}-processor-inline"
  role = aws_iam_role.processor.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["dynamodb:PutItem", "dynamodb:UpdateItem"]
        Resource = aws_dynamodb_table.telemetry_latest.arn
      },
      {
        Effect   = "Allow"
        Action   = ["sqs:ReceiveMessage", "sqs:DeleteMessage", "sqs:GetQueueAttributes"]
        Resource = aws_sqs_queue.telemetry_fifo.arn
      },
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:${var.aws_region}:${data.aws_caller_identity.current.account_id}:log-group:/aws/lambda/${locals.name_prefix}-processor:*"
      }
    ]
  })
}

# IAM role + policies for Query Lambda
resource "aws_iam_role" "query" {
  name               = "${locals.name_prefix}-query-lambda"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume.json
}

resource "aws_iam_role_policy" "query" {
  name = "${locals.name_prefix}-query-inline"
  role = aws_iam_role.query.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["dynamodb:GetItem"]
        Resource = aws_dynamodb_table.telemetry_latest.arn
      },
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:${var.aws_region}:${data.aws_caller_identity.current.account_id}:log-group:/aws/lambda/${locals.name_prefix}-query:*"
      }
    ]
  })
}

# Package Lambda source code
data "archive_file" "ingest_zip" {
  type        = "zip"
  source_dir  = "${path.module}/../src/ingest"
  output_path = "${path.module}/../dist/ingest.zip"
}

data "archive_file" "processor_zip" {
  type        = "zip"
  source_dir  = "${path.module}/../src/processor"
  output_path = "${path.module}/../dist/processor.zip"
}

data "archive_file" "query_zip" {
  type        = "zip"
  source_dir  = "${path.module}/../src/query"
  output_path = "${path.module}/../dist/query.zip"
}

resource "aws_lambda_function" "ingest" {
  function_name = "${locals.name_prefix}-ingest"
  role          = aws_iam_role.ingest.arn
  runtime       = "python3.11"
  handler       = "handler.lambda_handler"
  filename      = data.archive_file.ingest_zip.output_path
  source_code_hash = data.archive_file.ingest_zip.output_base64sha256
  memory_size   = var.lambda_memory_size
  timeout       = var.lambda_timeout_seconds
  environment {
    variables = {
      TELEMETRY_QUEUE_URL = aws_sqs_queue.telemetry_fifo.url
    }
  }
}

resource "aws_lambda_function" "processor" {
  function_name = "${locals.name_prefix}-processor"
  role          = aws_iam_role.processor.arn
  runtime       = "python3.11"
  handler       = "handler.lambda_handler"
  filename      = data.archive_file.processor_zip.output_path
  source_code_hash = data.archive_file.processor_zip.output_base64sha256
  memory_size   = var.lambda_memory_size
  timeout       = var.lambda_timeout_seconds
  environment {
    variables = {
      TELEMETRY_TABLE_NAME = aws_dynamodb_table.telemetry_latest.name
    }
  }
}

resource "aws_lambda_function" "query" {
  function_name = "${locals.name_prefix}-query"
  role          = aws_iam_role.query.arn
  runtime       = "python3.11"
  handler       = "handler.lambda_handler"
  filename      = data.archive_file.query_zip.output_path
  source_code_hash = data.archive_file.query_zip.output_base64sha256
  memory_size   = var.lambda_memory_size
  timeout       = var.lambda_timeout_seconds
  environment {
    variables = {
      TELEMETRY_TABLE_NAME = aws_dynamodb_table.telemetry_latest.name
    }
  }
}

resource "aws_lambda_event_source_mapping" "processor_sqs" {
  event_source_arn  = aws_sqs_queue.telemetry_fifo.arn
  function_name     = aws_lambda_function.processor.arn
  batch_size        = 10
  maximum_batching_window_in_seconds = 5
  enabled           = true
}

# HTTP API for ingest and query endpoints
resource "aws_apigatewayv2_api" "telemetry" {
  name          = "${locals.name_prefix}-api"
  protocol_type = "HTTP"
}

resource "aws_apigatewayv2_integration" "ingest" {
  api_id                 = aws_apigatewayv2_api.telemetry.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.ingest.invoke_arn
  integration_method     = "POST"
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "ingest" {
  api_id    = aws_apigatewayv2_api.telemetry.id
  route_key = "POST /telemetry"
  target    = "integrations/${aws_apigatewayv2_integration.ingest.id}"
}

resource "aws_lambda_permission" "apigw_ingest" {
  statement_id  = "AllowAPIGatewayInvokeIngest"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.ingest.arn
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.telemetry.execution_arn}/*/*"
}

resource "aws_apigatewayv2_integration" "query" {
  api_id                 = aws_apigatewayv2_api.telemetry.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.query.invoke_arn
  integration_method     = "GET"
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "query" {
  api_id    = aws_apigatewayv2_api.telemetry.id
  route_key = "GET /telemetry/{chargerId}"
  target    = "integrations/${aws_apigatewayv2_integration.query.id}"
}

resource "aws_lambda_permission" "apigw_query" {
  statement_id  = "AllowAPIGatewayInvokeQuery"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.query.arn
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.telemetry.execution_arn}/*/*"
}

resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.telemetry.id
  name        = "$default"
  auto_deploy = true

  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.api_logs.arn
    format          = jsonencode({ requestId = "$context.requestId", routeKey = "$context.routeKey", status = "$context.status" })
  }
}

resource "aws_cloudwatch_log_group" "api_logs" {
  name              = "/aws/apigw/${locals.name_prefix}"
  retention_in_days = 14
}

# Output parameters are defined in outputs.tf

