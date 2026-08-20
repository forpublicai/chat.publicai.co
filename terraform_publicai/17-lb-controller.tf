# --- IAM Role for AWS Load Balancer Controller (using EKS Pod Identity) ---
resource "aws_iam_role" "eks_lb_controller" {
  name = "${local.env}-AmazonEKSLoadBalancerControllerRole"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "pods.eks.amazonaws.com"
        }
        Action = [
          "sts:AssumeRole",
          "sts:TagSession"
        ]
      }
    ]
  })
}

# --- EKS Pod Identity Association for AWS Load Balancer Controller ---
resource "aws_eks_pod_identity_association" "eks_lb_controller" {
  cluster_name    = aws_eks_cluster.eks.name
  namespace       = "kube-system"
  service_account = "aws-load-balancer-controller"
  role_arn        = aws_iam_role.eks_lb_controller.arn
}

# --- Attach Required Policies to the Load Balancer Role ---
resource "aws_iam_role_policy_attachment" "eks_lb_controller_elbfull" {
  role       = aws_iam_role.eks_lb_controller.name
  policy_arn = "arn:aws:iam::aws:policy/ElasticLoadBalancingFullAccess"
}

resource "aws_iam_role_policy_attachment" "eks_lb_controller_vpcfull" {
  role       = aws_iam_role.eks_lb_controller.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonVPCFullAccess"
}

resource "aws_iam_role_policy_attachment" "eks_lb_controller_acm" {
  role       = aws_iam_role.eks_lb_controller.name
  policy_arn = "arn:aws:iam::aws:policy/AWSCertificateManagerReadOnly"
}

# --- Tag Shared Subnets for Prod Cluster Auto-Discovery ---
resource "aws_ec2_tag" "private_zone_1_cluster_tag" {
  resource_id = data.aws_subnet.private_zone_1.id
  key         = "kubernetes.io/cluster/${local.env}-${local.eks_name}"
  value       = "shared"
}

resource "aws_ec2_tag" "private_zone_2_cluster_tag" {
  resource_id = data.aws_subnet.private_zone_2.id
  key         = "kubernetes.io/cluster/${local.env}-${local.eks_name}"
  value       = "shared"
}

resource "aws_ec2_tag" "public_zone_1_cluster_tag" {
  resource_id = data.aws_subnet.public_zone_1.id
  key         = "kubernetes.io/cluster/${local.env}-${local.eks_name}"
  value       = "shared"
}

resource "aws_ec2_tag" "public_zone_2_cluster_tag" {
  resource_id = data.aws_subnet.public_zone_2.id
  key         = "kubernetes.io/cluster/${local.env}-${local.eks_name}"
  value       = "shared"
}
