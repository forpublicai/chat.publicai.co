 terraform plan -generate-config-out=generated.tf

## Install AWS CLI

Follow guide here:

[AWS CLI Install Guide](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html)

use aws configure or aws login.

## Install terraform

[Terraform Install Guide](https://developer.hashicorp.com/terraform/install)

terraform -install-autocomplete


# First time account set up
These instructions are only used if you want to create a brand new deployment from scratch in AWS. 

The terraform scripts are applied via a github action. Github needs to authenticate with AWS via GitHub OIDC federation.

## Add GitHub OIDC provider to IAM
[GitHub Provider details](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_providers_create_oidc.html#manage-oidc-provider-console)

For the provider URL: Use ``https://token.actions.githubusercontent.com``
For the "Audience": Use ``sts.amazonaws.com`` if you are using the official action.

[AWS Console](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_providers_create_oidc.html#manage-oidc-provider-console)

After provider is added, add an IAM role, assign it to the github organisation, repository and branch you want to push code from.

Create a role with trust policy - branch only

the trust policy must have repo formatted like below
```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            ...
                "StringLike": {
                    "token.actions.githubusercontent.com:sub": [
                        "repo:forpublicai/chat.publicai.co:ref:refs/tags/v*"
                    ]
                }
            }
        }
    ]
}
```

dd permissions for VPC, S3 CLuster etc..

## Create S3 bucket for terraform state
1. Create an IAM user with full access to S3 and DynamoDB.
1. Login to aws CLI with that user.
1. Modify the ``0-locals.tf`` to include the correct org and region in ``terraform-remote-state``
1. Then run the following commands to create the S3 bucket:

```bash
cd terraform-remote-state
terraform init
terraform plan
terraform apply
```

Then copy the bucket name into ``terraform/1-terraform.tf``, and update the region.

```yaml
  # remote state configuration here
  backend "s3" {
    bucket         = "staging-terraform-state-publicai" # update this to bucket name from terraform-remote-state
    key            = "infra/terraform.tfstate"
    region         = "us-east-1" # update this to match region in 0-locals.tf
    dynamodb_table = "terraform-state"
    encrypt        = true
  }
```



