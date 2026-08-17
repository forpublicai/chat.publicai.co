locals {
  org     = "publicai"
  domain  = "publicai.co"
  env     = "prod"   # must be set to "prod" to enable prod resources like rds deletion protection
  region  = "eu-central-2"
  s3state = "${local.env}-terraform-state-${local.org}"
}
