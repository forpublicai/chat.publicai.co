"""
Custom LiteLLM callback that replaces raw budget errors with a message end users can understand.

Budget errors come from two places:
1. LiteLLM's own budget checks (end user, key, team), raised as litellm.BudgetExceededError.
2. Upstream providers that run their own LiteLLM proxy, which come back wrapped as e.g.
   "litellm.BadRequestError: OpenAIException - Budget has been exceeded! Team=..."

Shown as is, they read as if Public AI ran out of OpenAI credits and expose internal ids and
spend figures. The original exception is still logged and alerted on by LiteLLM before this
hook runs. See https://docs.litellm.ai/docs/proxy/call_hooks (Transform Error Responses).
"""
from typing import Optional

import litellm
from fastapi import HTTPException
from litellm.integrations.custom_logger import CustomLogger
from litellm.proxy._types import UserAPIKeyAuth

BUDGET_EXCEEDED_MARKERS = ("Budget has been exceeded", "ExceededBudget")

BUDGET_EXCEEDED_MESSAGE = (
    "Public AI is a best-effort service, and high interest from visitors right now "
    "has exceeded our capacity to serve you. Please try again in a few minutes."
)


def is_budget_exceeded_error(exception: Exception) -> bool:
    if isinstance(exception, litellm.BudgetExceededError):
        return True
    message = str(getattr(exception, "message", None) or exception)
    return any(marker in message for marker in BUDGET_EXCEEDED_MARKERS)


class ErrorMessageCallback(CustomLogger):
    async def async_post_call_failure_hook(
        self,
        request_data: dict,
        original_exception: Exception,
        user_api_key_dict: UserAPIKeyAuth,
        traceback_str: Optional[str] = None,
    ) -> Optional[HTTPException]:
        if not is_budget_exceeded_error(original_exception):
            return None
        return HTTPException(
            status_code=getattr(original_exception, "status_code", 429),
            detail=BUDGET_EXCEEDED_MESSAGE,
        )


error_message_callback = ErrorMessageCallback()
