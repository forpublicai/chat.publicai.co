import sys
import urllib.error
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "probes"))
import probe


def test_expected_status_boundaries():
    expected = {"min_status": 200, "max_status": 399}
    assert probe.classify_status(200, expected)
    assert probe.classify_status(399, expected)
    assert not probe.classify_status(199, expected)
    assert not probe.classify_status(400, expected)


def test_api_accepts_unauthenticated_http_errors():
    expected = {"min_status": 100, "max_status": 499}
    endpoint = {"url": "https://api.publicai.co/v1/models", "expected_status": expected}
    error = urllib.error.HTTPError(endpoint["url"], 403, "Forbidden", {}, None)
    with patch.object(probe.urllib.request, "urlopen", side_effect=error):
        result = probe.check_endpoint(endpoint)
    assert result["status"] == 403
    assert result["result"] == "ok"


def test_connection_failure_fails():
    endpoint = {"url": "https://example.invalid", "expected_status": {"min_status": 200, "max_status": 399}}
    with patch.object(probe.urllib.request, "urlopen", side_effect=TimeoutError("timed out")):
        result = probe.check_endpoint(endpoint)
    assert result["status"] is None
    assert result["result"] == "fail"
