data "aws_cognito_user_pool" "this" {
  user_pool_id = "eu-central-2_Q868jeWwT"
}

data "aws_cognito_user_pool_client" "publicai_app" {
  user_pool_id = data.aws_cognito_user_pool.this.id
  client_id    = "4c3er1ug19vpu5vdufaqsntqdc"
}

module "cognito_cleanup" {
  source = "../modules/cognito-cleanup"

  name_prefix   = "${local.env}-${local.org}"
  user_pool_id  = data.aws_cognito_user_pool.this.id
  user_pool_arn = data.aws_cognito_user_pool.this.arn
}
