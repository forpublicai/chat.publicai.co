#!/usr/bin/env python3
"""
Model List Service & Cache API
Periodically queries the LiteLLM /v1/models endpoint, filters out excluded models based on
substring patterns, caches the result in memory, and serves it via a lightweight HTTP API.

Configuration via Environment Variables or Config File (Helm compatible):
  - CONFIG_FILE:
      Path to YAML or JSON config file (e.g. /etc/model-list/config.yaml or ./config.yaml).
  - LITELLM_ENDPOINT / LITELLM_URL / LITELLM_API_BASE:
      Base URL for the LiteLLM service.
      Default: http://litellm-service.platform.svc.cluster.local:4000
  - LITELLM_API_KEY / LITELLM_KEY / LITELLM_MASTER_KEY:
      API key for LiteLLM authorization.
  - EXCLUDE_MODELS / EXCLUDE_PATTERNS:
      Comma-separated list of substring patterns to exclude (e.g. "mock,test,rerank").
      Models matching any pattern will be filtered out.
  - CHECK_INTERVAL_SECONDS / INTERVAL_SECONDS / INTERVAL:
      Interval between background queries in seconds (default: 600 = 10 minutes).
  - PORT:
      HTTP API server port (default: 8000).
  - SSL_VERIFY:
      Set to 'false' or '0' to disable SSL certificate verification (default: true).

API Endpoints:
  - GET /v1/models or GET /models or GET /:
      Returns the filtered & cached LiteLLM models JSON payload.
  - GET /status or GET /health:
      Returns service health, exclude rules, and cache status JSON.
"""

import os
import ssl
import sys
import time
import json
import signal
import logging
import threading
import argparse
import urllib.request
import urllib.error
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime, timezone

# Optional PyYAML support if installed; fallback to JSON loader if YAML not installed
try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

# Default settings
DEFAULT_ENDPOINT = "http://litellm-service.platform.svc.cluster.local:4000"
DEFAULT_INTERVAL = 600  # 10 minutes in seconds
DEFAULT_PORT = 8000

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("model-list")

# Thread safety lock & global cache state
cache_lock = threading.Lock()
cached_raw_response = None
cached_models_list = []
total_unfiltered_count = 0
last_run_timestamp = None
last_run_latency = 0.0
last_error = None

# Shutdown event
shutdown_event = threading.Event()


def load_env(env_path=None, verbose=False):
    """Load environment variables from a .env file if present."""
    if not env_path:
        current_dir = os.path.abspath(os.getcwd())
        root_dir = os.path.dirname(os.path.abspath(__file__))
        search_dirs = [current_dir, root_dir]

        d = root_dir
        while d != os.path.dirname(d):
            if d not in search_dirs:
                search_dirs.append(d)
            d = os.path.dirname(d)

        for d in search_dirs:
            candidate = os.path.join(d, ".env")
            if os.path.isfile(candidate):
                env_path = candidate
                break

    if not env_path or not os.path.exists(env_path):
        if verbose:
            logger.debug(".env file not found.")
        return

    if verbose:
        logger.info(f"Loading environment variables from: {env_path}")

    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, val = line.split("=", 1)
                key = key.strip()
                val = val.strip().strip('"').strip("'")
                if key not in os.environ:
                    os.environ[key] = val


def load_config_file(file_path: str) -> dict:
    """Load configuration dictionary from a JSON or YAML file."""
    if not file_path or not os.path.exists(file_path):
        return {}

    logger.info(f"Loading configuration file from: {file_path}")
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
            if HAS_YAML:
                data = yaml.safe_load(content)
            else:
                data = json.loads(content)
            return data if isinstance(data, dict) else {}
    except Exception as e:
        logger.error(f"Failed to parse config file '{file_path}': {e}")
        return {}


def parse_patterns(value) -> list:
    """Parse comma-separated string or list into a clean list of pattern strings."""
    if not value:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    return []


