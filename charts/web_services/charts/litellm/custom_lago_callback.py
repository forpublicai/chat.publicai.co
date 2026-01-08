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
from typing import Literal, Optional
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
        print("✅ LagoCustomCallback initialized successfully")

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

    def _get_customer_id(self, kwargs: dict) -> Optional[str]:
        """Extract customer ID based on LAGO_API_CHARGE_BY setting"""
        litellm_params = kwargs.get("litellm_params", {}) or {}
        proxy_server_request = litellm_params.get("proxy_server_request") or {}
        end_user_id = proxy_server_request.get("body", {}).get("user", None)
        user_id = litellm_params.get("metadata", {}).get("user_api_key_user_id", None)
        team_id = litellm_params.get("metadata", {}).get("user_api_key_team_id", None)

        charge_by: Literal["end_user_id", "team_id", "user_id"] = "end_user_id"
        external_customer_id: Optional[str] = None

        if os.getenv("LAGO_API_CHARGE_BY", None) is not None and isinstance(
            os.environ["LAGO_API_CHARGE_BY"], str
        ):
            if os.environ["LAGO_API_CHARGE_BY"] in [
                "end_user_id",
                "user_id",
                "team_id",
            ]:
                charge_by = os.environ["LAGO_API_CHARGE_BY"]  # type: ignore

        if charge_by == "end_user_id":
            external_customer_id = end_user_id
        elif charge_by == "team_id":
            external_customer_id = team_id
        elif charge_by == "user_id":
            external_customer_id = user_id

        return external_customer_id

    def _normalize_model_name(self, model: str) -> str:
        """
        Normalize model names to match Lago billing codes.
        Maps internal LiteLLM model names to user-facing model names.
        """
        # Model name mapping: litellm model -> lago billing name
        model_mapping = {
            # Bedrock models
            "bedrock/eu.meta.llama3-2-3b-instruct-v1:0": "meta-llama/Llama-3.2-3B-Instruct",
            "bedrock/cohere.embed-multilingual-v3": "Cohere/Cohere-embed-multilingual-v3.0",
            "bedrock/cohere.rerank-v3-5:0": "Cohere/rerank-v3.5",

            # Apertus models (various endpoints with version suffixes)
            "Apertus-8B-Instruct-2509": "swiss-ai/apertus-8b-instruct",
            "swiss-ai/Apertus-8B-Instruct-2509": "swiss-ai/apertus-8b-instruct",
            "apertus-8b-instruct": "swiss-ai/apertus-8b-instruct",
            "Apertus-70B-Instruct-2509": "swiss-ai/apertus-70b-instruct",
            "swiss-ai/Apertus-70B-Instruct-2509": "swiss-ai/apertus-70b-instruct",
            "apertus-70b-instruct": "swiss-ai/apertus-70b-instruct",
            "swiss-ai/Apertus-70B-2509": "swiss-ai/apertus-70b-instruct",
            "swiss-ai/Apertus-8B-2509": "swiss-ai/apertus-8b-instruct",

            # Olmo models
            "Olmo-3-7B-Instruct": "allenai/Olmo-3-7B-Instruct",
            "allenai/Olmo-3-7B-Instruct": "allenai/Olmo-3-7B-Instruct",
            "Olmo-3-7B-Think": "allenai/Olmo-3-7B-Think",
            "Olmo-3-32B-Think": "allenai/Olmo-3-32B-Think",
            "Olmo-3-32B-Instruct": "allenai/Olmo-3.1-32B-Instruct",
            "Olmo-3.1-32B-Instruct": "allenai/Olmo-3.1-32B-Instruct",


            # SeaLion models
            "aisingapore/Gemma-SEA-LION-v4-27B-IT": "aisingapore/Gemma-SEA-LION-v4-27B-IT",
            "aisingapore/Qwen-SEA-LION-v4-32B-IT": "aisingapore/Qwen-SEA-LION-v4-32B-IT",

            # Spanish models
            "/root/.cache/huggingface/ALIA-40b-instruct_Q8_0/ALIA-40b-instruct_bos_Q8_0.gguf": "BSC-LT/ALIA-40b-instruct_Q8_0",
            "BSC-LT/salamandra-7b-instruct-tools-16k": "BSC-LT/salamandra-7b-instruct-tools-16k",
            "BSC-LT/salamandra-7b-instruct": "BSC-LT/salamandra-7b-instruct",

            # Mistral
            "mistral-small-3-1": "mistralai/mistral-small-3-1",

            # Dicta
            "DictaLM-3.0-24B-Thinking": "dicta-il/DictaLM-3.0-24B-Thinking",
        }

        # Try direct mapping first
        if model in model_mapping:
            return model_mapping[model]

        # If it's already in the correct format (org/model), return as-is
        return model

    def _create_event(self, customer_id: str, model: str, tokens: int, event_type: str) -> dict:
        """Create a single Lago event"""
        # Normalize the model name to match Lago billing codes
        normalized_model = self._normalize_model_name(model)

        return {
            "event": {
                "transaction_id": str(uuid.uuid4()),
                "external_subscription_id": customer_id,
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

            # Get customer ID
            customer_id = self._get_customer_id(kwargs)
            if not customer_id:
                verbose_logger.debug("⚠️ No customer ID found, skipping Lago events")
                return

            # Extract model and usage
            model = kwargs.get("model", "unknown")
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

            print(f"📊 Sending Lago events for customer: {customer_id}, prompt:{prompt_tokens}, completion:{completion_tokens}")

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
                input_event = self._create_event(customer_id, model, prompt_tokens, "input")
                response = self.sync_http_handler.post(
                    url=_url,
                    data=json.dumps(input_event),
                    headers=_headers,
                )
                response.raise_for_status()
                print(f"✅ Input event sent: {prompt_tokens} tokens")

            # Send output tokens event
            if completion_tokens > 0:
                output_event = self._create_event(customer_id, model, completion_tokens, "output")
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

            # Get customer ID
            customer_id = self._get_customer_id(kwargs)
            if not customer_id:
                verbose_logger.debug("⚠️ No customer ID found, skipping Lago events")
                return

            # Extract model and usage
            model = kwargs.get("model", "unknown")
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

            print(f"📊 Sending Lago events for customer: {customer_id}, prompt:{prompt_tokens}, completion:{completion_tokens}")

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
                input_event = self._create_event(customer_id, model, prompt_tokens, "input")
                response = await self.async_http_handler.post(
                    url=_url,
                    data=json.dumps(input_event),
                    headers=_headers,
                )
                response.raise_for_status()
                print(f"✅ Input event sent: {prompt_tokens} tokens")

            # Send output tokens event
            if completion_tokens > 0:
                output_event = self._create_event(customer_id, model, completion_tokens, "output")
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
