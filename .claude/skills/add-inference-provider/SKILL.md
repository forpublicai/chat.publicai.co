---
name: add-inference-provider
description: Complete step-by-step workflow for adding a new LLM model or inference provider to the Public AI platform across LiteLLM AI Gateway, AWS Secrets Manager, External Secrets Operator (ESO), Lago billing catalog, and OpenWebUI. Use this skill whenever adding, updating, or troubleshooting inference providers or models.
---

# Skill: Adding an Inference Provider & Model to Public AI

This guide is designed for an autonomous agent or developer working on the `chat.publicai.co` repository. It contains everything you need to know about the platform architecture, exact files to edit, prerequisites, and operational precautions.

---

## Repository Mental Model

Public AI operates an open-source inference utility on Amazon EKS deployed via Helm charts and Argo CD (GitOps):

1. **LiteLLM AI Gateway** (`platform` namespace, [`charts/platform/charts/litellm`](/charts/platform/charts/litellm)):
   - Unified OpenAI-compatible proxy and router.
   - Globs all model YAMLs from `charts/platform/charts/litellm/models/**/*.yaml`.
   - Dispatches requests to external inference partners (Infomaniak, CSCS, Featherless, AWS Bedrock, etc.).
   - Access is partitioned via `access_groups` (`api`, `chat`, `chat-private`).

2. **Secrets & External Secrets Operator (ESO)**:
   - Credentials are NOT stored in Git.
   - External Secrets Operator pulls API keys from AWS Secrets Manager and creates the Kubernetes Secret `litellm-secrets`.

3. **Lago Billing Engine** (`platform` namespace, [`charts/platform/charts/lago`](/charts/platform/charts/lago)):
   - Meters token usage.
   - The LiteLLM custom callback ([`custom_lago_callback.py`](/charts/platform/charts/litellm/custom_lago_callback.py)) automatically tracks prompt and completion tokens per model without requiring manual code changes.
   - Metric filters and package pricing are declared in [`charts/platform/lago-catalog.yaml`](/charts/platform/lago-catalog.yaml) and automatically synced to the Lago API on deploy via the `lago-catalog-syncer` Helm hook Job.

4. **OpenWebUI Chat Interface** (`chat` namespace, [`charts/chat`](/charts/chat)):
   - End-user chat UI at `chat.publicai.co`.
   - Models are declared in [`charts/chat/models.yaml`](/charts/chat/models.yaml) and automatically synced to PostgreSQL/Redis on deploy via the `config-syncer` Helm hook Job.

5. **Environments & GitOps**:
   - **Staging**: Deployed from branch `dev` in AWS region `us-east-1` (`api-internal.ai-staging.chat`, `chat.ai-staging.chat`, `argo.ai-staging.chat`).
   - **Production**: Deployed from branch `main` in AWS region `eu-central-2` (`api-internal.publicai.co`, `chat.publicai.co`, `argo.publicai.co`).

---

## ⚠️ Critical Rules & Gotchas (Read Before Making Changes!)

1. **MANDATORY PREREQUISITE: AWS Secrets Manager MUST be updated FIRST**:
   - You **MUST** add the provider's API key to AWS Secrets Manager **before** pushing code or syncing Argo CD.
   - **Why:** If `secrets.yaml` references a key that doesn't exist in AWS Secrets Manager, ESO will fail with `SecretSyncedError`. The target Kubernetes Secret will not be created/updated, LiteLLM pods will crash or fail to start, and the deployment will break.
2. **`access_groups` is Required on Every Model**:
   - Every model in `models/**/*.yaml` must have `model_info.access_groups` defined as a YAML list:
     - `["api"]`: Developer API only.
     - `["chat"]`: Chat UI only.
     - `["api", "chat"]`: Both developer API and Chat UI.
     - `["chat-private"]`: Internal RAG models (e.g. embeddings/rerankers).
3. **Automatic API Key Authorization**:
   - Models added to `access_groups: ["api"]` or `["chat"]` are **automatically authorized** for the master/developer API keys. You do **NOT** need to manually edit virtual keys in the LiteLLM UI.
