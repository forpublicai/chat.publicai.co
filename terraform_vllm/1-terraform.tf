terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.51.0"
    }
  }

  required_version = ">= 1.2"

  # remote state configuration here
  backend "s3" {
    bucket         = "vllmaws-terraform-state" # update this to bucket name from terraform-remote-state
    key            = "vllmaws/terraform.tfstate"
    region         = "eu-central-1" # update this to match region in 0-locals.tf
    dynamodb_table = "vllmaws-terraform-state"
    encrypt        = true
  }
}

provider "aws" {
  region = local.region
}

data "aws_caller_identity" "current" {}
