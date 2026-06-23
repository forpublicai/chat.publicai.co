# 1. OpenWebUI Role
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
            "${replace(aws_iam_openid_connect_provider.eks.url, "https://", "")}:sub" = "system:serviceaccount:web-services:openwebui-sa"
            "${replace(aws_iam_openid_connect_provider.eks.url, "https://", "")}:aud" = "sts.amazonaws.com"
          }
        }
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "openwebui_s3" {
  role       = aws_iam_role.openwebui_irsa.name
  policy_arn = aws_iam_policy.s3_access.arn
}

# 2. Lago Role
resource "aws_iam_role" "lago_irsa" {
  name = "${local.env}-Lago-IRSA-Role"

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
            "${replace(aws_iam_openid_connect_provider.eks.url, "https://", "")}:sub" = "system:serviceaccount:web-services:web-services-serviceaccount"
            "${replace(aws_iam_openid_connect_provider.eks.url, "https://", "")}:aud" = "sts.amazonaws.com"
          }
        }
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "lago_s3" {
  role       = aws_iam_role.lago_irsa.name
  policy_arn = aws_iam_policy.s3_access.arn
}



# 3. AmazonEKSLoadBalancerControllerRole
resource "aws_iam_role" "eks_lb_controller" {
  name = "AmazonEKSLoadBalancerControllerRole"

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
            "${replace(aws_iam_openid_connect_provider.eks.url, "https://", "")}:sub" = "system:serviceaccount:web-services:aws-load-balancer-controller"
            "${replace(aws_iam_openid_connect_provider.eks.url, "https://", "")}:aud" = "sts.amazonaws.com"
          }
        }
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "eks_lb_controller_elbfull" {
  role       = aws_iam_role.eks_lb_controller.name
  policy_arn = "arn:aws:iam::aws:policy/ElasticLoadBalancingFullAccess"
}

resource "aws_iam_role_policy_attachment" "eks_lb_controller_vpcfull" {
  role       = aws_iam_role.eks_lb_controller.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonVPCFullAccess"
}

# 4. AmazonEKS_LiteLLM_Role
resource "aws_iam_role" "lite_llm" {
  name = "AmazonEKS_LiteLLM_Role"

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
            "${replace(aws_iam_openid_connect_provider.eks.url, "https://", "")}:sub" = "system:serviceaccount:web-services:litellm-sa"
            "${replace(aws_iam_openid_connect_provider.eks.url, "https://", "")}:aud" = "sts.amazonaws.com"
          }
        }
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "lite_llm_elasticache" {
  role       = aws_iam_role.lite_llm.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonElastiCacheFullAccess"
}

resource "aws_iam_role_policy_attachment" "lite_llm_bedrock" {
  role       = aws_iam_role.lite_llm.name
  policy_arn = aws_iam_policy.apertus_bedrock.arn
}

# 5. AmazonEKS_S3_CSI_DriverRole
resource "aws_iam_role" "s3_csi_driver" {
  name = "AmazonEKS_S3_CSI_DriverRole"

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
            "${replace(aws_iam_openid_connect_provider.eks.url, "https://", "")}:sub" = "system:serviceaccount:kube-system:s3-csi-driver-sa"
            "${replace(aws_iam_openid_connect_provider.eks.url, "https://", "")}:aud" = "sts.amazonaws.com"
          }
        }
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "s3_csi_driver_s3" {
  role       = aws_iam_role.s3_csi_driver.name
  policy_arn = aws_iam_policy.apertus_s3_csi.arn
}

# 6. AmazonEKSAutoNodeRole
resource "aws_iam_role" "eks_auto_node_role" {
  name = "AmazonEKSAutoNodeRole"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "ec2.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })

  description          = "Allows EKS nodes to connect to EKS Auto Mode clusters and to pull container images from ECR."
  max_session_duration = 3600
}

resource "aws_iam_instance_profile" "eks_auto_node_profile" {
  name = "AmazonEKSAutoNodeRole"
  role = aws_iam_role.eks_auto_node_role.name
}

