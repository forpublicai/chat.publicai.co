locals {
  env    = "dev"
  region = "eu-central-2"
  zone1  = "eu-central-2a"
  zone2  = "eu-central-2b"
  eks_name = "main-cluster"
  eks_version="1.36" # https://docs.aws.amazon.com/eks/latest/userguide/kubernetes-versions-standard.html
}
