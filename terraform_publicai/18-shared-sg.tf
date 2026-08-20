resource "aws_security_group" "shared_data" {
  name        = "prod-shared-data-sg"
  description = "Dedicated security group for shared database and cache instances"
  vpc_id      = data.aws_vpc.main_vpc.id

  # Ingress: PostgreSQL traffic from EKS
  ingress {
    description     = "Allow PostgreSQL traffic from prod-main-cluster EKS nodes"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_eks_cluster.eks.vpc_config[0].cluster_security_group_id]
  }

  # Ingress: Valkey/Redis traffic from EKS
  ingress {
    description     = "Allow Valkey/Redis traffic from prod-main-cluster EKS nodes"
    from_port       = 6379
    to_port         = 6379
    protocol        = "tcp"
    security_groups = [aws_eks_cluster.eks.vpc_config[0].cluster_security_group_id]
  }

  tags = {
    Name        = "prod-shared-data-sg"
    Environment = local.env
  }
}
