#!/usr/bin/env python3
"""External black-box HTTP availability checks."""
import json
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
TIMEOUT_SECONDS = 10


def classify_status(status, expected):
    """Return whether an HTTP status satisfies an inclusive status rule."""
    return expected["min_status"] <= status <= expected["max_status"]


def check_endpoint(endpoint):
    started = time.monotonic()
    status = None
    try:
        with urllib.request.urlopen(endpoint["url"], timeout=TIMEOUT_SECONDS) as response:
            status = response.status
    except urllib.error.HTTPError as error:
        # HTTP errors still prove that the service answered the request.
        status = error.code
    except Exception as error:  # DNS, TLS, timeout, and connection failures.
        latency = round((time.monotonic() - started) * 1000, 2)
        return {"url": endpoint["url"], "status": None, "latency_ms": latency,
                "result": "fail", "error": str(error)}

    latency = round((time.monotonic() - started) * 1000, 2)
    ok = classify_status(status, endpoint["expected_status"])
    return {"url": endpoint["url"], "status": status, "latency_ms": latency,
            "result": "ok" if ok else "fail"}


def main():
    endpoints = json.loads((HERE / "endpoints.json").read_text())
    results = [check_endpoint(endpoint) for endpoint in endpoints]
    output = Path("probe-results.json")
    output.write_text(json.dumps(results, indent=2) + "\n")
    print("| Endpoint | Status | Latency (ms) | Result |")
    print("|---|---:|---:|---|")
    for result in results:
        print(f"| {result['url']} | {result['status'] or 'n/a'} | {result['latency_ms']:.2f} | {result['result']} |")
    return 1 if any(result["result"] == "fail" for result in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
