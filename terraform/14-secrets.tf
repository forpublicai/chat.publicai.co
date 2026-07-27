# 1. AWS Secrets Manager Secret for Manual Configuration (LICENSE_KEY, WEBUI_SECRET_KEY, Google client credentials)
resource "aws_secretsmanager_secret" "open_webui_manual" {
  name                    = "${local.env}/${local.org}/open-webui/manual-secrets"
  description             = "Manually managed secrets for Open WebUI"
  recovery_window_in_days = 0

  tags = {
    Name        = "${local.env}-${local.org}-open-webui-manual-secrets"
    Environment = local.env
  }
}

resource "aws_secretsmanager_secret_version" "open_webui_manual" {
  secret_id = aws_secretsmanager_secret.open_webui_manual.id
  secret_string = jsonencode({
    LICENSE_KEY          = "placeholder-replace-in-console"
    WEBUI_SECRET_KEY     = "placeholder-replace-in-console"
    GOOGLE_CLIENT_ID     = "placeholder-replace-in-console"
    GOOGLE_CLIENT_SECRET = "placeholder-replace-in-console"
  })

  lifecycle {
    ignore_changes = [secret_string]
  }
}

# 2. AWS Secrets Manager Secret for Auto-Generated Configuration (DB, Redis, Cognito client credentials)
resource "aws_secretsmanager_secret" "open_webui_managed" {
  name                    = "${local.env}/${local.org}/open-webui/managed-secrets"
  description             = "Terraform managed secrets for Open WebUI"
  recovery_window_in_days = 0

  tags = {
    Name        = "${local.env}-${local.org}-open-webui-managed-secrets"
    Environment = local.env
  }
}

resource "aws_secretsmanager_secret_version" "open_webui_managed" {
  secret_id = aws_secretsmanager_secret.open_webui_managed.id
  secret_string = jsonencode({
    DATABASE_URL         = "postgresql://postgres:${urlencode(jsondecode(data.aws_secretsmanager_secret_version.db_password.secret_string)["password"])}@${aws_rds_cluster.this.endpoint}:5432/openwebui?sslmode=require"
    OWUI_DATABASE_URL    = "postgresql://postgres:${urlencode(jsondecode(data.aws_secretsmanager_secret_version.db_password.secret_string)["password"])}@${aws_rds_cluster.this.endpoint}:5432/openwebui?sslmode=require"
    LITELLM_DATABASE_URL = "postgresql://postgres:${urlencode(jsondecode(data.aws_secretsmanager_secret_version.db_password.secret_string)["password"])}@${aws_rds_cluster.this.endpoint}:5432/litellm?sslmode=require"
    LAGO_DATABASE_URL    = "postgresql://postgres:${urlencode(jsondecode(data.aws_secretsmanager_secret_version.db_password.secret_string)["password"])}@${aws_rds_cluster.this.endpoint}:5432/lago?sslmode=require"
    MASTER_DATABASE_URL  = "postgresql://postgres:${urlencode(jsondecode(data.aws_secretsmanager_secret_version.db_password.secret_string)["password"])}@${aws_rds_cluster.this.endpoint}:5432/postgres?sslmode=require"
    REDIS_URL            = "rediss://${aws_elasticache_serverless_cache.currentai_serverless_cache.endpoint[0].address}:${aws_elasticache_serverless_cache.currentai_serverless_cache.endpoint[0].port}"
    LAGO_REDIS_URL       = "rediss://${aws_elasticache_serverless_cache.currentai_serverless_cache.endpoint[0].address}:${aws_elasticache_serverless_cache.currentai_serverless_cache.endpoint[0].port}/0"
    REDIS_HOST           = aws_elasticache_serverless_cache.currentai_serverless_cache.endpoint[0].address
    OAUTH_CLIENT_ID      = aws_cognito_user_pool_client.publicai_app.id
    OAUTH_CLIENT_SECRET  = aws_cognito_user_pool_client.publicai_app.client_secret
    OPENID_PROVIDER_URL  = "https://cognito-idp.${local.region}.amazonaws.com/${aws_cognito_user_pool.this.id}/.well-known/openid-configuration"
    OPENID_REDIRECT_URI  = "https://chat.${local.domain}/oauth/oidc/callback"
  })
}

# 2.5 AWS Secrets Manager Secret for LiteLLM Manual Configuration
resource "aws_secretsmanager_secret" "litellm_manual" {
  name                    = "${local.env}/${local.org}/litellm/manual-secrets"
  description             = "Manually managed secrets for LiteLLM"
  recovery_window_in_days = 0

  tags = {
    Name        = "${local.env}-${local.org}-litellm-manual-secrets"
    Environment = local.env
  }
}

# ANy changes to these should be done manually in the console, no need to change here
resource "aws_secretsmanager_secret_version" "litellm_manual" {
  secret_id = aws_secretsmanager_secret.litellm_manual.id
  secret_string = jsonencode({
    LITELLM_MASTER_KEY = "placeholder-replace-in-console"
    LITELLM_SALT_KEY   = "placeholder-replace-in-console"
    VLLM_API_KEY_INTEL = "placeholder-replace-in-console"
    LAGO_API_KEY       = "placeholder-replace-in-console"
    CSCS_API_KEY      = "placeholder-replace-in-console"
    # Add more manually in the console.
  })

  lifecycle {
    ignore_changes = [secret_string]
  }
}

# 2.6 AWS Secrets Manager Secret for Grafana Manual Configuration
resource "aws_secretsmanager_secret" "grafana" {
  name                    = "${local.env}/${local.org}/grafana/secrets"
  description             = "Manually managed secrets for Grafana"
  recovery_window_in_days = 0

  tags = {
    Name        = "${local.env}-${local.org}-grafana-secrets"
    Environment = local.env
  }
}

resource "aws_secretsmanager_secret_version" "grafana" {
  secret_id = aws_secretsmanager_secret.grafana.id
  secret_string = jsonencode({
    admin-user     = "admin"
    admin-password = "placeholder-replace-in-console"
  })

  lifecycle {
    ignore_changes = [secret_string]
  }
}

# 3. IAM Role & Policy for External Secrets Operator (IRSA)
resource "aws_iam_role" "external_secrets_irsa" {
  name = "${local.env}-ExternalSecrets-IRSA-Role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Federated = aws_iam_openid_connect_provider.eks.arn
        }
        Action = "sts:AssumeRoleWithWebIdentity"
        Condition = {
          StringEquals = {
            "${replace(aws_iam_openid_connect_provider.eks.url, "https://", "")}:sub" = "system:serviceaccount:external-secrets:external-secrets"
            "${replace(aws_iam_openid_connect_provider.eks.url, "https://", "")}:aud" = "sts.amazonaws.com"
          }
        }
      }
    ]
  })

  tags = {
    Name        = "${local.env}-${local.org}-external-secrets-irsa-role"
    Environment = local.env
  }
}

resource "aws_iam_policy" "external_secrets_secretsmanager_access" {
  name        = "${local.env}-ExternalSecrets-SecretsManager-Policy"
  description = "Allows External Secrets Operator to retrieve open-webui secrets from AWS Secrets Manager"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue",
          "secretsmanager:DescribeSecret"
        ]
        Resource = [
          aws_secretsmanager_secret.open_webui_manual.arn,
          aws_secretsmanager_secret.open_webui_managed.arn,
          aws_secretsmanager_secret.litellm_manual.arn,
          aws_secretsmanager_secret.grafana.arn
        ]
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "external_secrets_secretsmanager" {
  role       = aws_iam_role.external_secrets_irsa.name
  policy_arn = aws_iam_policy.external_secrets_secretsmanager_access.arn
}
