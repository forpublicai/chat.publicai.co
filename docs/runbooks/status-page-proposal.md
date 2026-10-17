# Proposal: public status page and alert routing

Status: proposal, not implemented. Builds on the synthetic probes in #57.

## Why
Enterprise customers expect a public status page and a known path from "probe failed" to "a human knows". We currently have neither.

## Alert routing (in #57)
- A scheduled probe failure opens a GitHub issue labelled `probe-failure` (deduplicated: if one is open it adds a comment).
- Proposed next step: route that issue to Slack via the GitHub Slack app (`/github subscribe forpublicai/chat.publicai.co issues +label:probe-failure`) in the infra channel. No new secrets, no code.
- Escalation: owner on call = Sean (backend/LiteLLM), Joseph (platform/Zuplo). See docs/runbooks/incident-response.md.

## Status page options
| Option | Cost | Effort | Notes |
|---|---|---|---|
| A. GitHub Pages page fed by the probe workflow | free | ~1 day | Workflow commits `status.json` (last 90 days, per endpoint) to a `status` branch; a static HTML page renders uptime bars. Fully in our control, no vendor. |
| B. Upptime (open-source, GitHub Actions) | free | ~half day | Mature template, separate repo `forpublicai/status`; duplicates our probes. |
| C. Hosted (Better Stack / Instatus free tier) | free to ~$20/mo | hours | Fastest, adds a vendor and an account to manage. |

Recommendation: A, at `status.publicai.co` (CNAME to GitHub Pages). It reuses #57 and keeps zero runtime dependencies on production.

## Decisions needed
1. Which option (default A).
2. Who owns the `status.publicai.co` DNS record.
3. Which Slack channel receives `probe-failure` alerts.
