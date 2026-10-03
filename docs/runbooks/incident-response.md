# Incident Response Runbook — Public AI Inference Utility

Scope: production services deployed from this repo (Argo apps under `argo/environments/prod`,
Helm charts under `charts/`) plus the Zuplo gateway (`platform.publicai.co`, deployed separately).

## Severity levels

| Sev | Definition | Example | Response target |
|---|---|---|---|
| SEV1 | Platform-wide outage or billing corruption; users cannot chat or are billed incorrectly | LiteLLM down, Lago double-charging | Ack < 15 min, mitigate < 1h |
| SEV2 | Partial degradation; one provider/model or one gateway feature down, workarounds exist | One model provider down, Zuplo 5xx on one route | Ack < 30 min, mitigate < 4h |
| SEV3 | Minor/cosmetic or single-user issue, no SLA impact | One synthetic probe flapping, non-critical dashboard broken | Next business day |

## First-response checklist (all incidents)

1. Check Grafana (`argo/environments/prod/grafana-values.yaml` deploys Grafana) and Prometheus
   dashboards, in particular the `health-check-dashboard` configmap
   (`charts/monitoring-resources/templates/health-check-dashboard-configmap.yaml`).
2. Check the `health-check` service's own probe output — it runs scheduled checks against
   LiteLLM, Zuplo, HuggingFace, and each model supplier (`health-check/litellm.py`,
   `health-check/zuplo.py`, `health-check/huggingface.py`, `health-check/suppliers.py`).
3. Check ArgoCD for out-of-sync or failed apps (`argo/apps/{staging,production}`, `argo/environments/prod`).
4. Post in the incident Slack channel and note start time; LiteLLM/ArgoCD alerts route via the
   `SLACK_WEBHOOK_URL` (LiteLLM) and ArgoCD notifications chart (`charts/monitoring-resources/templates/argocd-notifications-secret.yaml`).
5. Declare severity per the table above and assign an incident owner.

## LiteLLM proxy down

LiteLLM (`charts/platform/charts/litellm`) is the single point through which all model calls,
Open WebUI, and the Zuplo gateway pass — its outage is platform-wide (SEV1).

- **Where to look**: `health-check/litellm.py` probe result; pod status for the `litellm`
  deployment (`charts/platform/charts/litellm/templates/deployment.yaml`); Postgres
  (`DATABASE_URL`) and Redis (`REDIS_URL`/`REDIS_HOST`) connectivity, since LiteLLM depends on both.
- **Checks**: `kubectl get pods -n <platform namespace>`, `kubectl logs` on the litellm
  deployment, confirm the ExternalSecret `litellm-secrets` synced (external-secrets.io status),
  confirm DB/Redis are reachable.
- **Likely causes**: bad config push (models config lives in `charts/platform/charts/litellm/models/*.yaml`
  + `configmap.yaml`), DB/Redis outage, upstream `BerriAI/litellm` sync
  (`.github/workflows/1_publicai_sync_and_build.yml` in the litellm repo) introducing a breaking change.
- **Mitigation**: roll back to the previous Argo-synced Helm revision / previous litellm image tag;
  if config-related, revert the offending `models/*.yaml` or `configmap.yaml` change and re-sync via ArgoCD.

## A model provider is down (e.g. SEA-LION, Apertus/Infomaniak, Featherless, Bielik, Nexbit, vLLM)

SEV2 unless it is the only model serving a critical customer (escalate to SEV1 case-by-case).

- **Where to look**: `health-check/suppliers.py` probe output (checks each provider key/model);
  the specific model's file under `charts/platform/charts/litellm/models/<org>/<model>.yaml` for
  which provider/API key it uses.
- **Checks**: confirm the provider's own status page; verify the relevant API key
  (`SEALION_API_KEY`, `INFOMANIAK_API_KEY`, `FEATHERLESS_API_KEY`, `BIELIK_API_KEY`,
  `NEXBIT_API_KEY`, `PHOENIQS_API_KEY`, `VLLM_API_KEY_INTEL`) hasn't expired/rotated without
  updating AWS Secrets Manager.
