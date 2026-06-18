terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.92"
    }
    postgresql = {
      source  = "cyrilgdn/postgresql"
      version = "~> 1.26.0"
    }
        time = {
      source  = "hashicorp/time"
      version = "~> 0.11"
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

data "aws_caller_identity" "current" {}