def get_config(args=None):
    """
    Resolve configuration from CLI arguments, environment variables, config file, or defaults.
    Priority: CLI args > Environment variables > Config file > Defaults.
    """
    config_file_path = (
        (args and args.config)
        or os.environ.get("CONFIG_FILE")
        or (os.path.exists("/etc/model-list/config.yaml") and "/etc/model-list/config.yaml")
        or (os.path.exists("config.yaml") and "config.yaml")
        or None
    )

    file_cfg = load_config_file(config_file_path) if config_file_path else {}

    # Endpoint
    endpoint = (
        (args and args.endpoint)
        or os.environ.get("LITELLM_ENDPOINT")
        or os.environ.get("LITELLM_URL")
        or os.environ.get("LITELLM_API_BASE")
        or os.environ.get("LITELLM_BASE_URL")
        or file_cfg.get("endpoint")
        or file_cfg.get("litellm_endpoint")
        or DEFAULT_ENDPOINT
    ).strip()

    # API Key
    api_key = (
        (args and args.api_key)
        or os.environ.get("LITELLM_API_KEY")
        or os.environ.get("LITELLM_KEY")
        or os.environ.get("LITELLM_MASTER_KEY")
        or file_cfg.get("api_key")
        or file_cfg.get("litellm_api_key")
        or None
    )
    if api_key:
        api_key = api_key.strip()

    # Interval
    interval_raw = (
        (args and args.interval)
        or os.environ.get("CHECK_INTERVAL_SECONDS")
        or os.environ.get("INTERVAL_SECONDS")
        or os.environ.get("INTERVAL")
        or file_cfg.get("interval")
        or file_cfg.get("check_interval_seconds")
        or str(DEFAULT_INTERVAL)
    )
    try:
        interval = int(interval_raw)
    except ValueError:
        logger.warning(f"Invalid interval value '{interval_raw}', using default {DEFAULT_INTERVAL}s")
        interval = DEFAULT_INTERVAL

    # Port
    port_raw = (
        (args and args.port)
        or os.environ.get("PORT")
        or file_cfg.get("port")
        or str(DEFAULT_PORT)
    )
    try:
        port = int(port_raw)
    except ValueError:
        logger.warning(f"Invalid port value '{port_raw}', using default {DEFAULT_PORT}")
        port = DEFAULT_PORT

    # Exclude Patterns
    exclude_patterns_raw = (
        (args and args.exclude)
        or os.environ.get("EXCLUDE_MODELS")
        or os.environ.get("EXCLUDE_PATTERNS")
        or file_cfg.get("exclude_patterns")
        or file_cfg.get("exclude_models")
        or []
    )
    exclude_patterns = parse_patterns(exclude_patterns_raw)

    # SSL Verify
    ssl_verify = True
    if args and args.insecure:
        ssl_verify = False
    else:
        env_ssl = os.environ.get("SSL_VERIFY")
        if env_ssl is not None:
            if str(env_ssl).strip().lower() in ("false", "0", "no", "off"):
                ssl_verify = False
        elif "ssl_verify" in file_cfg:
            ssl_verify = bool(file_cfg["ssl_verify"])

    return {
        "config_file": config_file_path,
        "endpoint": endpoint,
        "api_key": api_key,
        "interval": interval,
        "port": port,
        "exclude_patterns": exclude_patterns,
        "ssl_verify": ssl_verify
    }


def normalize_models_url(base_url: str) -> str:
    """Normalize base URL and ensure proper /v1/models path."""
    url = base_url.rstrip("/")
    if not url.startswith("http://") and not url.startswith("https://"):
        url = f"http://{url}"

    if url.endswith("/v1/models") or url.endswith("/models"):
        return url
    if url.endswith("/v1"):
        return f"{url}/models"
    return f"{url}/v1/models"


def filter_models(models: list, exclude_patterns: list) -> tuple:
    """
    Filter model dicts to exclude models matching any of the exclude substring patterns.
    Returns: (filtered_models, total_unfiltered_count)
    """
    total_count = len(models)
    if not exclude_patterns:
        return models, total_count

    filtered = []
    for m in models:
        m_id = m.get("id", "")
        m_id_lower = m_id.lower()

        # Exclude models matching any pattern (case-insensitive)
        matched_exclude = any(pat.lower() in m_id_lower for pat in exclude_patterns if pat)
        if matched_exclude:
            continue

        filtered.append(m)

    return filtered, total_count