resource "aws_iam_role_policy_attachment" "eks_auto_node_role_AmazonEC2FullAccess" {
  role       = aws_iam_role.eks_auto_node_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEC2FullAccess"
}

resource "aws_iam_role_policy_attachment" "eks_auto_node_role_AmazonEKSWorkerNodePolicy" {
  role       = aws_iam_role.eks_auto_node_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSWorkerNodePolicy"
}

resource "aws_iam_role_policy_attachment" "eks_auto_node_role_AmazonEKSWorkerNodeMinimalPolicy" {
  role       = aws_iam_role.eks_auto_node_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSWorkerNodeMinimalPolicy"
}

resource "aws_iam_role_policy_attachment" "eks_auto_node_role_AmazonEC2ContainerRegistryPullOnly" {
  role       = aws_iam_role.eks_auto_node_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryPullOnly"
}

# Customer Managed Policies used by the roles
resource "aws_iam_policy" "apertus_bedrock" {
  name        = "ApertusBedrockPolicy"
  description = "Policy for Bedrock access used by LiteLLM pods"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "bedrock:InvokeModel*",
          "bedrock:CreateInferenceProfile"
        ]
        Resource = [
          "arn:aws:bedrock:*::foundation-model/*",
          "arn:aws:bedrock:*:*:inference-profile/*",
          "arn:aws:bedrock:*:*:application-inference-profile/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "bedrock:GetInferenceProfile",
          "bedrock:ListInferenceProfiles",
          "bedrock:DeleteInferenceProfile",
          "bedrock:TagResource",
          "bedrock:UntagResource",
          "bedrock:ListTagsForResource"
        ]
        Resource = [
          "arn:aws:bedrock:*:*:inference-profile/*",
          "arn:aws:bedrock:*:*:application-inference-profile/*"
        ]
      },
      {
        Sid    = "InvokeEmbeddingsEUCentral1"
        Effect = "Allow"
        Action = [
          "bedrock:InvokeModel",
          "bedrock:Rerank"
        ]
        Resource = [
          "arn:aws:bedrock:eu-central-1::foundation-model/amazon.titan-embed-text-v2:0",
          "arn:aws:bedrock:eu-central-1::foundation-model/cohere.embed-english-v3.0",
          "arn:aws:bedrock:eu-central-1::foundation-model/cohere.embed-multilingual-v3.0"
        ]
      },
      {
        Sid    = "BedrockGuardrailAccess"
        Effect = "Allow"
        Action = [
          "bedrock:ApplyGuardrail",
          "bedrock:GetGuardrail",
          "bedrock:ListGuardrails",
          "bedrock:InvokeModel"
        ]
        Resource = [
          "arn:aws:bedrock:eu-*:${data.aws_caller_identity.current.account_id}:guardrail/*",
          "arn:aws:bedrock:eu-*:${data.aws_caller_identity.current.account_id}:guardrail-profile/*",
          "arn:aws:bedrock:eu-central-1:${data.aws_caller_identity.current.account_id}:guardrail/ux3n95in9v9h",
          "arn:aws:bedrock:eu-central-1::foundation-model/*"
        ]
      },
      {
        Sid      = "OptionalListModels"
        Effect   = "Allow"
        Action   = "bedrock:ListFoundationModels"
        Resource = "*"
      }
    ]
  })
}

resource "aws_iam_policy" "apertus_s3_csi" {
  name        = "ApertusS3CSIDriverPolicy"
  description = "Policy for EKS S3 CSI Driver storage integrations"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "MountpointFullBucketAccess"
        Effect   = "Allow"
        Action   = ["s3:ListBucket"]
        Resource = [aws_s3_bucket.bucket.arn]
      },
      {
        Sid    = "MountpointFullObjectAccess"
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:AbortMultipartUpload",
          "s3:DeleteObject"
        ]
        Resource = ["${aws_s3_bucket.bucket.arn}/*"]
      }
    ]
  })
}
