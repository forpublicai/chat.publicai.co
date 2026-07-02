data "aws_route53_zone" "this" {
  name         = local.domain
  private_zone = false
}


# --- Wildcard ACM Certificate for EKS Ingresses (Must be in us-east-1 for ALB) ---
resource "aws_acm_certificate" "wildcard" {
  provider                  = aws.us_east_1
  domain_name               = "*.${local.domain}"
  subject_alternative_names = [local.domain]
  validation_method         = "DNS"

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_route53_record" "wildcard_acm_validation" {
  for_each = {
    for dvo in aws_acm_certificate.wildcard.domain_validation_options : dvo.domain_name => {
      name   = dvo.resource_record_name
      record = dvo.resource_record_value
      type   = dvo.resource_record_type
    }
  }

  allow_overwrite = true
  name            = each.value.name
  records         = [each.value.record]
  ttl             = 60
  type            = each.value.type
  zone_id         = data.aws_route53_zone.this.zone_id
}

resource "aws_acm_certificate_validation" "wildcard" {
  provider                = aws.us_east_1
  certificate_arn         = aws_acm_certificate.wildcard.arn
  validation_record_fqdns = [for record in aws_route53_record.wildcard_acm_validation : record.fqdn]
}

# --- SES Configuration for Cognito Verification/Mails ---
resource "aws_ses_domain_identity" "this" {
  domain = local.domain
}

resource "aws_route53_record" "ses_verification" {
  zone_id = data.aws_route53_zone.this.zone_id
  name    = "_amazonses.${local.domain}"
  type    = "TXT"
  ttl     = 600
  records = [aws_ses_domain_identity.this.verification_token]
}

resource "aws_ses_domain_dkim" "this" {
  domain = aws_ses_domain_identity.this.domain
}

resource "aws_route53_record" "ses_dkim" {
  count   = 3
  zone_id = data.aws_route53_zone.this.zone_id
  name    = "${aws_ses_domain_dkim.this.dkim_tokens[count.index]}._domainkey"
  type    = "CNAME"
  ttl     = 600
  records = ["${aws_ses_domain_dkim.this.dkim_tokens[count.index]}.dkim.amazonses.com"]
}

resource "aws_ses_configuration_set" "this" {
  name = "${local.env}-${local.org}-ses-config-set"
}

resource "aws_ses_domain_identity_verification" "this" {
  domain     = aws_ses_domain_identity.this.id
  depends_on = [aws_route53_record.ses_verification]
}

resource "aws_ses_identity_policy" "cognito" {
  identity = aws_ses_domain_identity.this.domain
  name     = "CognitoSendingPolicy"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowCognitoToSend"
        Effect = "Allow"
        Principal = {
          Service = "cognito-idp.amazonaws.com"
        }
        Action = [
          "SES:SendEmail",
          "SES:SendRawEmail"
        ]
        Resource = aws_ses_domain_identity.this.arn
        Condition = {
          StringEquals = {
            "aws:SourceArn" = aws_cognito_user_pool.this.arn
          }
        }
      }
    ]
  })
}


# --- Cognito User Pool ---
resource "aws_cognito_user_pool" "this" {
  name             = "${local.env}-${local.org}-openwebui"
  alias_attributes = null

  depends_on = [
    aws_ses_domain_identity_verification.this
  ]
  username_attributes      = ["email"]
  auto_verified_attributes = ["email"]
  # Active in prod, Inactive in staging/dev environments for easier lifecycle management
  deletion_protection = local.env == "prod" ? "ACTIVE" : "INACTIVE"
  mfa_configuration   = "OFF"

  user_pool_tier = "ESSENTIALS"

  account_recovery_setting {
    recovery_mechanism {
      name     = "verified_email"
      priority = 1
    }
    recovery_mechanism {
      name     = "verified_phone_number"
      priority = 2
    }
  }

  admin_create_user_config {
    allow_admin_create_user_only = false
  }

  email_configuration {
    configuration_set     = aws_ses_configuration_set.this.name
    email_sending_account = "DEVELOPER"
    from_email_address    = "No Reply <no-reply@${local.domain}>"
    source_arn            = aws_ses_domain_identity.this.arn
  }

  lambda_config {
    pre_sign_up = aws_lambda_function.pre_signup.arn
  }

  password_policy {
    minimum_length                   = 8
    password_history_size            = 0
    require_lowercase                = true
    require_numbers                  = true
    require_symbols                  = true
    require_uppercase                = true
    temporary_password_validity_days = 7
  }

  schema {
    attribute_data_type      = "String"
    developer_only_attribute = false
    mutable                  = true
    name                     = "email"
    required                 = true
    string_attribute_constraints {
      max_length = "2048"
      min_length = "0"
    }
  }

  schema {
    attribute_data_type      = "String"
    developer_only_attribute = false
    mutable                  = true
    name                     = "name"
    required                 = false
    string_attribute_constraints {
      max_length = null
      min_length = null
    }
  }

  sign_in_policy {
    allowed_first_auth_factors = ["PASSWORD"]
  }

  username_configuration {
    case_sensitive = false
  }

  verification_message_template {
    default_email_option  = "CONFIRM_WITH_LINK"
    email_message_by_link = "Please click the link below to verify your email address. {##Verify Email##}. \nAfter verification, simply go to https://chat.${local.domain}/ to login again. "
    email_subject_by_link = "Your verification link to join the Public AI Inference Utility"
  }
}