4. **DO NOT edit `custom_lago_callback.py`**:
   - The Lago callback dynamically inspects LiteLLM's `/app/config.yaml` to discover model mappings automatically.
5. **DO NOT configure models in OpenWebUI Admin Panel**:
   - Model definitions in OpenWebUI are managed declaratively via [`charts/chat/models.yaml`](/charts/chat/models.yaml). The Helm `config-syncer` hook Job updates the database and clears the cache automatically.
6. **LiteLLM Deployment Restart**:
   - LiteLLM loads configuration into memory at startup. When deploying changes to models or secrets, you must perform a rollout restart of `deployment/litellm` in the `platform` namespace via Argo CD or `kubectl rollout restart`.

---

## Step-by-Step Procedure

### Step 0: Add Secret to AWS Secrets Manager (Prerequisite)

Before modifying any repository code, add the provider's API key (e.g. `MY_PROVIDER_API_KEY`) to AWS Secrets Manager in both regions:

- **Staging** (AWS Region: `us-east-1`):
  - Secret ID: `staging/aichat/litellm/manual-secrets`
- **Production** (AWS Region: `eu-central-2`):
  - Secret ID: `prod/publicai/litellm/manual-secrets`

**AWS CLI Example:**
```bash
# 1. Fetch current secret JSON (Staging)
aws secretsmanager get-secret-value \
  --region us-east-1 \
  --secret-id staging/aichat/litellm/manual-secrets \
  --query SecretString --output text > current_secrets.json

# 2. Add "MY_PROVIDER_API_KEY": "sk-..." to current_secrets.json

# 3. Update secret value
aws secretsmanager put-secret-value \
  --region us-east-1 \
  --secret-id staging/aichat/litellm/manual-secrets \
  --secret-string file://current_secrets.json
```

---

### Step 1: Create or Update LiteLLM Model YAML

Create a new file under `charts/platform/charts/litellm/models/<vendor>/<model-name>.yaml`.

- Where multiple providers host the same model, list them all under `models:` with the identical `model_name` for load balancing and supplier failover.
- Configure `fallbacks:` with at least 2 independent model fallbacks.

**Template:**
```yaml
environments:
  - staging
  - prod
models:
  # Primary endpoint
  - model_name: vendor/my-model-name
    litellm_params:
      model: openai/vendor/my-model-name
      api_base: https://api.provider.com/v1
      api_key: os.environ/MY_PROVIDER_API_KEY
      supports_vision: false
      temperature: 1.0
      top_p: 0.95
      max_tokens: 16384
    model_info:
      input_cost_per_token: 0.00000085
      output_cost_per_token: 0.00000040
      access_groups: ["api", "chat"]

  # Secondary failover endpoint
  - model_name: vendor/my-model-name
    litellm_params:
      model: openai/vendor/my-model-name
      api_base: https://backup-api.provider.com/v1
      api_key: os.environ/BACKUP_PROVIDER_API_KEY
    model_info:
      input_cost_per_token: 0.00000085
      output_cost_per_token: 0.00000040
      access_groups: ["api", "chat"]

fallbacks:
  - speakleash/Bielik-11B-v3.0-Instruct
```

---

### Step 2: Wire Secret into Kubernetes via ESO

1. **Update [`charts/platform/charts/litellm/templates/secrets.yaml`](/charts/platform/charts/litellm/templates/secrets.yaml)**:
   - Add template mapping under `spec.target.template.data`:
     ```yaml
     my_provider_api_key: '{{ "{{ .MY_PROVIDER_API_KEY }}" }}'
     ```
   - Add remote reference under `spec.data`:
     ```yaml
     - secretKey: MY_PROVIDER_API_KEY
       remoteRef:
         key: {{ .Values.secrets.manualSecretsName }}
         property: MY_PROVIDER_API_KEY
     ```

