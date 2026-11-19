# Claude Code Project Guidelines for Public AI

Welcome to the **Public AI** infrastructure repository (`chat.publicai.co`). This repository contains the complete Infrastructure-as-Code (Terraform), Kubernetes Helm charts, and Argo CD GitOps manifests powering Public AI's inference utility, billing engine, and chat interface on Amazon EKS.

---

## Skills & Key Workflows

For adding or updating inference providers and models, follow the dedicated skill:
- **Skill File:** [`.claude/skills/add-inference-provider/SKILL.md`](.claude/skills/add-inference-provider/SKILL.md)
- **Detailed Documentation:** [`developer/docs/add-inference-provider.md`](developer/docs/add-inference-provider.md)
- **Architecture Overview:** [`developer/docs/overview.md`](developer/docs/overview.md)

---

## Core Platform Architecture

1. **LiteLLM AI Gateway** (`platform` namespace, `charts/platform/charts/litellm/`):
   - Proxies LLM inference requests to external suppliers (Infomaniak, CSCS, Featherless, Bedrock, etc.).
   - Model definitions live under `charts/platform/charts/litellm/models/<vendor>/<model>.yaml`.
   - Partitioned by `access_groups`: `["api"]`, `["chat"]`, `["api", "chat"]`, and `["chat-private"]`.
   - **Key Detail:** Models assigned to `api` or `chat` access groups are **automatically authorized** for the developer/chat API keys. You do **not** need to manually modify virtual keys in the LiteLLM UI.

2. **External Secrets Operator (ESO)**:
   - Syncs credentials from AWS Secrets Manager into Kubernetes Secrets (`litellm-secrets`).
   - Defined in `charts/platform/charts/litellm/templates/secrets.yaml`.

3. **Lago Billing System** (`platform` namespace, `charts/platform/charts/lago/`):
   - Token metering events are automatically emitted by `custom_lago_callback.py` (which parses `/app/config.yaml` dynamically; **never edit this callback manually**).
   - Metrics and plan pricing are declared in `charts/platform/lago-catalog.yaml` and synced to the Lago API on deploy via the `lago-catalog-syncer` Helm hook Job.

4. **OpenWebUI** (`chat` namespace, `charts/chat/`):
   - End-user chat interface.
   - Models, descriptions, avatars, system prompts, and capabilities are declared in `charts/chat/models.yaml` (**never configure models in the OpenWebUI web admin panel**).
   - Synced to PostgreSQL and Redis on deploy via the `config-syncer` Helm hook Job.

---

## ⚠️ Critical Rules to Prevent Outages

1. **AWS Secrets Manager FIRST**: Always add the secret to AWS Secrets Manager (`staging/aichat/litellm/manual-secrets` in `us-east-1`, `prod/publicai/litellm/manual-secrets` in `eu-central-2`) **before** committing or deploying code. If ESO cannot find the remote key, secret synchronization fails and blocks LiteLLM pods from starting.
2. **Access Groups Required**: Every LiteLLM model definition must include `model_info.access_groups: ["api"]`, `["chat"]`, or `["api", "chat"]`.
3. **Always Validate Before Pushing**: Run `python3 health-check/model-code-check.py` to ensure zero syntax, secret wiring, or pricing mismatches.
4. **Restart LiteLLM Post-Deploy**: LiteLLM caches configuration in memory at boot time. After Argo CD syncs, perform a rollout restart (`kubectl rollout restart deployment/litellm -n platform` or via Argo CD UI).

---

## Common Developer Commands

```bash
# 1. Validate all model YAMLs, secret pipelines, and Lago pricing
python3 health-check/model-code-check.py

# 2. Run LiteLLM health check on Staging
python health-check/litellm.py --staging

# 3. Run LiteLLM health check on Production
python health-check/litellm.py

# 4. Rollout restart LiteLLM (Staging - us-east-1)
aws eks update-kubeconfig --region us-east-1 --name staging-main-cluster
kubectl rollout restart deployment/litellm -n platform

# 5. Rollout restart LiteLLM (Production - eu-central-2)
aws eks update-kubeconfig --region eu-central-2 --name prod-main-cluster
kubectl rollout restart deployment/litellm -n platform
```

