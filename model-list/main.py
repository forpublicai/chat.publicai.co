#!/usr/bin/env python3
"""
Model List Service & Cache API (FastAPI)
Periodically queries the LiteLLM /model/info endpoint, filters out excluded models based on
substring patterns, removes internal identifiers (access_via_team_ids, api_base, model_info.id),
caches the result in memory, and serves it via FastAPI.

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
  - GET / (and /healthz, /health):
      Returns service health, exclude rules, and cache status JSON (formerly /status).
  - GET /info (and /model/info):
      Returns the filtered & sanitized LiteLLM /model/info JSON payload.
  - GET /docs:
      FastAPI Interactive Swagger UI documentation.
"""

import os
import ssl
import sys
import time
import json
import signal
import asyncio
import logging
import argparse
import urllib.request
import urllib.error
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

import uvicorn
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

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

# Global cache state
cached_info_response: Optional[Dict[str, Any]] = None
cached_models_list: List[str] = []
total_unfiltered_count: int = 0
last_run_timestamp: Optional[str] = None
last_run_latency: float = 0.0
last_error: Optional[str] = None
app_config: Dict[str, Any] = {}
background_task: Optional[asyncio.Task] = None


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
        (args and getattr(args, "config", None))
        or os.environ.get("CONFIG_FILE")
        or (os.path.exists("/etc/model-list/config.yaml") and "/etc/model-list/config.yaml")
        or (os.path.exists("config.yaml") and "config.yaml")
        or None
    )

    file_cfg = load_config_file(config_file_path) if config_file_path else {}

    # Endpoint
    endpoint = (
        (args and getattr(args, "endpoint", None))
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
        (args and getattr(args, "api_key", None))
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
        (args and getattr(args, "interval", None))
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
        (args and getattr(args, "port", None))
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
        (args and getattr(args, "exclude", None))
        or os.environ.get("EXCLUDE_MODELS")
        or os.environ.get("EXCLUDE_PATTERNS")
        or file_cfg.get("exclude_patterns")
        or file_cfg.get("exclude_models")
        or []
    )
    exclude_patterns = parse_patterns(exclude_patterns_raw)

    # SSL Verify
    ssl_verify = True
    if args and getattr(args, "insecure", False):
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


def normalize_info_url(base_url: str) -> str:
    """Normalize base URL and ensure proper /model/info path."""
    url = base_url.rstrip("/")
    if not url.startswith("http://") and not url.startswith("https://"):
        url = f"http://{url}"

    if (
        url.endswith("/model/info")
        or url.endswith("/models/info")
        or url.endswith("/model_info")
        or url.endswith("/v1/model/info")
        or url.endswith("/v1/models/info")
    ):
        return url

    if url.endswith("/v1/models"):
        url = url[:-10].rstrip("/")
    elif url.endswith("/models"):
        url = url[:-7].rstrip("/")

    if url.endswith("/v1"):
        url = url[:-3].rstrip("/")

    return f"{url}/model/info"


def is_model_excluded(item, exclude_patterns: list) -> bool:
    """Check if a model item matches any exclusion pattern (case-insensitive)."""
    if not exclude_patterns:
        return False

    candidates = []
    if isinstance(item, dict):
        if item.get("model_name"):
            candidates.append(str(item["model_name"]))
        m_params = item.get("litellm_params")
        if isinstance(m_params, dict) and m_params.get("model"):
            candidates.append(str(m_params["model"]))
        m_info = item.get("model_info")
        if isinstance(m_info, dict):
            if m_info.get("key"):
                candidates.append(str(m_info["key"]))
            if m_info.get("id"):
                candidates.append(str(m_info["id"]))
        if item.get("id"):
            candidates.append(str(item["id"]))
    elif isinstance(item, str):
        candidates.append(item)

    for pat in exclude_patterns:
        if not pat:
            continue
        pat_lower = pat.lower()
        for cand in candidates:
            if pat_lower in cand.lower():
                return True
    return False


def sanitize_model_info_item(item: dict) -> dict:
    """
    Remove internal / sensitive fields before serving:
      - access_via_team_ids
      - api_base (from litellm_params or top-level)
      - model_info.id
    """
    if not isinstance(item, dict):
        return item

    cleaned = dict(item)
    cleaned.pop("access_via_team_ids", None)
    cleaned.pop("api_base", None)

    if "litellm_params" in cleaned and isinstance(cleaned["litellm_params"], dict):
        cleaned_params = dict(cleaned["litellm_params"])
        cleaned_params.pop("api_base", None)
        cleaned["litellm_params"] = cleaned_params

    if "model_info" in cleaned and isinstance(cleaned["model_info"], dict):
        cleaned_info = dict(cleaned["model_info"])
        cleaned_info.pop("access_via_team_ids", None)
        cleaned_info.pop("id", None)
        cleaned_info.pop("api_base", None)
        cleaned["model_info"] = cleaned_info

    return cleaned


