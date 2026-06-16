resource "aws_security_group" "elasticache" {
  name        = "${local.env}-${local.org}-elasticache-sg"
  description = "Security group for ElastiCache serverless cache"
  vpc_id      = aws_vpc.main_vpc.id

  ingress {
    description = "Allow Valkey/Redis traffic from EKS cluster pods/nodes"
    from_port   = 6379
    to_port     = 6379
    protocol    = "tcp"
    security_groups = [
      aws_eks_cluster.eks.vpc_config[0].cluster_security_group_id
    ]
  }

  egress {
    description = "Allow all outbound traffic"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${local.env}-${local.org}-elasticache-sg"
  }
}

resource "aws_elasticache_serverless_cache" "currentai_serverless_cache" {
  name                     = "${local.env}-${local.org}-cache"
  engine                   = "valkey"
  major_engine_version     = "9"
  description              = "ElastiCache Serverless Valkey Cache for ${local.org} ${local.env}"
  daily_snapshot_time      = "03:00"
  snapshot_retention_limit = 0
  security_group_ids       = [aws_security_group.elasticache.id] # can use this instead     aws_eks_cluster.eks.vpc_config[0].cluster_security_group_id
  subnet_ids = [
    aws_subnet.private_zone_1.id,
    aws_subnet.private_zone_2.id
  ]
}
