terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.51.0"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 3.2.0"
    }
    helm = {
      source  = "hashicorp/helm"
      version = "~> 3.2.0"
    }
    postgresql = {
      source  = "cyrilgdn/postgresql"
      version = "~> 1.26.0"
    }
    time = {
      source  = "hashicorp/time"
      version = "~> 0.14"
    }
  }

  required_version = ">= 1.2"

  # remote state configuration here
  backend "s3" {
    bucket         = "staging-terraform-state-aichat" # update this to bucket name from terraform-remote-state
    key            = "infra/terraform.tfstate"
    region         = "us-east-1" # update this to match region in 0-locals.tf
    dynamodb_table = "terraform-state"
    encrypt        = true
  }
}

provider "aws" {
  region = local.region
}

provider "aws" {
  alias  = "us_east_1"
  region = "us-east-1"
}

provider "kubernetes" {
  host                   = aws_eks_cluster.eks.endpoint
  cluster_ca_certificate = base64decode(aws_eks_cluster.eks.certificate_authority[0].data)

  exec {
    api_version = "client.authentication.k8s.io/v1beta1"
    args        = ["eks", "get-token", "--cluster-name", aws_eks_cluster.eks.name]
    command     = "aws"
  }
}

provider "helm" {
  kubernetes {
    host                   = aws_eks_cluster.eks.endpoint
    cluster_ca_certificate = base64decode(aws_eks_cluster.eks.certificate_authority[0].data)

    exec {
      api_version = "client.authentication.k8s.io/v1beta1"
      args        = ["eks", "get-token", "--cluster-name", aws_eks_cluster.eks.name]
      command     = "aws"
    }
  }
}

data "aws_caller_identity" "current" {}
