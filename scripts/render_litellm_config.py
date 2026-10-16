import subprocess
import sys
from pathlib import Path

import yaml

# Resolved from this file's own location, not the process cwd — works regardless
# of where it's invoked from (e.g. `python3 scripts/render_litellm_config.py`
# from the repo root, or from inside a container with a different working_dir).
ROOT = Path(__file__).resolve().parent.parent
CHART_PATH = ROOT / "charts" / "platform" / "charts" / "litellm"
OUTPUT_CONFIG = ROOT / "litellm-config.rendered.yaml"
CHECK_SCRIPT = ROOT / "health-check" / "model-code-check.py"


def render_chart(chart_path, env: str = "staging") -> str:
    """Run `helm template` against the chart and return the rendered manifest text."""
    try:
        result = subprocess.run(
            ["helm", "template", "litellm-local", str(chart_path),
             "--set", f"global.environment={env}",
             "--set", "lago.enabled=false"],
            capture_output=True, text=True,
        )
    except FileNotFoundError:
        raise RuntimeError(
            "`helm` is not installed in this image. Rebuild the `render_config` service."
        )
    if result.returncode != 0:
        raise RuntimeError(
            f"helm template failed (is {chart_path} a valid chart?):\n{result.stderr}"
        )
    return result.stdout


def extract_config(rendered_manifest_text: str) -> dict:
    """Pull the real LiteLLM config out of the rendered Kubernetes ConfigMap.
    `helm template` emits multiple `---`-separated documents (Deployment,
    Service, ConfigMap, etc.) — find the ConfigMap that holds config.yaml."""
    for doc in yaml.safe_load_all(rendered_manifest_text):
        if doc and doc.get("kind") == "ConfigMap" and "config.yaml" in doc.get("data", {}):
            return yaml.safe_load(doc["data"]["config.yaml"])
    raise RuntimeError("No ConfigMap with a config.yaml key found in the rendered manifest.")


def patch_for_local_use(config: dict, api_key):
    """If a Public AI API key is set, redirect every OpenAI-compatible deployment
    through the real public API; otherwise leave the real per-partner config
    untouched. Only touches `litellm_params.model` values prefixed `openai/` —
    non-OpenAI-protocol entries (e.g. `bedrock/...`, `auto_router/...`) have no
    equivalent on api.publicai.co and must be left alone."""
    if not api_key or not api_key.strip():
        return config
    for entry in config.get("model_list", []):
        params = entry["litellm_params"]
        if not str(params.get("model", "")).startswith("openai/"):
            continue
        params["api_base"] = "https://api.publicai.co/v1"
        params["api_key"] = "os.environ/PUBLICAI_API_KEY"
        params.setdefault("extra_headers", {})["User-Agent"] = "public-ai-local/0.1"
    return config


def main():
    import os

    api_key = os.environ.get("PUBLICAI_API_KEY")

    rendered = render_chart(CHART_PATH)
    config = extract_config(rendered)
    config = patch_for_local_use(config, api_key)

    if OUTPUT_CONFIG.is_dir():
        raise RuntimeError(
            f"{OUTPUT_CONFIG} is a directory, not a file — this happens if `litellm` "
            "started before `render_config` ever ran. Remove it (rmdir) and retry."
        )
    with open(OUTPUT_CONFIG, "w") as f:
        yaml.safe_dump(config, f, sort_keys=False)

    print(f"Wrote {OUTPUT_CONFIG}")
    if not api_key:
        print("PUBLICAI_API_KEY is not set — no model will respond (the real chart "
              "has no offline/free model); set it in .env to test against real models.")
    elif not api_key.strip():
        print("PUBLICAI_API_KEY is set but empty — treated the same as unset; "
              "no model will respond until you set a real value in .env.")

    # Validates the chart SOURCE (models/, secrets, Lago mappings) independently
    # of what we just rendered — not a check on litellm-config.rendered.yaml itself.
    # Non-fatal on purpose: an upstream chart lint issue shouldn't block the local
    # stack from starting.
    validation = subprocess.run(
        [sys.executable, str(CHECK_SCRIPT), "--repo-root", str(ROOT), "--env", "staging"],
        capture_output=True, text=True,
    )
    if validation.returncode != 0:
        print("WARNING: chart source failed model-code-check.py validation "
              "(this checks charts/platform/charts/litellm/, not the rendered "
              "output above — the rendered config was still written):")
        print(validation.stdout)
        print(validation.stderr)
    else:
        print("Chart source passed model-code-check.py validation.")


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as e:
        sys.exit(f"ERROR: {e}")
