# Log in to cluster

You will need to authenticate AWS CLI tool and get an auth session into kubectl.
You can do that by follwing the docs here: [how to log in](index.md#deploy-to-production)

# Edit code
## Add API Key to LiteLLM

Working in ``charts/web_services/charts/litellm/templates/deployment.yaml``

Add a section to ``env`` for the API key.

```yaml
          env:
            - name: NEW_PROVIDER_API_KEY
              valueFrom:
                secretKeyRef:
                  name: {{ .Values.secrets.name }}
                  key: new_provider_api_key
```
## Create a new model endpoint and pricing for LiteLLM
Working in ``charts/web_services/charts/litellm/values.yaml``

```yaml
  models:
    - model_name: new-provider/apertus-8b-instruct
      litellm_params:
        model: openai/inference-apertus-8b
        api_base: https://api.newprovider.com/v1
        api_key: "os.environ/NEW_PROVIDER_API_KEY"
        supports_vision: true  
        weight: 20
        temperature: 0.8
        top_p: 0.9
        max_tokens: 16384
      model_info:
        input_cost_per_token: 0.00000010  # $0.10 per 1M tokens
        output_cost_per_token: 0.00000020  # $0.20 per 1M tokens

...
# Also add a line to declare the secrets configuration:
secrets:
  name: litellm-secrets
  litellmMasterKey: ""
  litellmSaltKey: ""
  ...
  new_provider_api_key: ""
```

In ``charts/web_services/charts/litellm/templates/secrets.yaml``
Add the secret

```yaml
...
  infomaniak_api_key: {{ .Values.secrets.infomaniakApiKey | quote }}
  deepinfra_api_key: {{ .Values.secrets.deepinfraApiKey | quote }}
  phoeniqs_api_key: {{ .Values.secrets.phoeniqsApiKey | quote }}
  bielik_api_key: {{ .Values.secrets.bielikApiKey | quote }}
...
```

## Add the API key to the deployment script

``web.sh``
This part of the script checks for missing env vars
```bash
    local required_vars=(
        "LICENSE_KEY"
        "WEBUI_SECRET_KEY"
        "OWUI_DATABASE_URL"
        ...
        "NEW_PROVIDER_API_KEY"
```

```bash
# Function to deploy web services
deploy_services() {
    echo "🔧 Building web services dependencies..."
    helm dependency build charts/web_services/

    echo "📦 Deploying web services with Lago billing..."
    helm upgrade --install web-services charts/web_services/ \
        -n web-services \
        --create-namespace \
        --set open-webui.secrets.licenseKey="$LICENSE_KEY" \
        --set open-webui.secrets.webuiSecretKey="$WEBUI_SECRET_KEY" \
        ...
        --set litellm.secrets.newProviderApiKey="$NEW_PROVIDER_API_KEY"
```

## Configure the callback to Lago billing engine
Working in ``charts/web_services/charts/litellm/custom_lago_callback.py``
```bash
    def _normalize_model_name(self, model: str) -> str:
        """
        Normalize model names to match Lago billing codes.
        Maps internal LiteLLM model names to user-facing model names.
        """
        # Model name mapping: litellm model -> lago billing name
        model_mapping = {
            # Apertus models (various endpoints with version suffixes)
            "Apertus-8B-Instruct-2509": "swiss-ai/apertus-8b-instruct",
            "swiss-ai/Apertus-8B-Instruct-2509": "swiss-ai/apertus-8b-instruct",
            "apertus-8b-instruct": "swiss-ai/apertus-8b-instruct",
            
            "NewProvider-8B-Instruct-2509": "new-provider/apertus-8b-instruct",
```

# Deploy the code

## Check changes
1. Validate the code ``./web.sh --validate``
1. Run this to see if code is edited in correct places ``python health-check/code_check_endpoint.py``

## Deploy
1. Then do a dry run ``./web.sh --deploy --dry-run``
1. Then do a real deploy ``./web.sh --deploy``
1. Then watch pods deploy ``watch -n 2 kubectl get pods -n web-services`` Check litellm is a new version, some small changes might not trigger a restart, if that is the case do a restart rollout on the deployment.

## Test
1. Once all rolled out test litellm ``python health-check/litellm.py``, check that you see all the models you expect to and they all return a token.

# Configure Apps

## Configure LiteLLM
To allow zuplo to access the new models they need to be added to the developer portal API key allowed list.

Go to the LiteLLM UI > Virtual Keys. Open the Developer Portal Master Key > go to Edit > Select the new models from the list.

![litellm](litellm.jpg)

## Configure OpenWebUI

Go to the OpenWebUI admin panel and configure.
![openwebui-admin](openwebui-admin.png)

## Check Lagos configuration
Cofirm Lagos has detected the model and pricing.

![lagos-admin.png](lagos-admin.png)


# Deploy to Hugging face
Read the hugging face docs here: [hugging face](huggingface.md)

