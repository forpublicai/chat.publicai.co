"""
Unit tests for charts/platform/charts/litellm/custom_lago_callback.py.

No real HTTP calls are made: sync_http_handler/async_http_handler are mocked
in every case. See tests/litellm_glue/README.md for how to run them.
"""
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import custom_lago_callback as lago_module

lago_callback = lago_module.lago_callback


def _run(coro):
    return asyncio.run(coro)


def _kwargs_with_subscription(subscription_id="sub-123", model="mistral-small-3-1"):
    return {
        "model": model,
        "litellm_params": {
            "proxy_server_request": {
                "headers": {"x-zuplo-subscription-id": subscription_id}
            }
        },
    }


def _response_obj(prompt_tokens, completion_tokens):
    import litellm

    resp = litellm.ModelResponse()
    resp["usage"] = {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
    }
    return resp


def test_normalize_model_name_known_mapping():
    assert (
        lago_callback._normalize_model_name("mistral-small-3-1")
        == "mistralai/mistral-small-3-1"
    )


def test_normalize_model_name_passthrough_for_unknown_model():
    assert lago_callback._normalize_model_name("some/unmapped-model") == "some/unmapped-model"


def test_subscription_id_read_from_header():
    kwargs = _kwargs_with_subscription("sub-from-header")
    assert lago_callback._get_subscription_id(kwargs) == "sub-from-header"


def test_subscription_id_falls_back_to_metadata():
    kwargs = {
        "litellm_params": {
            "proxy_server_request": {"headers": {}},
            "metadata": {"subscription_id": "sub-from-metadata"},
        }
    }
    assert lago_callback._get_subscription_id(kwargs) == "sub-from-metadata"


def test_subscription_id_missing_returns_none():
    kwargs = {"litellm_params": {"proxy_server_request": {"headers": {}}}}
    assert lago_callback._get_subscription_id(kwargs) is None


def test_create_event_payload_shape_for_input_tokens():
    event = lago_callback._create_event("sub-1", "mistral-small-3-1", 42, "input")

    payload = event["event"]
    assert payload["external_subscription_id"] == "sub-1"
    assert payload["code"] == "public_ai_models"
    assert payload["properties"] == {
        "tokens": 42,
        "model": "mistralai/mistral-small-3-1",
        "type": "input",
    }
    assert "transaction_id" in payload
    assert isinstance(payload["timestamp"], int)


def test_log_success_event_splits_input_and_output_tokens():
    mock_post = MagicMock(return_value=MagicMock(raise_for_status=MagicMock()))
    with patch.object(lago_callback.sync_http_handler, "post", mock_post):
        lago_callback.log_success_event(
            kwargs=_kwargs_with_subscription(),
            response_obj=_response_obj(10, 5),
            start_time=None,
            end_time=None,
        )

    assert mock_post.call_count == 2
    sent_events = [json.loads(call.kwargs["data"]) for call in mock_post.call_args_list]
    types_sent = {e["event"]["properties"]["type"]: e["event"]["properties"]["tokens"] for e in sent_events}
    assert types_sent == {"input": 10, "output": 5}


def test_log_success_event_without_subscription_id_skips_lago_entirely():
    mock_post = MagicMock()
    with patch.object(lago_callback.sync_http_handler, "post", mock_post):
        lago_callback.log_success_event(
            kwargs={"litellm_params": {"proxy_server_request": {"headers": {}}}},
            response_obj=_response_obj(10, 5),
            start_time=None,
            end_time=None,
        )

    mock_post.assert_not_called()


def test_log_success_event_zero_tokens_skips_lago():
    mock_post = MagicMock()
    with patch.object(lago_callback.sync_http_handler, "post", mock_post):
        lago_callback.log_success_event(
            kwargs=_kwargs_with_subscription(),
            response_obj=_response_obj(0, 0),
            start_time=None,
            end_time=None,
        )

    mock_post.assert_not_called()


def test_log_success_event_swallows_lago_http_errors():
    mock_post = MagicMock(side_effect=RuntimeError("lago is down"))
    with patch.object(lago_callback.sync_http_handler, "post", mock_post):
        # Should not raise: a billing outage must never break the chat request.
        lago_callback.log_success_event(
            kwargs=_kwargs_with_subscription(),
            response_obj=_response_obj(10, 5),
            start_time=None,
            end_time=None,
        )


def test_async_log_success_event_splits_input_and_output_tokens():
    mock_post = AsyncMock(return_value=MagicMock(raise_for_status=MagicMock()))
    with patch.object(lago_callback.async_http_handler, "post", mock_post):
        _run(
            lago_callback.async_log_success_event(
                kwargs=_kwargs_with_subscription(),
                response_obj=_response_obj(7, 3),
                start_time=None,
                end_time=None,
            )
        )

    assert mock_post.await_count == 2
    sent_events = [json.loads(call.kwargs["data"]) for call in mock_post.await_args_list]
    types_sent = {e["event"]["properties"]["type"]: e["event"]["properties"]["tokens"] for e in sent_events}
    assert types_sent == {"input": 7, "output": 3}


def test_async_log_success_event_swallows_lago_http_errors():
    mock_post = AsyncMock(side_effect=RuntimeError("lago is down"))
    with patch.object(lago_callback.async_http_handler, "post", mock_post):
        _run(
            lago_callback.async_log_success_event(
                kwargs=_kwargs_with_subscription(),
                response_obj=_response_obj(7, 3),
                start_time=None,
                end_time=None,
            )
        )


def test_validate_environment_raises_on_missing_keys():
    import os

    original = os.environ.pop("LAGO_API_KEY")
    try:
        try:
            lago_callback.validate_environment()
        except Exception as exc:
            assert "LAGO_API_KEY" in str(exc)
        else:
            raise AssertionError("expected validate_environment to raise")
    finally:
        os.environ["LAGO_API_KEY"] = original
