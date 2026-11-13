"""
Custom LiteLLM callback that replaces upstream budget errors with a 503 capacity message.

Upstream providers running their own LiteLLM proxy can return budget errors wrapped as e.g.:
  "litellm.BadRequestError: OpenAIException - Budget has been exceeded! Team=..."

Shown as is, they read as a 400 client error and expose internal IDs and spend figures.
This hook rewrites them to 503 Service Unavailable with a user-facing capacity message and
lets all other errors pass through unchanged. LiteLLM still logs and alerts on the original
exception before this hook runs. See https://docs.litellm.ai/docs/proxy/call_hooks.
"""
from typing import Optional

from fastapi import HTTPException
from litellm.integrations.custom_logger import CustomLogger
from litellm.proxy._types import UserAPIKeyAuth

UPSTREAM_BUDGET_EXCEEDED_MARKERS = ("Budget has been exceeded", "ExceededBudget")

UPSTREAM_CAPACITY_MESSAGE = (
    "Public AI is temporarily at capacity and cannot serve this model right now. "
    "Please try again in a few minutes."
)


def _exception_text(exception: Exception) -> str:
    """Collect the exception string and optional `.message` attribute for inspection."""
    parts = [str(exception)]
    message = getattr(exception, "message", None)
    if message:
        parts.append(str(message))
    return " ".join(parts)


def is_upstream_budget_error(exception: Exception) -> bool:
    """Return True if the exception text matches an upstream budget-exceeded marker."""
    text = _exception_text(exception)
    return any(marker in text for marker in UPSTREAM_BUDGET_EXCEEDED_MARKERS)


class ErrorMessageCallback(CustomLogger):
    async def async_post_call_failure_hook(
        self,
        request_data: dict,
        original_exception: Exception,
        user_api_key_dict: UserAPIKeyAuth,
        traceback_str: Optional[str] = None,
    ) -> Optional[HTTPException]:
        if is_upstream_budget_error(original_exception):
            return HTTPException(status_code=503, detail=UPSTREAM_CAPACITY_MESSAGE)
        return None


error_message_callback = ErrorMessageCallback()
