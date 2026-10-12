data "aws_elasticache_serverless_cache" "publicai_serverless_cache" {
  name = "publicai-serverless-cache"
}

# Dedicated non-cluster ElastiCache instance for Lago (Cluster Mode: disabled)
# Sidekiq multi-queue BRPOP requires standalone/non-cluster Redis to avoid CROSSSLOT errors
data "aws_elasticache_replication_group" "non_cluster_cache" {
  replication_group_id = "non-cluster"
}



