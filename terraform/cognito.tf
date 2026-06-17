provider "aws" {
  alias  = "us_east_1"
  region = "us-east-1"
}

data "aws_route53_zone" "this" {
  name         = local.domain
  private_zone = false
}

# --- Cognito ACM Certificate (Must be in us-east-1 for custom domains) ---
resource "aws_acm_certificate" "cognito" {
  provider          = aws.us_east_1
  domain_name       = "auth.${local.domain}"
  validation_method = "DNS"

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_route53_record" "cognito_acm_validation" {
  for_each = {
    for dvo in aws_acm_certificate.cognito.domain_validation_options : dvo.domain_name => {
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

resource "aws_acm_certificate_validation" "cognito" {
  provider                = aws.us_east_1
  certificate_arn         = aws_acm_certificate.cognito.arn
  validation_record_fqdns = [for record in aws_route53_record.cognito_acm_validation : record.fqdn]
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

# --- Cognito User Pool ---
resource "aws_cognito_user_pool" "this" {
  name                = "${local.env}-${local.org}-openwebui"
  alias_attributes    = null
  username_attributes = ["email"]

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
  certificate_arn       = aws_acm_certificate_validation.cognito.certificate_arn
  managed_login_version = 2
  user_pool_id          = aws_cognito_user_pool.this.id
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
    client_id                     = ""
    client_secret                 = ""
    oidc_issuer                   = "https://accounts.google.com"
    token_request_method          = "POST"
    token_url                     = "https://www.googleapis.com/oauth2/v4/token"
  }
}

# --- Cognito User Pool Client ---
resource "aws_cognito_user_pool_client" "publicai_app" {
  name                                          = "${local.env}-${local.org}-app-client"
  user_pool_id                                  = aws_cognito_user_pool.this.id
  generate_secret                               = null
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
  read_attributes                               = []
  write_attributes                              = []
  supported_identity_providers                  = ["COGNITO", "Google"]

  token_validity_units {
    access_token  = "minutes"
    id_token      = "minutes"
    refresh_token = "days"
  }

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
