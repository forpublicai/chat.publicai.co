import os
import sys
import json
import time
import subprocess
import threading
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler

# Thread safety lock
data_lock = threading.Lock()

# Custom JSON Logger setup
class JsonFormatter(logging.Formatter):
    def format(self, record):
        log_record = {
            "timestamp": time.strftime('%Y-%m-%dT%H:%M:%S', time.gmtime(record.created)) + f".{int(record.msecs):03d}Z",
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
        }
        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)
        
        # Include extra attributes passed to log statements via `extra={...}`
        standard_attrs = {
            'args', 'asctime', 'created', 'exc_info', 'exc_text', 'filename',
            'funcName', 'levelname', 'levelno', 'lineno', 'module',
            'msecs', 'message', 'msg', 'name', 'pathname', 'process',
            'processName', 'relativeCreated', 'stack_info', 'thread', 'threadName'
        }
        for key, val in record.__dict__.items():
            if key not in standard_attrs:
                log_record[key] = val
        return json.dumps(log_record)

logger = logging.getLogger("health-check")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(JsonFormatter())
logger.addHandler(handler)

# Global state
latest_results = []
last_run_timestamp = 0.0
last_error = None

suppliers_results = []
suppliers_last_run_timestamp = 0.0
suppliers_last_error = None

publicai_results = []
publicai_last_run_timestamp = 0.0
publicai_last_error = None

currentai_results = []
currentai_last_run_timestamp = 0.0
currentai_last_error = None

zuplo_results = []
zuplo_last_run_timestamp = 0.0
zuplo_last_error = None

CHECK_TIMEOUT_SECONDS = int(os.environ.get("CHECK_TIMEOUT_SECONDS", 100))

