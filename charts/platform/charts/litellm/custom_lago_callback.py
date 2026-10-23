"""
Custom LiteLLM callback to send separate input/output token events to Lago.

This callback replaces the default Lago integration to send two separate events:
1. Input tokens event with code "public_ai_models" and type "input"
2. Output tokens event with code "public_ai_models" and type "output"

Based on https://github.com/BerriAI/litellm/blob/main/litellm/integrations/lago.py
"""
import json
import os
from litellm._uuid import uuid
from typing import Optional, Dict
import yaml
import httpx
import litellm
from litellm._logging import verbose_logger
from litellm.integrations.custom_logger import CustomLogger
from litellm.llms.custom_httpx.http_handler import (
    HTTPHandler,
    get_async_httpx_client,
    httpxSpecialProvider,
)


def get_utc_datetime():
    import datetime as dt
    from datetime import datetime

    if hasattr(dt, "UTC"):
        return datetime.now(dt.UTC)  # type: ignore
    else:
        return datetime.utcnow()  # type: ignore


class LagoCustomCallback(CustomLogger):
    def __init__(self) -> None:
        super().__init__()
        print("🚀 LagoCustomCallback initializing...")
        self.validate_environment()
        self.async_http_handler = get_async_httpx_client(
            llm_provider=httpxSpecialProvider.LoggingCallback
        )
        self.sync_http_handler = HTTPHandler()
        self.dynamic_model_mapping: dict = self._load_model_mapping_from_config()
        print("✅ LagoCustomCallback initialized successfully")

    def _load_model_mapping_from_config(self) -> dict:
        """
        Dynamically loads model name mappings from LiteLLM config (/app/config.yaml or local fallback).
        Automatically maps backend deployment models (litellm_params.model) to public billing IDs (model_name).
        """
        mapping = {}
        candidate_paths = [
            os.getenv("LITELLM_CONFIG_PATH"),
            "/app/config.yaml",
            "config.yaml",
            os.path.join(os.path.dirname(__file__), "config.yaml"),
        ]

        for path in candidate_paths:
            if path and os.path.isfile(path):
                try:
                    import yaml
                    with open(path, "r") as f:
                        data = yaml.safe_load(f) or {}
                    model_list = data.get("model_list", [])
                    for item in model_list:
                        if not isinstance(item, dict):
                            continue
                        model_name = item.get("model_name")
                        litellm_model = (item.get("litellm_params") or {}).get("model")
                        if litellm_model and model_name:
                            mapping[str(litellm_model)] = str(model_name)
                        if model_name:
                            mapping[str(model_name)] = str(model_name)
                    print(f"✅ Loaded {len(mapping)} model mappings from {path}")
                    return mapping
                except Exception as e:
                    verbose_logger.error(f"Error loading model mapping from {path}: {e}")
        return mapping

    def validate_environment(self):
        """
        Expects LAGO_API_BASE, LAGO_API_KEY, LAGO_API_EVENT_CODE in the environment
        """
        missing_keys = []
        if os.getenv("LAGO_API_KEY", None) is None:
            missing_keys.append("LAGO_API_KEY")

        if os.getenv("LAGO_API_BASE", None) is None:
            missing_keys.append("LAGO_API_BASE")

        if os.getenv("LAGO_API_EVENT_CODE", None) is None:
            missing_keys.append("LAGO_API_EVENT_CODE")

        if len(missing_keys) > 0:
            raise Exception("Missing keys={} in environment.".format(missing_keys))

    def _get_subscription_id(self, kwargs: dict) -> Optional[str]:
        """Extract subscription ID from request headers or metadata"""
        litellm_params = kwargs.get("litellm_params", {}) or {}
        proxy_server_request = litellm_params.get("proxy_server_request") or {}

        # Try to get subscription ID from custom header first
        headers = proxy_server_request.get("headers", {}) or {}
        subscription_id = headers.get("x-zuplo-subscription-id", None)

        if subscription_id:
            verbose_logger.debug(f"Found subscription ID in headers: {subscription_id}")
            return subscription_id

        # Fallback: try to get from metadata
        subscription_id = litellm_params.get("metadata", {}).get("subscription_id", None)
        if subscription_id:
            verbose_logger.debug(f"Found subscription ID in metadata: {subscription_id}")
            return subscription_id

        verbose_logger.debug("No subscription ID found in headers or metadata")
        return None

    def _extract_canonical_model_name(self, kwargs: dict) -> str:
        """
        Extract the canonical user-facing model name from the LiteLLM request context.
        Priority:
        1. model_info.billing_model (explicitly stamped by Helm)
        2. Router model_group / standard_logging_object (logical proxy model)
        3. Client requested model in proxy_server_request body
        4. Underlying deployment model in kwargs['model']
        """
        litellm_params = kwargs.get("litellm_params", {}) or {}

        # 1. Check model_info for explicit billing_model
        model_info = litellm_params.get("model_info", {}) or kwargs.get("model_info", {}) or {}
        if isinstance(model_info, dict) and model_info.get("billing_model"):
            return str(model_info["billing_model"])

        # 2. Check LiteLLM router model_group (logical user-facing group)
        model_group = (
            kwargs.get("model_group")
            or (kwargs.get("standard_logging_object") or {}).get("model_group")
            or litellm_params.get("metadata", {}).get("model_group")
        )
        if model_group:
            return str(model_group)

        # 3. Check proxy_server_request body (original client payload)
        proxy_request = litellm_params.get("proxy_server_request") or {}
        body = proxy_request.get("body") or {}
        if isinstance(body, dict) and body.get("model"):
            return str(body["model"])

        # 4. Fallback to physical execution model
        return kwargs.get("model", "unknown")

    def _normalize_model_name(self, model: str) -> str:
        """
        Normalize model names to match Lago billing codes.
        1. Check dynamic mapping loaded from config.yaml
        2. Check static router / alias exceptions
        3. Algorithmic cleanup (strip provider prefix / deployment tags)
        4. Pass through
        """
        # If mapping is empty (e.g. config was not available at boot), attempt reload once
        if not getattr(self, "dynamic_model_mapping", None):
            self.dynamic_model_mapping = self._load_model_mapping_from_config()

        # 1. Direct dynamic mapping from config.yaml (litellm_params.model -> model_name)
        if self.dynamic_model_mapping and model in self.dynamic_model_mapping:
            return self.dynamic_model_mapping[model]

        # 2. Static router and legacy aliases
        static_aliases = {
            "smart-router": "smart-router",
            "auto_router/complexity_router": "smart-router",
        }
        if model in static_aliases:
            return static_aliases[model]

        # 3. Algorithmic normalization
        clean = model
        # Strip provider prefixes like 'openai/'
        if clean.startswith("openai/"):
            clean = clean[len("openai/") :]
        # Strip trailing deployment or provider tags like ':featherless-ai', ':cohere', ':40b'
        if ":" in clean and not clean.startswith("arn:"):
            clean = clean.split(":")[0]

        if self.dynamic_model_mapping and clean in self.dynamic_model_mapping:
            return self.dynamic_model_mapping[clean]

        # If it's already in the format (org/model), return as-is
        verbose_logger.debug(f"ℹ️ Model '{model}' normalized to '{clean}'")
        return clean

    def _create_event(self, subscription_id: str, model: str, tokens: int, event_type: str) -> dict:
        """Create a single Lago event"""
        # Normalize the model name to match Lago billing codes
        normalized_model = self._normalize_model_name(model)

        return {
            "event": {
                "transaction_id": str(uuid.uuid4()),
                "external_subscription_id": subscription_id,
                "code": os.getenv("LAGO_API_EVENT_CODE", "public_ai_models"),
                "timestamp": int(get_utc_datetime().timestamp()),
                "properties": {
                    "tokens": tokens,
                    "model": normalized_model,
                    "type": event_type
                }
            }
        }

    def log_success_event(self, kwargs, response_obj, start_time, end_time):
        """Synchronous success event logging"""
        try:
            print("🔍 Lago sync callback triggered")

            # Get subscription ID
            subscription_id = self._get_subscription_id(kwargs)
            if not subscription_id:
                verbose_logger.debug("⚠️ No subscription ID found, skipping Lago events")
                return

            # Extract canonical model and usage
            model = self._extract_canonical_model_name(kwargs)
            usage = {}
            if (
                isinstance(response_obj, litellm.ModelResponse)
                or isinstance(response_obj, litellm.EmbeddingResponse)
            ) and hasattr(response_obj, "usage"):
                usage = {
                    "prompt_tokens": response_obj["usage"].get("prompt_tokens", 0),
                    "completion_tokens": response_obj["usage"].get("completion_tokens", 0),
                }

            prompt_tokens = usage.get("prompt_tokens", 0)
            completion_tokens = usage.get("completion_tokens", 0)

            if prompt_tokens == 0 and completion_tokens == 0:
                verbose_logger.debug("⚠️ No tokens found in response")
                return

            print(f"📊 Sending Lago events for subscription: {subscription_id}, prompt:{prompt_tokens}, completion:{completion_tokens}")

            # Setup URL and headers
            _url = os.getenv("LAGO_API_BASE")
            if _url.endswith("/"):
                _url += "api/v1/events"
            else:
                _url += "/api/v1/events"

            api_key = os.getenv("LAGO_API_KEY")
            _headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            }

            # Send input tokens event
            if prompt_tokens > 0:
                input_event = self._create_event(subscription_id, model, prompt_tokens, "input")
                response = self.sync_http_handler.post(
                    url=_url,
                    data=json.dumps(input_event),
                    headers=_headers,
                )
                response.raise_for_status()
                print(f"✅ Input event sent: {prompt_tokens} tokens")

            # Send output tokens event
            if completion_tokens > 0:
                output_event = self._create_event(subscription_id, model, completion_tokens, "output")
                response = self.sync_http_handler.post(
                    url=_url,
                    data=json.dumps(output_event),
                    headers=_headers,
                )
                response.raise_for_status()
                print(f"✅ Output event sent: {completion_tokens} tokens")

        except Exception as e:
            verbose_logger.error(f"❌ Error in Lago sync callback: {str(e)}")
            # Don't raise - we don't want billing errors to block API calls

    async def async_log_success_event(self, kwargs, response_obj, start_time, end_time):
        """Async success event logging"""
        try:
            print("🔍 Lago async callback triggered")

            # Get subscription ID
            subscription_id = self._get_subscription_id(kwargs)
            if not subscription_id:
                verbose_logger.debug("⚠️ No subscription ID found, skipping Lago events")
                return

            # Extract canonical model and usage
            model = self._extract_canonical_model_name(kwargs)
            usage = {}
            if (
                isinstance(response_obj, litellm.ModelResponse)
                or isinstance(response_obj, litellm.EmbeddingResponse)
            ) and hasattr(response_obj, "usage"):
                usage = {
                    "prompt_tokens": response_obj["usage"].get("prompt_tokens", 0),
                    "completion_tokens": response_obj["usage"].get("completion_tokens", 0),
                }

            prompt_tokens = usage.get("prompt_tokens", 0)
            completion_tokens = usage.get("completion_tokens", 0)

            if prompt_tokens == 0 and completion_tokens == 0:
                verbose_logger.debug("⚠️ No tokens found in response")
                return

            print(f"📊 Sending Lago events for subscription: {subscription_id}, prompt:{prompt_tokens}, completion:{completion_tokens}")

            # Setup URL and headers
            _url = os.getenv("LAGO_API_BASE")
            if _url.endswith("/"):
                _url += "api/v1/events"
            else:
                _url += "/api/v1/events"

            api_key = os.getenv("LAGO_API_KEY")
            _headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            }

            # Send input tokens event
            if prompt_tokens > 0:
                input_event = self._create_event(subscription_id, model, prompt_tokens, "input")
                response = await self.async_http_handler.post(
                    url=_url,
                    data=json.dumps(input_event),
                    headers=_headers,
                )
                response.raise_for_status()
                print(f"✅ Input event sent: {prompt_tokens} tokens")

            # Send output tokens event
            if completion_tokens > 0:
                output_event = self._create_event(subscription_id, model, completion_tokens, "output")
                response = await self.async_http_handler.post(
                    url=_url,
                    data=json.dumps(output_event),
                    headers=_headers,
                )
                response.raise_for_status()
                print(f"✅ Output event sent: {completion_tokens} tokens")

        except Exception as e:
            verbose_logger.error(f"❌ Error in Lago async callback: {str(e)}")
            # Don't raise - we don't want billing errors to block API calls


# Create singleton instance
lago_callback = LagoCustomCallback()
