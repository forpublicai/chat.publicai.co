data "aws_rds_cluster" "this" {
  cluster_identifier = "publicai-database-1"
}

resource "aws_vpc_security_group_ingress_rule" "allow_eks_to_db" {
  security_group_id            = "sg-0b3a705b8e92c8e7b"
  description                  = "Allow PostgreSQL traffic from prod-main-cluster EKS nodes"
  referenced_security_group_id = aws_eks_cluster.eks.vpc_config[0].cluster_security_group_id
  from_port                    = 5432
  to_port                      = 5432
  ip_protocol                  = "tcp"
}
