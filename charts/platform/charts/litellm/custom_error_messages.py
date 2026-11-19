"""
Custom LiteLLM callback that replaces upstream budget errors with a 503 capacity message.

Upstream providers running their own LiteLLM proxy can return budget errors wrapped as e.g.:
  "litellm.BadRequestError: OpenAIException - Budget has been exceeded! Team=..."

Shown as is, they read as a 400 client error and expose internal IDs and spend figures.
This hook rewrites upstream budget errors to 503 Service Unavailable with an OpenAI-formatted
user-facing capacity message, while leaving local proxy budget errors (e.g. end-user
`public_ai_free` limits) and all other errors unchanged. LiteLLM still logs and alerts on
the original exception before this hook runs. See https://docs.litellm.ai/docs/proxy/call_hooks.
"""
from typing import Optional

import litellm
from fastapi import HTTPException
from litellm._logging import verbose_logger
from litellm.integrations.custom_logger import CustomLogger
from litellm.proxy._types import UserAPIKeyAuth

UPSTREAM_BUDGET_EXCEEDED_MARKERS = ("Budget has been exceeded", "ExceededBudget")
UPSTREAM_EXCEPTION_MARKERS = ("OpenAIException", "litellm.BadRequestError")

UPSTREAM_CAPACITY_MESSAGE = (
    "Public AI is temporarily at capacity and cannot serve this model right now. "
    "Please try again in a few minutes."
)


def _exception_types(*names: str) -> tuple:
    types = []
    for name in names:
        exc_type = getattr(litellm, name, None)
        if isinstance(exc_type, type):
            types.append(exc_type)
    return tuple(types)


def _exception_text(exception: Exception) -> str:
    """Collect the exception string and optional `.message` attribute for inspection."""
    parts = [str(exception)]
    message = getattr(exception, "message", None)
    if message:
        parts.append(str(message))
    return " ".join(parts)


def _is_local_budget_error(exception: Exception) -> bool:
    """Return True if the exception came from this proxy's own budget enforcement."""
    local_budget_types = _exception_types("BudgetExceededError")
    if local_budget_types and isinstance(exception, local_budget_types):
        return True
    if type(exception).__name__ == "BudgetExceededError":
        return True
    if getattr(exception, "type", None) == "budget_exceeded":
        return True
    return False


def _is_upstream_exception(exception: Exception, text: str) -> bool:
    """Return True if the exception originated from an upstream provider call."""
    upstream_types = _exception_types("BadRequestError", "RateLimitError", "APIError")
    if upstream_types and isinstance(exception, upstream_types):
        return True
    if getattr(exception, "llm_provider", None):
        return True
    return any(marker in text for marker in UPSTREAM_EXCEPTION_MARKERS)


def is_upstream_budget_error(exception: Exception) -> bool:
    """Return True if the exception is an upstream provider budget-exceeded error."""
    if _is_local_budget_error(exception):
        return False
    text = _exception_text(exception)
    if not _is_upstream_exception(exception, text):
        return False
    return any(marker in text for marker in UPSTREAM_BUDGET_EXCEEDED_MARKERS)


class ErrorMessageCallback(CustomLogger):
    async def async_post_call_failure_hook(
        self,
        request_data: dict,
        original_exception: Exception,
        user_api_key_dict: UserAPIKeyAuth,
        traceback_str: Optional[str] = None,
        **kwargs,
    ) -> Optional[HTTPException]:
        try:
            if is_upstream_budget_error(original_exception):
                return HTTPException(
                    status_code=503,
                    detail={
                        "error": {
                            "message": UPSTREAM_CAPACITY_MESSAGE,
                            "type": "service_unavailable",
                            "code": "503",
                        }
                    },
                )
        except Exception as e:
            verbose_logger.error(f"Error in ErrorMessageCallback failure hook: {e}")
        return None


error_message_callback = ErrorMessageCallback()
