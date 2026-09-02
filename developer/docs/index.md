
# Contents
1. [Accounts and UIs](accounts-and-uis.md)
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

please read this document: [Accounts and UIs](accounts-and-uis.md)

# Deploy to production
Anything pushed to the ``dev`` branch will be deployed to staging
Any changes pushed to the ``main`` branch will be deployed to production
You can view the sync process on argo.ai-staging.chat and argo.publicai.co respectively
If you want direct access to the k8s cluster see below to get access

## Note
Some small config changes might not be applied automatically, in this case you may need to restart the pods or services manually.

```bash
kubectl rollout restart deployment/litellm -n platform
kubectl rollout restart deployment/openwebui -n chat
```

## Generate AWS IAM user access key and secret key
1. Log in to AWS
2. Search for IAM in the search bar and go to IAM
3. Go to IAM users
4. Choose a user
    1. publicai-readonly : gives read only access to AWS and the cluster, use this for debugging
    2. publicai-write-cluster : gives read only access to AWS and the cluster, use this for deployment
5. Click on the user and go to the Security credentials tab
6. Click on Create access key (if you need to deactivate and delete existing keys, it is safe to do so)
7. Choose CLI
8. Enter a description and click on Create Access Key
9. Now in your terminal type ``aws configure`` and enter the access key and secret key from the console
10. *You are now connected to AWS, next we need to connect to the cluster*
11. Run the commands below:

*Staging*
```bash
aws sts get-caller-identity
aws eks list-clusters --region us-east-1
aws eks update-kubeconfig --region us-east-1 --name staging-main-cluser
kubectl config current-context
```
*Production*
```bash
aws sts get-caller-identity
aws eks list-clusters --region eu-central-2
aws eks update-kubeconfig --region eu-central-2 --name prod-main-cluser
kubectl config current-context
```

## Tests
After deployment run the tests (secrets will be in doppler):

```bash
cd health-check
python suppliers.py # this tests our providers are working
python litellm.py # this tests our litellm is working
```

