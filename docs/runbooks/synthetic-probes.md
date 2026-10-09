# Synthetic probes

The GitHub Actions probe checks publicai.co, chat.publicai.co, platform.publicai.co, the unauthenticated API models endpoint, and publicai.network every 15 minutes. It records HTTP status and latency in `probe-results.json`; an HTTP response below 500 counts as healthy for the API endpoint, including 401/403.

## Add an endpoint

Add a URL and inclusive expected-status range to `scripts/probes/endpoints.json`. Keep the timeout at 10 seconds. Add or update tests if the classification needs special handling.

## On an alert

Open the scheduled workflow run, inspect the probe-results artifact, and check the endpoint independently before escalating. A single open `probe-failure` issue is reused for later scheduled failures. Resolve the underlying issue and close the alert issue when appropriate.

This is an external black-box check and complements, rather than replaces, Prometheus/Grafana internal metrics and alerting.

To disable the checks, remove or comment out the `schedule` trigger in `.github/workflows/synthetic-probes.yml` (or disable the workflow in GitHub Actions).
