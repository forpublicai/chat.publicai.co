# IAM Role for OpenWebUI (IRSA)

resource "aws_iam_role" "openwebui_irsa" {
  name = "${local.env}-OpenWebUI-IRSA-Role"

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
            "${replace(aws_iam_openid_connect_provider.eks.url, "https://", "")}:sub" = "system:serviceaccount:chat:openwebui-sa"
            "${replace(aws_iam_openid_connect_provider.eks.url, "https://", "")}:aud" = "sts.amazonaws.com"
          }
        }
      }
    ]
  })

  tags = {
    Name        = "${local.env}-${local.org}-openwebui-irsa-role"
    Environment = local.env
  }
}

resource "aws_iam_role_policy_attachment" "openwebui_s3" {
  role       = aws_iam_role.openwebui_irsa.name
  policy_arn = aws_iam_policy.s3_access.arn
}

output "openwebui_irsa_role_arn" {
  description = "IAM Role ARN for OpenWebUI IRSA"
  value       = aws_iam_role.openwebui_irsa.arn
}