# --- Cognito Custom Domain ---
resource "aws_cognito_user_pool_domain" "this" {
  domain                = "auth.${local.domain}"
  certificate_arn       = aws_acm_certificate_validation.wildcard.certificate_arn
  managed_login_version = 2
  user_pool_id          = aws_cognito_user_pool.this.id

  depends_on = [
    time_sleep.wait_for_dns_propagation
  ]
}

# --- Route 53 Alias Record for Cognito Custom Domain ---
resource "aws_route53_record" "cognito_domain" {
  name    = "auth.${local.domain}"
  type    = "A"
  zone_id = data.aws_route53_zone.this.zone_id

  alias {
    evaluate_target_health = false
    name                   = aws_cognito_user_pool_domain.this.cloudfront_distribution
    zone_id                = aws_cognito_user_pool_domain.this.cloudfront_distribution_zone_id
  }
}

resource "aws_route53_record" "root_a_record" {
  zone_id = data.aws_route53_zone.this.zone_id
  name    = local.domain
  type    = "A"
  ttl     = 300
  records = ["1.1.1.1"] # Dummy IP to satisfy Cognito validation
}

resource "time_sleep" "wait_for_dns_propagation" {
  depends_on = [aws_route53_record.root_a_record]

  create_duration = "30s"
}


# --- Cognito Identity Provider (Google) ---
resource "aws_cognito_identity_provider" "google" {
  user_pool_id  = aws_cognito_user_pool.this.id
  provider_name = "Google"
  provider_type = "Google"

  attribute_mapping = {
    email    = "email"
    name     = "name"
    username = "sub"
  }

  provider_details = {
    attributes_url                = "https://people.googleapis.com/v1/people/me?personFields="
    attributes_url_add_attributes = "true"
    authorize_scopes              = "openid email profile"
    authorize_url                 = "https://accounts.google.com/o/oauth2/v2/auth"
    client_id                     = var.google_client_id
    client_secret                 = var.google_client_secret
    oidc_issuer                   = "https://accounts.google.com"
    token_request_method          = "POST"
    token_url                     = "https://www.googleapis.com/oauth2/v4/token"
  }
}

# --- Cognito User Pool Client ---
resource "aws_cognito_user_pool_client" "publicai_app" {
  name                                          = "${local.env}-${local.org}-app-client"
  user_pool_id                                  = aws_cognito_user_pool.this.id
  generate_secret                               = true
  access_token_validity                         = 60
  id_token_validity                             = 60
  refresh_token_validity                        = 5
  auth_session_validity                         = 3
  allowed_oauth_flows                           = ["code"]
  allowed_oauth_flows_user_pool_client          = true
  allowed_oauth_scopes                          = ["email", "openid", "phone", "profile"]
  callback_urls                                 = ["https://chat.${local.domain}/oauth/oidc/callback"]
  logout_urls                                   = ["https://chat.${local.domain}/", "https://${local.domain}/"]
  enable_propagate_additional_user_context_data = false
  enable_token_revocation                       = true
  prevent_user_existence_errors                 = "ENABLED"
  supported_identity_providers                  = ["COGNITO", "Google"]

  token_validity_units {
    access_token  = "minutes"
    id_token      = "minutes"
    refresh_token = "days"
  }

  explicit_auth_flows = [
    "ALLOW_ADMIN_USER_PASSWORD_AUTH",
    "ALLOW_CUSTOM_AUTH",
    "ALLOW_REFRESH_TOKEN_AUTH",
    "ALLOW_USER_AUTH",
    "ALLOW_USER_PASSWORD_AUTH",
    "ALLOW_USER_SRP_AUTH"
  ]

  # Ensure the identity provider is created before assigning it to the client
  depends_on = [aws_cognito_identity_provider.google]
}

# --- Cognito User Group ---
resource "aws_cognito_user_group" "google" {
  name         = "${aws_cognito_user_pool.this.id}_Google"
  description  = "Autogenerated group for users who sign in using Google"
  precedence   = 0
  role_arn     = null
  user_pool_id = aws_cognito_user_pool.this.id
}

# --- Cognito Pre Sign-Up Lambda Trigger ---
data "archive_file" "pre_signup_zip" {
  type        = "zip"
  output_path = "${path.module}/pre_signup.zip"

  source {
    content  = <<EOF
exports.handler = async (event) => {
    const email = event.request.userAttributes.email;
    if (!email) {
        throw new Error("Email is required.");
    }
    const domain = email.split('@')[1].toLowerCase();
    const allowedDomains = ["publicai.co", "currentai.org"];
    
    if (allowedDomains.includes(domain)) {
        event.response.autoConfirmUser = true;
        event.response.autoVerifyEmail = true;
        return event;
    } else {
        throw new Error("Registration is restricted to authorized domains in staging.");
    }
};
EOF
    filename = "index.js"
  }
}

resource "aws_lambda_function" "pre_signup" {
  filename         = data.archive_file.pre_signup_zip.output_path
  source_code_hash = data.archive_file.pre_signup_zip.output_base64sha256
  function_name    = "${local.env}-${local.org}-cognito-pre-signup"
  role             = aws_iam_role.pre_signup_lambda_role.arn
  handler          = "index.handler"
  runtime          = "nodejs18.x"
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

resource "aws_lambda_permission" "cognito_pre_signup" {
  statement_id  = "AllowExecutionFromCognito"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.pre_signup.function_name
  principal     = "cognito-idp.amazonaws.com"
  source_arn    = aws_cognito_user_pool.this.arn
}
