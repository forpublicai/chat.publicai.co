terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.92"
    }
  }

  required_version = ">= 1.2"

  # remote state configuration here
  backend "s3" {
    bucket         = "staging-terraform-state-publicai" # update this to bucket name from terraform-remote-state
    key            = "infra/terraform.tfstate"
    region         = "us-east-1" # update this to match region in 0-locals.tf
    dynamodb_table = "terraform-state"
    encrypt        = true
  }
}

provider "aws" {
  region = local.region
}
