# LiteLLM billing/auth glue tests

Unit tests for the two custom LiteLLM plugins that back budget provisioning
and Lago billing:

- `charts/platform/charts/litellm/custom_auth.py`
- `charts/platform/charts/litellm/custom_lago_callback.py`

## What's covered

- `custom_auth.py`: new-user budget provisioning, existing-user no-op,
  provisioning failure handling, unexpected/network errors, header
  detection for OpenWebUI vs Zuplo requests, non-completion paths being
  skipped, and falling back to normal API-key auth on any error.
- `custom_lago_callback.py`: model-name normalization, subscription-id
  extraction (header vs metadata fallback vs missing), Lago event payload
  shape, splitting prompt/completion tokens into separate input/output
  events (sync and async paths), skipping when there's no subscription id
  or zero tokens, and swallowing Lago HTTP failures so billing outages
  never break a chat request.

## What's NOT covered

- No real network calls to LiteLLM or Lago — `httpx.AsyncClient` and the
  handler's `.post()` are mocked everywhere.
- No test against a real `litellm` package; a minimal stub of the
  `litellm`/`fastapi`/`httpx` surface these two files actually touch lives
  in `tests/litellm_glue/../../conftest.py` (repo-root `conftest.py`), so
  behaviour of the real upstream LiteLLM proxy itself is out of scope.
- No coverage of the Zuplo gateway modules or `model-list` service — only
  the two LiteLLM glue files described above.
- No load/perf/integration testing against a live Lago instance.

## How to run

```bash
pip install -r tests/litellm_glue/requirements-test.txt
pytest tests/litellm_glue -v
```

Run from the repo root — `conftest.py` there puts
`charts/platform/charts/litellm` on `sys.path` and installs the stub
modules before the plugin files are imported.

For review: @sean (infra maintainer) — please check the stubs in
`conftest.py` accurately reflect the real `litellm` surface your fork
relies on.
