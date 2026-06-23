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

# Google Auth Credentials

Go to console.cloud.google.com
Create a new project if needed
Go to Google Auth PLatform
Click "Get started" / Create a new app
Fill in details and finish
Next, create an OAuth client
Select "Web application"

Add an Authorized redirect URIs ``https://auth.yourdomain.com/oauth2/idpresponse``

In your GH repo add the google client id and google client secret as secrets.
```
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
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

This will create an output:
```
Outputs:

dynamodb_table_name = "terraform-state"
name_servers = tolist([
  "ns-000.awsdns-00.org",
  "ns-000.awsdns-00.co.uk",
  "ns-000.awsdns-00.com",
  "ns-000.awsdns-00.net",
])
s3_bucket_arn = "arn:aws:s3:::staging-terraform-state-aichat"
```
Next steps:
1. Copy the bucket name (``arn:aws:s3:::staging-terraform-state-XXXX``) into ``terraform/1-terraform.tf``, and update the region.
2. Add the ``name_servers`` to your domain registrar DNS 
3. Wait for the DNS settings to take effect.


```yaml
  # remote state configuration here
  backend "s3" {
    bucket         = "staging-terraform-state-XXXX" # update this to bucket name from terraform-remote-state
    key            = "infra/terraform.tfstate"
    region         = "us-east-1" # update this to match region in 0-locals.tf
    dynamodb_table = "terraform-state"
    encrypt        = true
  }
```




You need to request a quota increase from AWS for your EC2 limits. 
1. Go to the **AWS Console > Service Quotas > AWS Services > Amazon Elastic Compute Cloud (Amazon EC2)**.
2. Search for **"Running On-Demand Standard (A, C, D, H, I, M, R, T, Z) instances"**.
3. Select it and click **Request quota increase**. 
4. Request an increase to something like **32 or 64 vCPUs**. 


### 1. Spot Instance Quotas
* **Quota Name:** `All Standard (A, C, D, H, I, M, R, T, Z) Spot Instance Requests`
* **Current Limit:** 5 vCPUs
* **Recommended Increase:** 32 or 64 vCPUs

### 2. GPU Instance Quotas
* **Quota Name:** `Running On-Demand G and VT instances`
* **Current Limit:** 0 vCPUs
* **Recommended Increase:** 16 vCPUs (enough to run a couple of `g4dn.xlarge` instances)

### 3. Elastic IPs 
* **Quota Name:** `EC2-VPC Elastic IPs`
* **Current Limit:** 5
* **Recommended Increase:** 10




# Kubectl

### 1. Verify AWS credentials

```bash
aws sts get-caller-identity
```



### 2. List EKS clusters (optional)

```bash
aws eks list-clusters --region us-east-1
```


### 3. Update your kubeconfig

```bash
aws eks update-kubeconfig \
  --region us-east-1 \
  --name staging-main-cluster
```

This will:

* Create `~/.kube/config` if it doesn't exist.
* Add the EKS cluster configuration.
* Configure authentication through the AWS CLI.

### 4. Test access

```bash
kubectl cluster-info
```