def filter_and_sanitize_response(raw_data, exclude_patterns: list) -> tuple:
    """
    Filter model items matching exclusion patterns and strip access_via_team_ids, api_base, model_info.id.
    Returns: (sanitized_response_dict, kept_model_names_list, total_unfiltered_count)
    """
    if isinstance(raw_data, dict):
        raw_items = raw_data.get("data", [])
        if not isinstance(raw_items, list):
            raw_items = [raw_data]
    elif isinstance(raw_data, list):
        raw_items = raw_data
    else:
        raw_items = []

    total_count = len(raw_items)
    kept_items = []
    kept_names = []

    for item in raw_items:
        if is_model_excluded(item, exclude_patterns):
            continue

        sanitized_item = sanitize_model_info_item(item)
        kept_items.append(sanitized_item)

        name = ""
        if isinstance(item, dict):
            name = item.get("model_name") or item.get("model_info", {}).get("key") or item.get("id") or "unknown"
        else:
            name = str(item)
        kept_names.append(name)

    if isinstance(raw_data, dict):
        response_obj = dict(raw_data)
        response_obj["data"] = kept_items
    else:
        response_obj = {"data": kept_items}

    return response_obj, kept_names, total_count


def fetch_model_info(endpoint: str, api_key: str = None, ssl_verify: bool = True, timeout: int = 30):
    """
    Call LiteLLM /model/info endpoint and return parsed JSON data and latency.
    Returns: (raw_data, latency, error_message)
    """
    url = normalize_info_url(endpoint)
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
            return data, latency, None

    except urllib.error.HTTPError as e:
        latency = time.time() - start_time
        try:
            error_body = e.read().decode("utf-8")
        except Exception:
            error_body = ""
        err_msg = f"HTTP {e.code} ({e.reason})"
        if error_body:
            err_msg += f" - Response: {error_body.strip()}"
        return None, latency, err_msg

    except urllib.error.URLError as e:
        latency = time.time() - start_time
        return None, latency, f"URL Error: {e.reason}"

    except json.JSONDecodeError as e:
        latency = time.time() - start_time
        return None, latency, f"JSON Decode Error: {e}"

    except Exception as e:
        latency = time.time() - start_time
        return None, latency, f"Unexpected Error ({type(e).__name__}): {e}"


def run_single_check(config: dict, verbose: bool = False, update_cache: bool = True) -> tuple:
    """Execute a single fetch from LiteLLM, apply exclusion filter and sanitization, and update cache."""
    global cached_info_response, cached_models_list, total_unfiltered_count, last_run_timestamp, last_run_latency, last_error

    endpoint = config["endpoint"]
    api_key = config["api_key"]
    ssl_verify = config["ssl_verify"]
    exclude_patterns = config["exclude_patterns"]
    target_url = normalize_info_url(endpoint)
    masked_key = f"{api_key[:4]}...{api_key[-4:]}" if api_key and len(api_key) > 8 else ("***" if api_key else "[None]")

    logger.info(f"Fetching LiteLLM model info from: {target_url} (API Key: {masked_key}, SSL Verify: {ssl_verify})")

    raw_data, latency, error = fetch_model_info(
        endpoint=endpoint,
        api_key=api_key,
        ssl_verify=ssl_verify
    )

    if error:
        if update_cache:
            last_run_timestamp = datetime.now(timezone.utc).isoformat()
            last_run_latency = latency
            last_error = error
        logger.error(f"Failed to fetch model info from LiteLLM: {error} (latency: {latency:.3f}s)")
        return False, None

    # Apply exclusion filter and sanitization
    sanitized_response, kept_names, total_count = filter_and_sanitize_response(raw_data, exclude_patterns)

    if update_cache:
        last_run_timestamp = datetime.now(timezone.utc).isoformat()
        last_run_latency = latency
        last_error = None
        cached_info_response = sanitized_response
        cached_models_list = kept_names
        total_unfiltered_count = total_count

    logger.info(
        f"Successfully updated cache: {len(kept_names)}/{total_count} model(s) kept "
        f"(Exclude patterns: {exclude_patterns or 'None'}) in {latency:.3f}s:"
    )
    for idx, m_id in enumerate(kept_names, start=1):
        logger.info(f"  {idx:2d}. {m_id}")

    return True, sanitized_response


