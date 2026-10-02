import os
import subprocess
import sys
import yaml

# Paths relative to this script's own directory (scripts/), matching the
# `render` compose service's working_dir — one level up reaches the repo root.
CHART_PATH = "../charts/platform/charts/litellm"
OUTPUT_CONFIG = "../litellm-config.rendered.yaml"
CHECK_SCRIPT = "../health-check/model-code-check.py"


def render_chart(chart_path: str, env: str = "staging") -> str:
    """Run `helm template` against the chart and return the rendered manifest text."""
    try:
        result = subprocess.run(
            ["helm", "template", "litellm-local", chart_path,
             "--set", f"global.environment={env}",
             "--set", "lago.enabled=false"],
            capture_output=True, text=True,
        )
    except FileNotFoundError:
        raise RuntimeError(
            "`helm` is not installed in this image. Rebuild the `render` service."
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
    """If a Public AI API key is set, redirect every deployment through the real
    public API; otherwise leave the real per-partner config untouched."""
    if not api_key:
        return config
    for entry in config.get("model_list", []):
        params = entry["litellm_params"]
        params["api_base"] = "https://api.publicai.co/v1"
        params["api_key"] = "os.environ/PUBLICAI_API_KEY"
        params["extra_headers"] = {"User-Agent": "public-ai-local/0.1"}
    return config


def main():
    api_key = os.environ.get("PUBLICAI_API_KEY")

    rendered = render_chart(CHART_PATH)
    config = extract_config(rendered)
    config = patch_for_local_use(config, api_key)

    with open(OUTPUT_CONFIG, "w") as f:
        yaml.safe_dump(config, f, sort_keys=False)

    print(f"Wrote {OUTPUT_CONFIG}")
    if not api_key:
        print("PUBLICAI_API_KEY not set — no model will respond (the real chart has "
              "no offline/free model); set it in .env to test against real models.")

    validation = subprocess.run(
        [sys.executable, CHECK_SCRIPT, "--repo-root", ".."],
        capture_output=True, text=True,
    )
    if validation.returncode != 0:
        print("WARNING: rendered config failed model-code-check.py validation:")
        print(validation.stdout)
        print(validation.stderr)
        sys.exit(1)
    print("Passed model-code-check.py validation.")


if __name__ == "__main__":
    main()
