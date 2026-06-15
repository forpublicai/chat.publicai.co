locals {
  org = "publicai"
  env    = "staging"
  region = "us-east-1" # "eu-central-2"
  s3state = "${local.env}-terraform-state-${local.org}"
}
