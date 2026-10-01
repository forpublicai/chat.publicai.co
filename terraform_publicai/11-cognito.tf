data "aws_cognito_user_pool" "this" {
  user_pool_id = "eu-central-2_Q868jeWwT"
}

data "aws_cognito_user_pool_client" "publicai_app" {
  user_pool_id = data.aws_cognito_user_pool.this.id
  client_id    = "4c3er1ug19vpu5vdufaqsntqdc"
}

# --- Cognito Pre Sign-Up Lambda Trigger (Auto-Confirm & Auto-Verify) ---

data "archive_file" "pre_signup_zip" {
  type        = "zip"
  output_path = "${path.module}/pre_signup.zip"

  source {
    content  = <<EOF
exports.handler = async (event) => {
    event.response.autoConfirmUser = true;
    event.response.autoVerifyEmail = true;
    return event;
};
EOF
    filename = "index.js"
  }
}

resource "aws_iam_role" "pre_signup_lambda_role" {
  name = "${local.env}-${local.org}-pre-signup-lambda-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "pre_signup_lambda_logs" {
  role       = aws_iam_role.pre_signup_lambda_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_lambda_function" "pre_signup" {
  filename         = data.archive_file.pre_signup_zip.output_path
  source_code_hash = data.archive_file.pre_signup_zip.output_base64sha256
  function_name    = "${local.env}-${local.org}-cognito-pre-signup"
  role             = aws_iam_role.pre_signup_lambda_role.arn
  handler          = "index.handler"
  runtime          = "nodejs20.x"
}

resource "aws_lambda_permission" "cognito_pre_signup" {
  statement_id  = "AllowExecutionFromCognito"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.pre_signup.function_name
  principal     = "cognito-idp.amazonaws.com"
  source_arn    = data.aws_cognito_user_pool.this.arn
}

output "pre_signup_lambda_arn" {
  description = "ARN of the Pre-Sign-Up Lambda to attach to the Cognito User Pool"
  value       = aws_lambda_function.pre_signup.arn
}

