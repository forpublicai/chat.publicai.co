terraform {
  required_providers {
    aws = {
      source = "hashicorp/aws"
    }
    archive = {
      source = "hashicorp/archive"
    }
  }
}

variable "name_prefix" {
  type        = string
  description = "Environment and organization prefix for cleanup resources."
}

variable "user_pool_id" {
  type        = string
  description = "Cognito pool whose unconfirmed registrations will be cleaned up."
}

variable "user_pool_arn" {
  type        = string
  description = "Cognito pool to which cleanup permissions are restricted."
}

locals {
  name = "${var.name_prefix}-cognito-cleanup"
}

data "archive_file" "this" {
  type        = "zip"
  source_file = "${path.module}/cleanup.py"
  output_path = "${path.root}/.terraform/${local.name}.zip"
}

resource "aws_cloudwatch_log_group" "this" {
  name              = "/aws/lambda/${local.name}"
  retention_in_days = 30
}

resource "aws_iam_role" "this" {
  name = local.name

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Action    = "sts:AssumeRole"
      Principal = { Service = "lambda.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy" "this" {
  name = "cleanup"
  role = aws_iam_role.this.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "cognito-idp:ListUsers",
          "cognito-idp:AdminGetUser",
          "cognito-idp:AdminDeleteUser",
        ]
        Resource = var.user_pool_arn
      },
      {
        Effect   = "Allow"
        Action   = ["logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "${aws_cloudwatch_log_group.this.arn}:*"
      }
    ]
  })
}

resource "aws_lambda_function" "this" {
  function_name                  = local.name
  filename                       = data.archive_file.this.output_path
  source_code_hash               = data.archive_file.this.output_base64sha256
  role                           = aws_iam_role.this.arn
  handler                        = "cleanup.handler"
  runtime                        = "python3.14"
  timeout                        = 300
  memory_size                    = 128
  reserved_concurrent_executions = 1

  environment {
    variables = {
      USER_POOL_ID = var.user_pool_id
    }
  }

  depends_on = [aws_iam_role_policy.this]
}

resource "aws_cloudwatch_event_rule" "this" {
  name                = local.name
  description         = "Delete Cognito registrations unconfirmed for more than 24 hours."
  schedule_expression = "rate(1 hour)"
}

resource "aws_lambda_permission" "events" {
  statement_id  = "AllowHourlyCleanup"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.this.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.this.arn
}

resource "aws_cloudwatch_event_target" "this" {
  rule      = aws_cloudwatch_event_rule.this.name
  target_id = "cognito-cleanup"
  arn       = aws_lambda_function.this.arn

  depends_on = [aws_lambda_permission.events]
}