- **Mitigation**: if LiteLLM has a fallback model configured, confirm traffic is routing there;
  otherwise disable/hide the affected model in the model-list service output
  (`model-list/main.py`) so clients don't select it, and communicate to affected users if the
  model is customer-facing.

## Lago billing failing

SEV1 if usage events are being dropped (silent revenue loss) or double-counted (customer
overcharge); SEV2 if only the dashboard/UI is affected.

- **Where to look**: `charts/platform/charts/litellm/custom_lago_callback.py` (emits per-token
  usage events, event code `public_ai_models`) and the Zuplo modules that read/write wallet state
  (`platform.publicai.co/modules/wallet-balance-handler.ts`, `wallet-topup.ts`,
  `customer-provisioning.ts`, `set-litellm-headers.ts`).
- **Checks**: confirm `LAGO_API_BASE` (internal `platform-api-svc.platform.svc.cluster.local:3000`)
  is reachable from both the LiteLLM pod and the Zuplo gateway; check Lago's own service health;
  check `LAGO_API_KEY` validity in both the AWS Secrets Manager copy (chat.publicai.co) and the
  Zuplo environment copy (platform.publicai.co) — these are two separate copies of the same key.
- **Mitigation**: if Lago itself is down, LiteLLM calls should still succeed (billing callback
  failures should not block inference) — verify this fails open, not closed; queue/replay missed
  usage events once Lago recovers if events were dropped. Freeze wallet auto-topup
  (`AUTO_TOPUP_CONFIG` in Zuplo) if balances are unreliable.

## Zuplo gateway errors (platform.publicai.co)

SEV1 if it blocks all third-party API traffic; SEV2 if scoped to one route/handler.

- **Where to look**: Zuplo's own dashboard/logs (deployed outside this repo, via Zuplo's git
  integration on `forpublicai/platform.publicai.co`); the specific module implicated
  (`modules/api-keys.ts`, `set-litellm-headers.ts`, `bedrock-guardrail-policy.ts`,
  `user-rate-limiter.ts`, billing/wallet handlers).
- **Checks**: `health-check/zuplo.py` probe output; confirm `ZP_DEVELOPER_API_KEY`,
  `AUTH0_DOMAIN`/`AUTH0_CLIENT_ID`/`AUTH0_CLIENT_SECRET`, and `LITELLM_DEVELOPER_API_KEY` are
  valid in the Zuplo environment; check whether the error is at the gateway edge or in the
  downstream LiteLLM call it proxies.
- **Mitigation**: Zuplo deploys are managed by Zuplo's own git-triggered pipeline (no
  `.github/workflows` in that repo) — revert the last merged commit on
  `forpublicai/platform.publicai.co` main to roll back; there is no confirmed staging environment
  for this repo, so treat every rollback as production-impacting.

## Auth0 outage

SEV1 for new logins/signups and any Zuplo developer-portal auth; existing Open WebUI sessions
may continue to work until token refresh is required.

- **Where to look**: Open WebUI OIDC config (`OAUTH_CLIENT_ID`/`OAUTH_CLIENT_SECRET`/
  `OPENID_PROVIDER_URL` in `charts/chat/charts/open-webui/templates/secrets.yaml`) for
  signed-in-user login; `platform.publicai.co/modules/auth0-helper.ts` and
  `customer-provisioning.ts` for developer-portal auth (Auth0 Management API calls).
- **Checks**: Auth0 status page; confirm this is Auth0-side vs a misconfigured
  `AUTH0_DOMAIN`/client credential.
- **Mitigation**: no bypass — Auth0 is a hard dependency for both signed-in chat users and
  developer-portal API key provisioning. Communicate expected downtime; existing valid sessions
  and already-issued API keys should keep working since they don't re-hit Auth0 per request.

## Escalation

If unresolved past the mitigation target for the declared severity, escalate to Sean (primary
infra owner/maintainer of this repo) and post a status update in the incident channel every 30
minutes for SEV1, hourly for SEV2.
