# Monitoring & SLO Proposal (draft for Sean)

> **Status: PROPOSAL, not yet implemented or agreed.** Written to support the SLA-readiness goal;
> please review/adjust targets and ownership before treating any of this as committed.

## Context

We already have: Prometheus + Grafana (`argo/environments/{staging,prod}/{prometheus,grafana}-values.yaml`,
`charts/monitoring-resources`), a `health-check` FastAPI service that actively probes LiteLLM,
Zuplo, HuggingFace, and each model supplier (`health-check/*.py`), and a Grafana dashboard
configmap for it. There is no public status page and no formally published SLOs yet.

## Proposed SLOs

| Surface | SLO | Notes |
|---|---|---|
| `platform.publicai.co /v1/chat/completions` | 99.5% monthly availability (5xx-free responses) | Primary external developer-facing endpoint |
| `platform.publicai.co /v1/models`, `/v1/completions` | 99.5% monthly availability | Same gateway, lower traffic |
| chat.publicai.co (signed-in chat) | 99.5% monthly availability | End-user facing; depends on LiteLLM + Open WebUI + DB/Redis |
| Latency | p95 < 3s time-to-first-token for chat completions (excludes model generation time budget, which varies by provider) | Needs baselining — no current latency SLO exists |
| Per-provider availability | Tracked but not SLO'd individually | Providers are third-party; we can only alert, not guarantee |

These are starting proposals; actual numbers should be set from ~30 days of real health-check
metrics before being called commitments.

## Synthetic probes (build on existing health-check service)

The `health-check` service already does most of this — proposal is to formalize its cadence and
alerting rather than build new tooling:

- Run `health-check/litellm.py` and `health-check/zuplo.py` on a fixed interval (`CHECK_INTERVAL_SECONDS`,
  currently configurable) against production, hitting `/v1/models` as a cheap liveness probe and
  one lightweight `/v1/chat/completions` call against a stable model to catch auth/billing wiring
  breakage, not just gateway liveness.
- Extend `health-check/suppliers.py` results to feed the SLO dashboard per-provider, so a single
  provider outage is visibly distinguished from a platform-wide outage.
- Export probe results as Prometheus metrics (there's already a Grafana dashboard configmap for
  health-check — confirm it's wired to real metrics, not just logs) so alerting rules can use them.

## Alerting

- Route SEV1/SEV2 alerts (per `incident-response.md`) to Slack via the existing
  `SLACK_WEBHOOK_URL` (currently used by LiteLLM) and the ArgoCD notifications chart
  (`charts/monitoring-resources/templates/argocd-notifications-secret.yaml`) — proposal: reuse
  one shared "prod-incidents" Slack channel for all three (LiteLLM, ArgoCD sync failures,
  health-check probe failures) rather than three separate channels.
- Alert thresholds proposal: page on 2 consecutive failed health-check probes (~2x
  `CHECK_INTERVAL_SECONDS`) for LiteLLM/Zuplo; single-provider failures alert but don't page.

## Public status page (options, not yet decided)

1. **Managed status page (e.g. Better Stack, Statuspage.io, Instatus)** — fastest to stand up,
   can ingest webhook/API pings from the existing health-check service; low engineering cost.
2. **Self-hosted status page (e.g. Cachet, Gatus)** — more control, one more service to run and
   patch on infra that's already single-maintainer (bus-factor risk noted in repo analysis).
3. **Static page generated from health-check results**, published via the same pipeline as
   `publicai.co` — cheapest, least featureful (no historical uptime graphs without extra work).

Recommendation to evaluate: option 1, pointed at the health-check service's probe results, is the
lowest-effort path to a credible public status page for the enterprise-SLA goal; final choice is
Sean's call given who would own on-call for it.

## Open items for Sean

- Confirm/adjust SLO numbers above once we have real baseline data.
- Decide alert routing (shared vs per-component Slack channels) and who is on-call.
- Pick a status-page option (or defer) and who owns keeping it accurate.
