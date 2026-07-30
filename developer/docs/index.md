
# Contents
1. [Accounts and UIs](account-and-uis.md)
1. [Deploy to production](#deploy-to-production)
1. [Tests](#tests)
1. [Add an inference provider](add-inference-provider.md)
1. [Hugging face connector](hugging-face-connector.md)
1. [Architectural overview](overview.md)


# Accounts and UIs
If you want to use the UIs for any service like 
- LiteLLM 
- Monitoring
- Billing application
- Authenticated 
- and more...

please read this document: [Accounts and UIs](account-and-uis.md)

# Deploy to production
1. Clone this repo
2. Download the .env file from doppler and place in the root directory
3. Install AWS CLI [here](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html)
4. Generate AWS IAM user access key and secret key
5. Run AWS configure and enter the access key and secret key
6. Deploy to production


## Generate AWS IAM user access key and secret key
1. Log in to AWS
2. Search for IAM in the search bar and go to IAM
3. Go to IAM users
4. Choose a user
    1. read-only : gives read only access to AWS and the cluster, use this for debugging
    2. currentai-cluster-deploy : gives full access to AWS and the cluster, use this for deployment
5. Click on the user and go to the Security credentials tab
6. Click on Create access key (if you need to deactivate and delete existing keys it is safe to do so)
7. Choose CLI
8. Enter a description and click on Create access key
9. Now in your terminal type ``aws configure`` and enter the access key and secret key from the console
10. *You are now connected to AWS, next we need to connect to the cluster*
11. Run the commands below:

```bash
aws sts get-caller-identity
aws eks list-clusters --region eu-central-2

aws eks update-kubeconfig --region eu-central-2 --name publicai-eks
  
kubectl config current-context
```

11. *You are now connected to the cluster, next we need to deploy to production*

## web.sh deployer

Deployments are done y running ``./web.sh``

1. Check your code is valid by running ``./web.sh --validate``
2. Do a dry run by running ``./web.sh --deploy --dry-run``
3. Deploy by running ``./web.sh --deploy``
4. After deployment check your changes have deployed (at least check if pods have restarted etc..), not all yaml changes trigger a restart of pods or services.
5. If changes are not applied you may need to restart the pods or services manually.

```bash
kubectl rollout restart deployment/litellm -n web-services
kubectl rollout restart deployment/openwebui -n web-services
```

## Tests
After deployment run the tests:

```bash
cd developer/test
python providers.py # this tests our providers are working
python litellm.py # this tests our litellm is working
```

