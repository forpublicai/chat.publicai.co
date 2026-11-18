# Spain reasoning stream reproduction

On chat.publicai.co, a first-turn prompt to Spain such as “Reply with just the number: 17 plus 25.” can display reasoning prose and a literal closing `</think>` before the answer. The JSON export preserves the malformed text in the ordinary assistant message. Tool-assisted responses can show the same symptom before or after the tool result.

This fixture recreates that response shape with synthetic text. It runs Open WebUI v0.12.5 and upstream LiteLLM v1.92.0, matching the tracked version pins. The LiteLLM package here is the upstream build. Production uses a custom image. The fixture verifies behavior when the supplier has already emitted the malformed shape. Its input is synthetic, so it cannot establish where production first loses the opening delimiter.

## Run locally

Run each of the first three blocks in a separate terminal from the directory containing this README. Keep these services bound to loopback. The local Open WebUI instance uses a disposable data directory and authentication is disabled for the fixture.

```sh
python3 mock.py
```

```sh
uv run --no-project --python 3.12 --with 'litellm[proxy]==1.92.0' \
  litellm --host 127.0.0.1 --port 18744 --config gateway.yaml
```

```sh
audit_data=$(mktemp -d)
DATA_DIR="$audit_data" WEBUI_AUTH=False ENABLE_OLLAMA_API=False \
  OPENAI_API_BASE_URL=http://127.0.0.1:18744/v1 OPENAI_API_KEY=local-fixture-key \
  WEBUI_SECRET_KEY=local-fixture-only OFFLINE_MODE=True HF_HUB_OFFLINE=1 \
  ENABLE_VERSION_UPDATE_CHECK=False ENABLE_TITLE_GENERATION=False \
  ENABLE_TAGS_GENERATION=False ENABLE_FOLLOW_UP_GENERATION=False \
  uv run --no-project --python 3.12 --with open-webui==0.12.5 \
  open-webui serve --host 127.0.0.1 --port 18743
```

Run the browser check with Node and Google Chrome installed. The npm dependency is installed outside the checkout.

```sh
audit_node=$(mktemp -d)
npm --prefix "$audit_node" install --no-audit --no-fund playwright@1.65.1
NODE_PATH="$audit_node/node_modules" node browser.cjs
```

The browser check sends a prompt to all three mock models and checks both the rendered response after reload and the persisted output items.

| Input | Expected observation on the pinned build |
| --- | --- |
| Reasoning-like prose and a closing tag only | Ordinary answer contains the raw marker. |
| Opening and closing tags split across chunks | Reasoning and answer are separate output items. |
| Structured reasoning delta followed by answer text | Reasoning and answer are separate output items. |

For the eventual fix, compare a redacted Nextbit stream with the Public AI gateway stream for a fresh plain reply and a tool continuation. Normalize at the first boundary that emits the malformed shape. Preserve the two controls, and verify that ordinary quoted tags in answer text remain literal.
