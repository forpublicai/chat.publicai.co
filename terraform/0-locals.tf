locals {
  org         = "publicai"
  domain      = "publicai.co"
  env         = "staging"    # must be set to "prod" to enable prod resources like rds deletion protection
  region      = "us-east-1"  # "eu-central-2"
  zone1       = "us-east-1a" # "eu-central-2a"
  zone2       = "us-east-1b" # "eu-central-2b"
  eks_name    = "main-cluster"
  eks_version = "1.36" # https://docs.aws.amazon.com/eks/latest/userguide/kubernetes-versions-standard.html
}