async def background_poller():
    """Background async polling task running once every app_config['interval'] seconds."""
    logger.info(f"Starting background polling task (interval: {app_config['interval']}s)...")
    while True:
        try:
            run_single_check(app_config, update_cache=True)
        except asyncio.CancelledError:
            logger.info("Background polling task cancelled.")
            break
        except Exception as e:
            logger.error(f"Unhandled error in polling cycle: {e}", exc_info=True)

        logger.info(f"Next background check scheduled in {app_config['interval']} seconds...")
        try:
            await asyncio.sleep(app_config["interval"])
        except asyncio.CancelledError:
            break


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI Lifespan context manager for startup and shutdown events."""
    global background_task, app_config
    if not app_config:
        load_env()
        app_config = get_config()

    logger.info("=" * 70)
    logger.info("Starting LiteLLM Model Info Cache & API Service (FastAPI)")
    if app_config.get("config_file"):
        logger.info(f"Config File:     {app_config['config_file']}")
    logger.info(f"Target Endpoint: {normalize_info_url(app_config['endpoint'])}")
    logger.info(f"Exclude Rules:   {app_config['exclude_patterns'] or 'None'}")
    logger.info(f"Poll Interval:   {app_config['interval']} seconds ({app_config['interval'] / 60:.1f} minute(s))")
    logger.info(f"HTTP Server Port:{app_config['port']}")
    logger.info(f"SSL Verify:      {app_config['ssl_verify']}")
    logger.info("=" * 70)

    # Initial warm-up check
    try:
        run_single_check(app_config, update_cache=True)
    except Exception as e:
        logger.error(f"Initial warm-up check failed: {e}")

    # Start background polling task
    background_task = asyncio.create_task(background_poller())

    yield

    # Shutdown
    if background_task:
        background_task.cancel()
        try:
            await background_task
        except asyncio.CancelledError:
            pass
    logger.info("LiteLLM Model List Service stopped cleanly.")


# Initialize FastAPI application
app = FastAPI(
    title="Model List Service",
    description="Caches LiteLLM model info with exclusion filters and serves via HTTP API.",
    version="1.0.0",
    lifespan=lifespan
)

# Enable CORS for all origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(StarletteHTTPException)
async def custom_http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Custom 404 handler with available endpoints hint."""
    if exc.status_code == 404:
        return JSONResponse(
            status_code=404,
            content={"error": "Not Found", "available_endpoints": ["/", "/info", "/docs"]}
        )
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail}
    )


@app.get(
    "/",
    summary="Health & Status Overview",
    description="Returns the service health status, last poll timestamp, latency, and cached model names list.",
    tags=["Status"]
)
@app.get("/healthz", include_in_schema=False)
@app.get("/health", include_in_schema=False)
async def get_status():
    """Root endpoint returning service status & health."""
    status_text = "healthy" if last_error is None else "degraded"
    if last_run_timestamp is None and last_error is None:
        status_text = "warming"

    health_data = {
        "status": status_text,
        "last_run_timestamp": last_run_timestamp,
        "last_run_latency_seconds": round(last_run_latency, 3),
        "filtered_model_count": len(cached_models_list),
        "total_unfiltered_model_count": total_unfiltered_count,
        "models": cached_models_list,
        "last_error": last_error
    }
    status_code = status.HTTP_200_OK if last_error is None else status.HTTP_500_INTERNAL_SERVER_ERROR
    return JSONResponse(status_code=status_code, content=health_data)


@app.get(
    "/info",
    summary="LiteLLM Model Info",
    description="Returns the cached LiteLLM /model/info JSON payload with excluded models filtered and internal metadata stripped.",
    tags=["Models"]
)
@app.get("/model/info", include_in_schema=False)
async def get_info():
    """Returns cached LiteLLM model info."""
    if cached_info_response is not None:
        return JSONResponse(status_code=status.HTTP_200_OK, content=cached_info_response)
    else:
        response_obj = {
            "data": [],
            "error": last_error or "Cache warming in progress...",
            "status": "error" if last_error else "cache_empty"
        }
        status_code = status.HTTP_503_SERVICE_UNAVAILABLE if last_error else status.HTTP_202_ACCEPTED
        return JSONResponse(status_code=status_code, content=response_obj)


def main():
    global app_config
    parser = argparse.ArgumentParser(
        description="Model List Service (FastAPI) - Caches LiteLLM model info with exclusion filters and serves via HTTP API."
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
        help="Fetch model info once, print JSON to stdout, and exit"
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
    app_config = get_config(args)

    if args.verbose:
        logger.setLevel(logging.DEBUG)

    run_once = args.once or os.environ.get("RUN_ONCE", "").strip().lower() in ("true", "1", "yes")
    if run_once:
        success, result_data = run_single_check(app_config, verbose=args.verbose, update_cache=False)
        if success and result_data:
            print(json.dumps(result_data, indent=2))
        sys.exit(0 if success else 1)

    log_level = "debug" if args.verbose else "info"
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=app_config["port"],
        log_level=log_level
    )


if __name__ == "__main__":
    main()