def fetch_models(endpoint: str, api_key: str = None, ssl_verify: bool = True, timeout: int = 30):
    """
    Call LiteLLM models endpoint and return parsed model list and metadata.
    Returns: (models_list, raw_response, latency, error_message)
    """
    url = normalize_models_url(endpoint)
    headers = {
        "User-Agent": "model-list-service/1.0",
        "Accept": "application/json"
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    req = urllib.request.Request(url, headers=headers, method="GET")

    context = None
    if not ssl_verify:
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE

    start_time = time.time()
    try:
        with urllib.request.urlopen(req, context=context, timeout=timeout) as response:
            latency = time.time() - start_time
            body_bytes = response.read()
            body_str = body_bytes.decode("utf-8")
            data = json.loads(body_str)

            models = []
            if isinstance(data, dict):
                data_list = data.get("data", [])
                if isinstance(data_list, list):
                    for item in data_list:
                        if isinstance(item, dict):
                            models.append({
                                "id": item.get("id", "unknown"),
                                "owned_by": item.get("owned_by", ""),
                                "created": item.get("created"),
                                "raw": item
                            })
                        elif isinstance(item, str):
                            models.append({
                                "id": item,
                                "owned_by": "",
                                "created": None,
                                "raw": item
                            })
                elif "models" in data and isinstance(data["models"], list):
                    for item in data["models"]:
                        model_id = item.get("id", item) if isinstance(item, dict) else str(item)
                        models.append({
                            "id": model_id,
                            "owned_by": item.get("owned_by", "") if isinstance(item, dict) else "",
                            "created": item.get("created") if isinstance(item, dict) else None,
                            "raw": item
                        })
            elif isinstance(data, list):
                for item in data:
                    model_id = item.get("id", item) if isinstance(item, dict) else str(item)
                    models.append({
                        "id": model_id,
                        "owned_by": item.get("owned_by", "") if isinstance(item, dict) else "",
                        "created": item.get("created") if isinstance(item, dict) else None,
                        "raw": item
                    })

            return models, data, latency, None

    except urllib.error.HTTPError as e:
        latency = time.time() - start_time
        try:
            error_body = e.read().decode("utf-8")
        except Exception:
            error_body = ""
        err_msg = f"HTTP {e.code} ({e.reason})"
        if error_body:
            err_msg += f" - Response: {error_body.strip()}"
        return None, None, latency, err_msg

    except urllib.error.URLError as e:
        latency = time.time() - start_time
        return None, None, latency, f"URL Error: {e.reason}"

    except json.JSONDecodeError as e:
        latency = time.time() - start_time
        return None, None, latency, f"JSON Decode Error: {e}"

    except Exception as e:
        latency = time.time() - start_time
        return None, None, latency, f"Unexpected Error ({type(e).__name__}): {e}"


def run_single_check(config: dict, verbose: bool = False, update_cache: bool = True) -> bool:
    """Execute a single fetch from LiteLLM, apply exclusion filter, and update internal cache state."""
    global cached_raw_response, cached_models_list, total_unfiltered_count, last_run_timestamp, last_run_latency, last_error

    endpoint = config["endpoint"]
    api_key = config["api_key"]
    ssl_verify = config["ssl_verify"]
    exclude_patterns = config["exclude_patterns"]
    target_url = normalize_models_url(endpoint)
    masked_key = f"{api_key[:4]}...{api_key[-4:]}" if api_key and len(api_key) > 8 else ("***" if api_key else "[None]")

    logger.info(f"Fetching LiteLLM models from: {target_url} (API Key: {masked_key}, SSL Verify: {ssl_verify})")

    raw_models, raw_data, latency, error = fetch_models(
        endpoint=endpoint,
        api_key=api_key,
        ssl_verify=ssl_verify
    )

    if error:
        if update_cache:
            with cache_lock:
                last_run_timestamp = datetime.now(timezone.utc).isoformat()
                last_run_latency = latency
                last_error = error
        logger.error(f"Failed to fetch models from LiteLLM: {error} (latency: {latency:.3f}s)")
        return False

    # Apply exclusion filter
    filtered_models, total_count = filter_models(raw_models, exclude_patterns)
    filtered_model_ids = [m["id"] for m in filtered_models]
    filtered_raw_objects = [m["raw"] for m in filtered_models]

    constructed_response = {
        "object": "list",
        "data": filtered_raw_objects
    }

    if update_cache:
        with cache_lock:
            last_run_timestamp = datetime.now(timezone.utc).isoformat()
            last_run_latency = latency
            last_error = None
            cached_raw_response = constructed_response
            cached_models_list = filtered_model_ids
            total_unfiltered_count = total_count

    logger.info(
        f"Successfully updated cache: {len(filtered_models)}/{total_count} model(s) kept "
        f"(Exclude patterns: {exclude_patterns or 'None'}) in {latency:.3f}s:"
    )
    for idx, m_id in enumerate(filtered_model_ids, start=1):
        logger.info(f"  {idx:2d}. {m_id}")

    return True


def polling_loop(config: dict, verbose: bool = False):
    """Background polling loop running once every config['interval'] seconds."""
    logger.info(f"Starting background polling loop (interval: {config['interval']}s)...")
    while not shutdown_event.is_set():
        try:
            run_single_check(config, verbose=verbose, update_cache=True)
        except Exception as e:
            logger.error(f"Unhandled exception during polling cycle: {e}", exc_info=True)

        logger.info(f"Next background check scheduled in {config['interval']} seconds...")
        if shutdown_event.wait(timeout=config["interval"]):
            break


class ModelListAPIHandler(BaseHTTPRequestHandler):
    """HTTP Request Handler for serving cached LiteLLM models."""

    def log_message(self, format, *args):
        logger.info(f"API Request [{self.client_address[0]}] {format % args}")

    def _send_json(self, status_code: int, data: dict or list):
        payload = json.dumps(data, indent=2).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        clean_path = self.path.split("?")[0].rstrip("/")
        if not clean_path:
            clean_path = "/"

        # Models API endpoints
        if clean_path in ("/", "/v1/models", "/models"):
            with cache_lock:
                if cached_raw_response is not None:
                    self._send_json(200, cached_raw_response)
                else:
                    response_obj = {
                        "object": "list",
                        "data": [],
                        "error": last_error or "Cache warming in progress...",
                        "status": "cache_empty"
                    }
                    self._send_json(503 if last_error else 202, response_obj)

        # Status & Health endpoint
        elif clean_path in ("/status", "/healthz", "/health"):
            with cache_lock:
                health_data = {
                    "status": "healthy" if last_error is None else "degraded",
                    "last_run_timestamp": last_run_timestamp,
                    "last_run_latency_seconds": round(last_run_latency, 3),
                    "filtered_model_count": len(cached_models_list),
                    "total_unfiltered_model_count": total_unfiltered_count,
                    "models": cached_models_list,
                    "last_error": last_error
                }
                status_code = 200 if last_error is None else 500
                self._send_json(status_code, health_data)

        else:
            self._send_json(404, {"error": "Not Found", "available_endpoints": ["/v1/models", "/models", "/", "/status"]})


def main():
    parser = argparse.ArgumentParser(
        description="Model List Service - Caches LiteLLM models with exclusion filters and serves via HTTP API."
    )
    parser.add_argument(
        "-c", "--config",
        dest="config",
        help="Path to YAML or JSON configuration file"
    )
    parser.add_argument(
        "-e", "--endpoint", "--url", "-u",
        dest="endpoint",
        help="LiteLLM endpoint base URL"
    )
    parser.add_argument(
        "-k", "--key", "--api-key",
        dest="api_key",
        help="LiteLLM API key"
    )
    parser.add_argument(
        "--exclude",
        dest="exclude",
        help="Comma-separated substring patterns to exclude (e.g. 'mock,test,rerank')"
    )
    parser.add_argument(
        "-i", "--interval",
        dest="interval",
        help="Check interval in seconds (default: 600 = 10 minutes)"
    )
    parser.add_argument(
        "-p", "--port",
        dest="port",
        help="HTTP API port (default: 8000)"
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Fetch models once, print JSON to stdout, and exit"
    )
    parser.add_argument(
        "--insecure",
        action="store_true",
        help="Disable SSL certificate verification"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output in JSON format (used with --once)"
    )
    args = parser.parse_args()

    load_env(verbose=args.verbose)
    config = get_config(args)

    if args.verbose:
        logger.setLevel(logging.DEBUG)

    run_once = args.once or os.environ.get("RUN_ONCE", "").strip().lower() in ("true", "1", "yes")
    if run_once:
        success = run_single_check(config, verbose=args.verbose, update_cache=False)
        sys.exit(0 if success else 1)

    def signal_handler(signum, frame):
        sig_name = signal.Signals(signum).name
        logger.info(f"Received signal {sig_name}, shutting down...")
        shutdown_event.set()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    logger.info("=" * 70)
    logger.info("Starting LiteLLM Model List Cache & API Service")
    if config['config_file']:
        logger.info(f"Config File:     {config['config_file']}")
    logger.info(f"Target Endpoint: {normalize_models_url(config['endpoint'])}")
    logger.info(f"Exclude Rules:   {config['exclude_patterns'] or 'None'}")
    logger.info(f"Poll Interval:   {config['interval']} seconds ({config['interval'] / 60:.1f} minute(s))")
    logger.info(f"HTTP Server Port:{config['port']}")
    logger.info(f"SSL Verify:      {config['ssl_verify']}")
    logger.info("=" * 70)

    # Start background polling thread
    poll_thread = threading.Thread(target=polling_loop, args=(config, args.verbose), daemon=True)
    poll_thread.start()

    # Start HTTP server
    server_address = ("", config["port"])
    httpd = HTTPServer(server_address, ModelListAPIHandler)
    logger.info(f"HTTP API server listening on http://0.0.0.0:{config['port']}")

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        logger.info("Stopping HTTP server...")
        httpd.server_close()
        logger.info("LiteLLM Model List Service stopped cleanly.")


if __name__ == "__main__":
    main()
