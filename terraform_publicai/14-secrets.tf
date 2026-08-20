
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
    DB_HOST             = data.aws_rds_cluster.this.endpoint
    DB_PORT             = "5432"
    DB_USER             = "postgres"
    DB_PASSWORD_ARN     = aws_secretsmanager_secret.rds_password.arn
    REDIS_URL           = "rediss://${data.aws_elasticache_serverless_cache.publicai_serverless_cache.endpoint.address}:${data.aws_elasticache_serverless_cache.publicai_serverless_cache.endpoint.port}"
    LAGO_REDIS_URL      = "rediss://${data.aws_elasticache_serverless_cache.publicai_serverless_cache.endpoint.address}:${data.aws_elasticache_serverless_cache.publicai_serverless_cache.endpoint.port}/0"
    REDIS_HOST          = data.aws_elasticache_serverless_cache.publicai_serverless_cache.endpoint.address
    OAUTH_CLIENT_ID     = data.aws_cognito_user_pool_client.publicai_app.id
    OAUTH_CLIENT_SECRET = data.aws_cognito_user_pool_client.publicai_app.client_secret
    OPENID_PROVIDER_URL = "https://cognito-idp.${local.region}.amazonaws.com/${data.aws_cognito_user_pool.this.id}/.well-known/openid-configuration"
    OPENID_REDIRECT_URI = "https://chat.${local.domain}/oauth/oidc/callback"
  })
}

resource "aws_secretsmanager_secret" "litellm_manual" {
  name                    = "${local.env}/${local.org}/litellm/manual-secrets"
  description             = "Manually managed secrets for LiteLLM"
  recovery_window_in_days = 0

  tags = {
    Name        = "${local.env}-${local.org}-litellm-manual-secrets"
    Environment = local.env
  }
}

resource "aws_secretsmanager_secret_version" "litellm_manual" {
  secret_id = aws_secretsmanager_secret.litellm_manual.id
  secret_string = jsonencode({
    LITELLM_MASTER_KEY = "placeholder-replace-in-console"
    LITELLM_SALT_KEY   = "placeholder-replace-in-console"
    VLLM_API_KEY_INTEL = "placeholder-replace-in-console"
    LAGO_API_KEY       = "placeholder-replace-in-console"
    CSCS_API_KEY       = "placeholder-replace-in-console"
  })

  lifecycle {
    ignore_changes = [secret_string]
  }
}

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

resource "aws_secretsmanager_secret" "prometheus" {
  name                    = "${local.env}/${local.org}/prometheus/secrets"
  description             = "Manually managed secrets for Prometheus"
  recovery_window_in_days = 0

  tags = {
    Name        = "${local.env}-${local.org}-prometheus-secrets"
    Environment = local.env
  }
}

resource "aws_secretsmanager_secret_version" "prometheus" {
  secret_id = aws_secretsmanager_secret.prometheus.id
  secret_string = jsonencode({
    admin-user     = "admin"
    admin-password = "placeholder-replace-in-console"
  })

  lifecycle {
    ignore_changes = [secret_string]
  }
}

resource "aws_secretsmanager_secret" "rds_password" {
  name                    = "${local.env}/${local.org}/database/password"
  description             = "Manually managed database master password"
  recovery_window_in_days = 0
}

resource "aws_secretsmanager_secret_version" "rds_password" {
  secret_id = aws_secretsmanager_secret.rds_password.id
  secret_string = jsonencode({
    password = "placeholder-replace-in-console"
  })

  lifecycle {
    ignore_changes = [secret_string]
  }
}

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
  description = "Allows External Secrets Operator to retrieve secrets from AWS Secrets Manager"

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
          aws_secretsmanager_secret.grafana.arn,
          aws_secretsmanager_secret.prometheus.arn,
          aws_secretsmanager_secret.rds_password.arn
        ]
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "external_secrets_secretsmanager" {
  role       = aws_iam_role.external_secrets_irsa.name
  policy_arn = aws_iam_policy.external_secrets_secretsmanager_access.arn
}
