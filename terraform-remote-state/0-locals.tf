locals {
  org     = "aichat"
  domain  = "ai-staging.chat"
  env     = "staging"   # must be set to "prod" to enable prod resources like rds deletion protection
  region  = "us-east-1" # "eu-central-2"
  s3state = "${local.env}-terraform-state-${local.org}"
}