2. **Update [`charts/platform/charts/litellm/templates/deployment.yaml`](/charts/platform/charts/litellm/templates/deployment.yaml)**:
   - Expose the environment variable to the container under `spec.template.spec.containers[0].env`:
     ```yaml
     - name: MY_PROVIDER_API_KEY
       valueFrom:
         secretKeyRef:
           name: {{ .Values.secrets.name }}
           key: my_provider_api_key
           optional: true
     ```

---

### Step 3: Add Model to Lago Billing Catalog

Edit [`charts/platform/lago-catalog.yaml`](/charts/platform/lago-catalog.yaml):

1. **Register Model in Metric Filter**:
   Add the `model_name` under `billable_metrics[public_ai_models].filters[model].values`:
   ```yaml
   billable_metrics:
     - code: public_ai_models
       filters:
         - key: model
           values:
             - vendor/my-model-name
   ```

2. **Add Plan Pricing**:
   Under `plans[pay_as_you_go].charges[...].filters`, add the pricing for 1,000-token packages (`amount = cost_per_token * 1000`):
   ```yaml
   # Input tokens
   - model: vendor/my-model-name
     type: input
     amount: "0.00085"
     package_size: 1000
     free_units: 0
   # Output tokens
   - model: vendor/my-model-name
     type: output
     amount: "0.00040"
     package_size: 1000
     free_units: 0
   ```

---

### Step 4: Add to OpenWebUI (If `chat` Access Group)

If the model includes `"chat"` in `access_groups`, declare it in [`charts/chat/models.yaml`](/charts/chat/models.yaml):

```yaml
models:
  - id: vendor/my-model-name # Must match LiteLLM model_name
    name: Model Display Name
    base_model_id: null
    visibility: public # "public" for all users, or "private" for admin-only
    meta:
      description: Description of the model and its compute sponsors.
      profile_image_url: data:image/webp;base64,... # WebP base64 data URI or image URL
      capabilities:
        file_context: true
        vision: false
        file_upload: true
        web_search: true
        image_generation: false
        code_interpreter: true
        citations: true
        status_updates: true
        builtin_tools: true
      builtinTools:
        time: true
        memory: true
        chats: true
        notes: true
        knowledge: true
        channels: true
        web_search: true
        image_generation: false
        code_interpreter: true
      filterIds: []
    params:
      system: |
        Today's date is {{CURRENT_DATE}}

        You are Model Name, an open AI model deployed by the Public AI Inference Utility.
```

---

### Step 5: Run Pre-deploy Validation

Always run the code checker locally to confirm everything matches:

```bash
python3 health-check/model-code-check.py
```

The script verifies:
- YAML syntax and structure
- Presence of required `access_groups`
- Secret wiring from `models/**/*.yaml` -> `secrets.yaml` -> `deployment.yaml`
- Lago catalog consistency (model registered, and prices match `cost_per_token * 1000`)
- Absence of circular fallbacks or broken references

Ensure the command exits with `STATUS: SUCCESS (No blocking errors)`.

---

### Step 6: Deploy & Restart LiteLLM

1. **Deploy to Staging**:
   - Push or merge changes to the **`dev`** branch.
   - Wait for Argo CD to sync.
   - **Restart LiteLLM deployment**:
     ```bash
     aws eks update-kubeconfig --region us-east-1 --name staging-main-cluster
     kubectl rollout restart deployment/litellm -n platform
     kubectl rollout status deployment/litellm -n platform
     ```
2. **Verify Staging**:
   ```bash
   python health-check/litellm.py --staging
   ```
   - Test in the playground: `https://api-internal.ai-staging.chat`
   - Test in Chat UI: `https://chat.ai-staging.chat`
3. **Deploy to Production**:
   - Open a PR from `dev` to **`main`** and merge.
   - Once synced by Argo CD:
     ```bash
     aws eks update-kubeconfig --region eu-central-2 --name prod-main-cluster
     kubectl rollout restart deployment/litellm -n platform
     kubectl rollout status deployment/litellm -n platform
     ```
   - Verify:
     ```bash
     python health-check/litellm.py
     ```