def run_huggingface_check():
    global latest_results, last_run_timestamp, last_error
    hf_script = "/app/huggingface.py"
    if not os.path.exists(hf_script):
        hf_script = os.path.abspath(os.path.join(os.path.dirname(__file__), "huggingface.py"))
        
    try:
        result = subprocess.run(
            [sys.executable, hf_script, "-json"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=CHECK_TIMEOUT_SECONDS
        )
        try:
            data = json.loads(result.stdout)
            with data_lock:
                latest_results = data.get("results", [])
                last_run_timestamp = time.time()
                error_obj = data.get("error")
                if error_obj:
                    last_error = error_obj.get("message")
                else:
                    last_error = None
            logger.info("HuggingFace health check completed", extra={
                "check_type": "huggingface",
                "success": last_error is None,
                "results": latest_results,
                "error": last_error
            })
        except json.JSONDecodeError:
            with data_lock:
                latest_results = []
                last_run_timestamp = time.time()
                last_error = f"Invalid JSON output from huggingface.py. Stdout: {result.stdout[:500]} Stderr: {result.stderr[:500]}"
            logger.error("Failed to decode JSON from huggingface.py", extra={
                "check_type": "huggingface",
                "success": False,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "error": last_error
            })
    except subprocess.TimeoutExpired:
        with data_lock:
            latest_results = []
            last_run_timestamp = time.time()
            last_error = f"HuggingFace health check timed out after {CHECK_TIMEOUT_SECONDS}s"
        logger.error(f"HuggingFace health check timed out after {CHECK_TIMEOUT_SECONDS}s", extra={
            "check_type": "huggingface",
            "success": False,
            "error": last_error
        })
    except Exception as e:
        with data_lock:
            latest_results = []
            last_run_timestamp = time.time()
            last_error = f"Exception running huggingface.py: {e}"
        logger.error(f"Exception running huggingface.py: {e}", exc_info=True, extra={
            "check_type": "huggingface",
            "success": False,
            "error": last_error
        })

def run_suppliers_check():
    global suppliers_results, suppliers_last_run_timestamp, suppliers_last_error
    suppliers_script = "/app/suppliers.py"
    if not os.path.exists(suppliers_script):
        suppliers_script = os.path.abspath(os.path.join(os.path.dirname(__file__), "suppliers.py"))
        
    try:
        result = subprocess.run(
            [sys.executable, suppliers_script, "-json"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=CHECK_TIMEOUT_SECONDS
        )
        try:
            data = json.loads(result.stdout)
            with data_lock:
                suppliers_results = data.get("results", [])
                suppliers_last_run_timestamp = time.time()
                error_obj = data.get("error")
                if error_obj:
                    suppliers_last_error = error_obj.get("message")
                else:
                    suppliers_last_error = None
            logger.info("Suppliers health check completed", extra={
                "check_type": "suppliers",
                "success": suppliers_last_error is None,
                "results": suppliers_results,
                "error": suppliers_last_error
            })
        except json.JSONDecodeError:
            with data_lock:
                suppliers_results = []
                suppliers_last_run_timestamp = time.time()
                suppliers_last_error = f"Invalid JSON output from suppliers.py. Stdout: {result.stdout[:500]} Stderr: {result.stderr[:500]}"
            logger.error("Failed to decode JSON from suppliers.py", extra={
                "check_type": "suppliers",
                "success": False,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "error": suppliers_last_error
            })
    except subprocess.TimeoutExpired:
        with data_lock:
            suppliers_results = []
            suppliers_last_run_timestamp = time.time()
            suppliers_last_error = f"Suppliers health check timed out after {CHECK_TIMEOUT_SECONDS}s"
        logger.error(f"Suppliers health check timed out after {CHECK_TIMEOUT_SECONDS}s", extra={
            "check_type": "suppliers",
            "success": False,
            "error": suppliers_last_error
        })
    except Exception as e:
        with data_lock:
            suppliers_results = []
            suppliers_last_run_timestamp = time.time()
            suppliers_last_error = f"Exception running suppliers.py: {e}"
        logger.error(f"Exception running suppliers.py: {e}", exc_info=True, extra={
            "check_type": "suppliers",
            "success": False,
            "error": suppliers_last_error
        })

def run_publicai_router_check():
    global publicai_results, publicai_last_run_timestamp, publicai_last_error
    litellm_script = "/app/litellm.py"
    if not os.path.exists(litellm_script):
        litellm_script = os.path.abspath(os.path.join(os.path.dirname(__file__), "litellm.py"))
        
    try:
        result = subprocess.run(
            [sys.executable, litellm_script, "--router-name", "publicai_router", "-json"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=CHECK_TIMEOUT_SECONDS
        )
        try:
            data = json.loads(result.stdout)
            with data_lock:
                publicai_results = data.get("results", [])
                publicai_last_run_timestamp = time.time()
                error_obj = data.get("error")
                if error_obj:
                    publicai_last_error = error_obj.get("message")
                else:
                    publicai_last_error = None
            logger.info("PublicAI Router health check completed", extra={
                "check_type": "publicai_router",
                "success": publicai_last_error is None,
                "results": publicai_results,
                "error": publicai_last_error
            })
        except json.JSONDecodeError:
            with data_lock:
                publicai_results = []
                publicai_last_run_timestamp = time.time()
                publicai_last_error = f"Invalid JSON output from litellm.py (publicai_router). Stdout: {result.stdout[:500]} Stderr: {result.stderr[:500]}"
            logger.error("Failed to decode JSON from litellm.py (publicai_router)", extra={
                "check_type": "publicai_router",
                "success": False,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "error": publicai_last_error
            })
    except subprocess.TimeoutExpired:
        with data_lock:
            publicai_results = []
            publicai_last_run_timestamp = time.time()
            publicai_last_error = f"PublicAI Router health check timed out after {CHECK_TIMEOUT_SECONDS}s"
        logger.error(f"PublicAI Router health check timed out after {CHECK_TIMEOUT_SECONDS}s", extra={
            "check_type": "publicai_router",
            "success": False,
            "error": publicai_last_error
        })
    except Exception as e:
        with data_lock:
            publicai_results = []
            publicai_last_run_timestamp = time.time()
            publicai_last_error = f"Exception running litellm.py (publicai_router): {e}"
        logger.error(f"Exception running litellm.py (publicai_router): {e}", exc_info=True, extra={
            "check_type": "publicai_router",
            "success": False,
            "error": publicai_last_error
        })

def run_currentai_router_check():
    global currentai_results, currentai_last_run_timestamp, currentai_last_error
    litellm_script = "/app/litellm.py"
    if not os.path.exists(litellm_script):
        litellm_script = os.path.abspath(os.path.join(os.path.dirname(__file__), "litellm.py"))
        
    try:
        result = subprocess.run(
            [sys.executable, litellm_script, "--router-name", "currentai_router", "-json"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=CHECK_TIMEOUT_SECONDS
        )
        try:
            data = json.loads(result.stdout)
            with data_lock:
                currentai_results = data.get("results", [])
                currentai_last_run_timestamp = time.time()
                error_obj = data.get("error")
                if error_obj:
                    currentai_last_error = error_obj.get("message")
                else:
                    currentai_last_error = None
            logger.info("CurrentAI Router health check completed", extra={
                "check_type": "currentai_router",
                "success": currentai_last_error is None,
                "results": currentai_results,
                "error": currentai_last_error
            })
        except json.JSONDecodeError:
            with data_lock:
                currentai_results = []
                currentai_last_run_timestamp = time.time()
                currentai_last_error = f"Invalid JSON output from litellm.py (currentai_router). Stdout: {result.stdout[:500]} Stderr: {result.stderr[:500]}"
            logger.error("Failed to decode JSON from litellm.py (currentai_router)", extra={
                "check_type": "currentai_router",
                "success": False,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "error": currentai_last_error
            })
    except subprocess.TimeoutExpired:
        with data_lock:
            currentai_results = []
            currentai_last_run_timestamp = time.time()
            currentai_last_error = f"CurrentAI Router health check timed out after {CHECK_TIMEOUT_SECONDS}s"
        logger.error(f"CurrentAI Router health check timed out after {CHECK_TIMEOUT_SECONDS}s", extra={
            "check_type": "currentai_router",
            "success": False,
            "error": currentai_last_error
        })
    except Exception as e:
        with data_lock:
            currentai_results = []
            currentai_last_run_timestamp = time.time()
            currentai_last_error = f"Exception running litellm.py (currentai_router): {e}"
        logger.error(f"Exception running litellm.py (currentai_router): {e}", exc_info=True, extra={
            "check_type": "currentai_router",
            "success": False,
            "error": currentai_last_error
        })

def run_zuplo_check():
    global zuplo_results, zuplo_last_run_timestamp, zuplo_last_error
    zuplo_script = "/app/zuplo.py"
    if not os.path.exists(zuplo_script):
        zuplo_script = os.path.abspath(os.path.join(os.path.dirname(__file__), "zuplo.py"))
        
    try:
        result = subprocess.run(
            [sys.executable, zuplo_script, "-json"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=CHECK_TIMEOUT_SECONDS
        )
        try:
            data = json.loads(result.stdout)
            with data_lock:
                zuplo_results = data.get("results", [])
                zuplo_last_run_timestamp = time.time()
                error_obj = data.get("error")
                if error_obj:
                    zuplo_last_error = error_obj.get("message")
                else:
                    zuplo_last_error = None
            logger.info("Zuplo health check completed", extra={
                "check_type": "zuplo",
                "success": zuplo_last_error is None,
                "results": zuplo_results,
                "error": zuplo_last_error
            })
        except json.JSONDecodeError:
            with data_lock:
                zuplo_results = []
                zuplo_last_run_timestamp = time.time()
                zuplo_last_error = f"Invalid JSON output from zuplo.py. Stdout: {result.stdout[:500]} Stderr: {result.stderr[:500]}"
            logger.error("Failed to decode JSON from zuplo.py", extra={
                "check_type": "zuplo",
                "success": False,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "error": zuplo_last_error
            })
    except subprocess.TimeoutExpired:
        with data_lock:
            zuplo_results = []
            zuplo_last_run_timestamp = time.time()
            zuplo_last_error = f"Zuplo health check timed out after {CHECK_TIMEOUT_SECONDS}s"
        logger.error(f"Zuplo health check timed out after {CHECK_TIMEOUT_SECONDS}s", extra={
            "check_type": "zuplo",
            "success": False,
            "error": zuplo_last_error
        })
    except Exception as e:
        with data_lock:
            zuplo_results = []
            zuplo_last_run_timestamp = time.time()
            zuplo_last_error = f"Exception running zuplo.py: {e}"
        logger.error(f"Exception running zuplo.py: {e}", exc_info=True, extra={
            "check_type": "zuplo",
            "success": False,
            "error": zuplo_last_error
        })

def minutely_scheduler_loop():
    interval = 120.0
    while True:
        start_time = time.time()
        try:
            logger.info("Running 2-minute health checks (Suppliers, PublicAI Router, CurrentAI Router)...")
            t_sup = threading.Thread(target=run_suppliers_check)
            t_pub = threading.Thread(target=run_publicai_router_check)
            t_cur = threading.Thread(target=run_currentai_router_check)
            t_sup.start()
            t_pub.start()
            t_cur.start()
            t_sup.join()
            t_pub.join()
            t_cur.join()
        except Exception as e:
            logger.error(f"Error in minutely_scheduler_loop: {e}", exc_info=True)
        elapsed = time.time() - start_time
        sleep_time = max(0.0, interval - elapsed)
        time.sleep(sleep_time)

def hourly_scheduler_loop():
    interval = 3600.0
    while True:
        start_time = time.time()
        try:
            logger.info("Running hourly health checks (HuggingFace, Zuplo)...")
            t_hf = threading.Thread(target=run_huggingface_check)
            t_zup = threading.Thread(target=run_zuplo_check)
            t_hf.start()
            t_zup.start()
            t_hf.join()
            t_zup.join()
        except Exception as e:
            logger.error(f"Error in hourly_scheduler_loop: {e}", exc_info=True)
        elapsed = time.time() - start_time
        sleep_time = max(0.0, interval - elapsed)
        time.sleep(sleep_time)

class MetricsHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Log server requests in JSON format
        logger.info(format % args, extra={
            "client_address": self.client_address[0],
            "request_line": self.requestline
        })

    def do_GET(self):
        if self.path == "/metrics":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
            self.end_headers()

            lines = []
            with data_lock:
                lines.append("# HELP huggingface_last_run_timestamp_seconds Unix timestamp of the last health check run")
                lines.append("# TYPE huggingface_last_run_timestamp_seconds gauge")
                lines.append(f"huggingface_last_run_timestamp_seconds {last_run_timestamp}")

                global_success = 1 if last_error is None else 0
                lines.append("# HELP huggingface_test_global_success Overall status of the health checks (1 = success, 0 = failure)")
                lines.append("# TYPE huggingface_test_global_success gauge")
                lines.append(f"huggingface_test_global_success {global_success}")

                lines.append("# HELP huggingface_model_test_success Success status of individual model test (1 = success, 0 = failure)")
                lines.append("# TYPE huggingface_model_test_success gauge")
                for r in latest_results:
                    model = r.get("model", "")
                    success_val = 1 if r.get("success", False) else 0
                    lines.append(f'huggingface_model_test_success{{model="{model}"}} {success_val}')

                lines.append("# HELP huggingface_model_ttft_seconds Time to First Token (TTFT) in seconds for model")
                lines.append("# TYPE huggingface_model_ttft_seconds gauge")
                for r in latest_results:
                    model = r.get("model", "")
                    ttft = r.get("ttft")
                    if ttft is not None:
                        lines.append(f'huggingface_model_ttft_seconds{{model="{model}"}} {ttft}')
                    else:
                        lines.append(f'huggingface_model_ttft_seconds{{model="{model}"}} NaN')

                # --- Suppliers Metrics ---
                lines.append("# HELP suppliers_last_run_timestamp_seconds Unix timestamp of the last health check run")
                lines.append("# TYPE suppliers_last_run_timestamp_seconds gauge")
                lines.append(f"suppliers_last_run_timestamp_seconds {suppliers_last_run_timestamp}")

                suppliers_global_success = 1 if suppliers_last_error is None else 0
                lines.append("# HELP suppliers_test_global_success Overall status of the health checks (1 = success, 0 = failure)")
                lines.append("# TYPE suppliers_test_global_success gauge")
                lines.append(f"suppliers_test_global_success {suppliers_global_success}")

                lines.append("# HELP suppliers_model_test_success Success status of individual model test (1 = success, 0 = failure)")
                lines.append("# TYPE suppliers_model_test_success gauge")
                for r in suppliers_results:
                    model = r.get("model", "")
                    success_val = 1 if r.get("success", False) else 0
                    lines.append(f'suppliers_model_test_success{{model="{model}"}} {success_val}')

                lines.append("# HELP suppliers_model_ttft_seconds Time to First Token (TTFT) in seconds for model")
                lines.append("# TYPE suppliers_model_ttft_seconds gauge")
                for r in suppliers_results:
                    model = r.get("model", "")
                    ttft = r.get("ttft")
                    if ttft is not None:
                        lines.append(f'suppliers_model_ttft_seconds{{model="{model}"}} {ttft}')
                    else:
                        lines.append(f'suppliers_model_ttft_seconds{{model="{model}"}} NaN')

                # --- PublicAI Router (LiteLLM) Metrics ---
                lines.append("# HELP publicai_router_last_run_timestamp_seconds Unix timestamp of the last health check run")
                lines.append("# TYPE publicai_router_last_run_timestamp_seconds gauge")
                lines.append(f"publicai_router_last_run_timestamp_seconds {publicai_last_run_timestamp}")

                publicai_global_success = 1 if publicai_last_error is None else 0
                lines.append("# HELP publicai_router_test_global_success Overall status of the health checks (1 = success, 0 = failure)")
                lines.append("# TYPE publicai_router_test_global_success gauge")
                lines.append(f"publicai_router_test_global_success {publicai_global_success}")

                lines.append("# HELP publicai_router_model_test_success Success status of individual model test (1 = success, 0 = failure)")
                lines.append("# TYPE publicai_router_model_test_success gauge")
                for r in publicai_results:
                    model = r.get("model", "")
                    success_val = 1 if r.get("success", False) else 0
                    lines.append(f'publicai_router_model_test_success{{model="{model}"}} {success_val}')

                lines.append("# HELP publicai_router_model_ttft_seconds Time to First Token (TTFT) in seconds for model")
                lines.append("# TYPE publicai_router_model_ttft_seconds gauge")
                for r in publicai_results:
                    model = r.get("model", "")
                    ttft = r.get("ttft")
                    if ttft is not None:
                        lines.append(f'publicai_router_model_ttft_seconds{{model="{model}"}} {ttft}')
                    else:
                        lines.append(f'publicai_router_model_ttft_seconds{{model="{model}"}} NaN')

                # --- CurrentAI Router (LiteLLM) Metrics ---
                lines.append("# HELP currentai_router_last_run_timestamp_seconds Unix timestamp of the last health check run")
                lines.append("# TYPE currentai_router_last_run_timestamp_seconds gauge")
                lines.append(f"currentai_router_last_run_timestamp_seconds {currentai_last_run_timestamp}")

                currentai_global_success = 1 if currentai_last_error is None else 0
                lines.append("# HELP currentai_router_test_global_success Overall status of the health checks (1 = success, 0 = failure)")
                lines.append("# TYPE currentai_router_test_global_success gauge")
                lines.append(f"currentai_router_test_global_success {currentai_global_success}")

                lines.append("# HELP currentai_router_model_test_success Success status of individual model test (1 = success, 0 = failure)")
                lines.append("# TYPE currentai_router_model_test_success gauge")
                for r in currentai_results:
                    model = r.get("model", "")
                    success_val = 1 if r.get("success", False) else 0
                    lines.append(f'currentai_router_model_test_success{{model="{model}"}} {success_val}')

                lines.append("# HELP currentai_router_model_ttft_seconds Time to First Token (TTFT) in seconds for model")
                lines.append("# TYPE currentai_router_model_ttft_seconds gauge")
                for r in currentai_results:
                    model = r.get("model", "")
                    ttft = r.get("ttft")
                    if ttft is not None:
                        lines.append(f'currentai_router_model_ttft_seconds{{model="{model}"}} {ttft}')
                    else:
                        lines.append(f'currentai_router_model_ttft_seconds{{model="{model}"}} NaN')

                # --- Zuplo Metrics ---
                lines.append("# HELP zuplo_last_run_timestamp_seconds Unix timestamp of the last health check run")
                lines.append("# TYPE zuplo_last_run_timestamp_seconds gauge")
                lines.append(f"zuplo_last_run_timestamp_seconds {zuplo_last_run_timestamp}")

                zuplo_global_success = 1 if zuplo_last_error is None else 0
                lines.append("# HELP zuplo_test_global_success Overall status of the health checks (1 = success, 0 = failure)")
                lines.append("# TYPE zuplo_test_global_success gauge")
                lines.append(f"zuplo_test_global_success {zuplo_global_success}")

                lines.append("# HELP zuplo_model_test_success Success status of individual model test (1 = success, 0 = failure)")
                lines.append("# TYPE zuplo_model_test_success gauge")
                for r in zuplo_results:
                    model = r.get("model", "")
                    success_val = 1 if r.get("success", False) else 0
                    lines.append(f'zuplo_model_test_success{{model="{model}"}} {success_val}')

                lines.append("# HELP zuplo_model_ttft_seconds Time to First Token (TTFT) in seconds for model")
                lines.append("# TYPE zuplo_model_ttft_seconds gauge")
                for r in zuplo_results:
                    model = r.get("model", "")
                    ttft = r.get("ttft")
                    if ttft is not None:
                        lines.append(f'zuplo_model_ttft_seconds{{model="{model}"}} {ttft}')
                    else:
                        lines.append(f'zuplo_model_ttft_seconds{{model="{model}"}} NaN')

            self.wfile.write(("\n".join(lines) + "\n").encode("utf-8"))

        elif self.path in ("/healthz", "/"):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            with data_lock:
                status = {
                    "last_run_timestamp": max(last_run_timestamp, suppliers_last_run_timestamp, publicai_last_run_timestamp, currentai_last_run_timestamp, zuplo_last_run_timestamp),
                    "last_error": last_error or suppliers_last_error or publicai_last_error or currentai_last_error or zuplo_last_error,
                    "success": last_error is None and suppliers_last_error is None and publicai_last_error is None and currentai_last_error is None and zuplo_last_error is None,
                    "huggingface": {
                        "last_run_timestamp": last_run_timestamp,
                        "last_error": last_error,
                        "success": last_error is None
                    },
                    "suppliers": {
                        "last_run_timestamp": suppliers_last_run_timestamp,
                        "last_error": suppliers_last_error,
                        "success": suppliers_last_error is None
                    },
                    "publicai_router": {
                        "last_run_timestamp": publicai_last_run_timestamp,
                        "last_error": publicai_last_error,
                        "success": publicai_last_error is None
                    },
                    "currentai_router": {
                        "last_run_timestamp": currentai_last_run_timestamp,
                        "last_error": currentai_last_error,
                        "success": currentai_last_error is None
                    },
                    "zuplo": {
                        "last_run_timestamp": zuplo_last_run_timestamp,
                        "last_error": zuplo_last_error,
                        "success": zuplo_last_error is None
                    }
                }
            self.wfile.write(json.dumps(status, indent=2).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not Found")

def main():
    t_min = threading.Thread(target=minutely_scheduler_loop, daemon=True)
    t_min.start()

    t_hour = threading.Thread(target=hourly_scheduler_loop, daemon=True)
    t_hour.start()

    port = int(os.environ.get("PORT", 8000))
    server_address = ("", port)
    httpd = HTTPServer(server_address, MetricsHandler)
    logger.info(f"Starting server on port {port}...")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    logger.info("Server stopped.")

if __name__ == "__main__":
    main()
