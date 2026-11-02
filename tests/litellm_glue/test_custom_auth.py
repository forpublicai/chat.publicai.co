"""
Unit tests for charts/platform/charts/litellm/custom_auth.py.

These tests never talk to a real LiteLLM proxy: httpx.AsyncClient is mocked
in every case. See tests/litellm_glue/README.md for how to run them.
"""
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import custom_auth


def _run(coro):
    return asyncio.run(coro)


def _mock_client(get_response=None, post_response=None):
    """Build a mock that behaves like `async with httpx.AsyncClient() as client`."""
    client = MagicMock()
    client.get = AsyncMock(return_value=get_response)
    client.post = AsyncMock(return_value=post_response)

    async_client_cm = MagicMock()
    async_client_cm.__aenter__ = AsyncMock(return_value=client)
    async_client_cm.__aexit__ = AsyncMock(return_value=False)
    return async_client_cm, client


def _response(status_code, text=""):
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = text
    return resp


def test_new_user_gets_customer_and_budget_created():
    async_cm, client = _mock_client(
        get_response=_response(400),
        post_response=_response(201),
    )
    with patch.object(custom_auth.httpx, "AsyncClient", return_value=async_cm):
        result = _run(custom_auth.ensure_end_user_with_budget("user-1", "u@example.com"))

    assert result is True
    _, kwargs = client.post.call_args
    assert json.loads(json.dumps(kwargs["json"])) == {
        "user_id": "user-1",
        "budget_id": "public_ai_free",
    }


def test_existing_user_is_not_recreated():
    async_cm, client = _mock_client(get_response=_response(200))
    with patch.object(custom_auth.httpx, "AsyncClient", return_value=async_cm):
        result = _run(custom_auth.ensure_end_user_with_budget("user-2"))

    assert result is True
    client.post.assert_not_called()


def test_customer_creation_failure_returns_false():
    async_cm, _ = _mock_client(
        get_response=_response(400),
        post_response=_response(500, "internal error"),
    )
    with patch.object(custom_auth.httpx, "AsyncClient", return_value=async_cm):
        result = _run(custom_auth.ensure_end_user_with_budget("user-3"))

    assert result is False


def test_unexpected_lookup_error_returns_false_without_raising():
    async_cm, client = _mock_client()
    client.get.side_effect = RuntimeError("connection reset")
    with patch.object(custom_auth.httpx, "AsyncClient", return_value=async_cm):
        result = _run(custom_auth.ensure_end_user_with_budget("user-4"))

    assert result is False


def _request(headers, path="/v1/chat/completions"):
    return custom_auth.Request(headers=headers, url=path)


def test_openwebui_headers_trigger_provisioning():
    request = _request({"x-openwebui-user-id": "owui-1"})
    with patch.object(
        custom_auth, "ensure_end_user_with_budget", new=AsyncMock(return_value=True)
    ) as ensure_mock:
        result = _run(custom_auth.user_api_key_auth(request, "sk-test"))

    ensure_mock.assert_awaited_once_with("owui-1", "")
    assert result == "sk-test"


def test_zuplo_headers_trigger_provisioning():
    request = _request(
        {"x-zuplo-user-id": "zuplo-1", "x-zuplo-user-email": "dev@example.com"}
    )
    with patch.object(
        custom_auth, "ensure_end_user_with_budget", new=AsyncMock(return_value=True)
    ) as ensure_mock:
        result = _run(custom_auth.user_api_key_auth(request, "sk-test"))

    ensure_mock.assert_awaited_once_with("zuplo-1", "dev@example.com")
    assert result == "sk-test"


def test_no_recognized_headers_skips_provisioning():
    request = _request({})
    with patch.object(
        custom_auth, "ensure_end_user_with_budget", new=AsyncMock()
    ) as ensure_mock:
        result = _run(custom_auth.user_api_key_auth(request, "sk-test"))

    ensure_mock.assert_not_awaited()
    assert result == "sk-test"


def test_non_completion_path_skips_custom_auth_entirely():
    request = _request({"x-openwebui-user-id": "owui-2"}, path="/health")
    with patch.object(
        custom_auth, "ensure_end_user_with_budget", new=AsyncMock()
    ) as ensure_mock:
        result = _run(custom_auth.user_api_key_auth(request, "sk-test"))

    ensure_mock.assert_not_awaited()
    assert result == "sk-test"


def test_header_parsing_error_falls_back_to_api_key():
    class ExplodingRequest:
        url = "/v1/chat/completions"

        @property
        def headers(self):
            raise ValueError("boom")

    result = _run(custom_auth.user_api_key_auth(ExplodingRequest(), "sk-fallback"))

    assert result == "sk-fallback"
