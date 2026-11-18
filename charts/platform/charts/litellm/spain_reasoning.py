import re

from litellm.integrations.custom_logger import CustomLogger

SPAIN_MODEL = "BSC-LT/ALIA-40b-instruct"
MAX_PREFIX_CHARS = 8192
MAX_PREFIX_CHUNKS = 2048
MARKER = re.compile(r"</think>|<think|`")
NON_TEXT_FIELDS = (
    "reasoning_content",
    "reasoning",
    "thinking",
    "tool_calls",
    "function_call",
)


def _text_delta(chunk):
    choices = getattr(chunk, "choices", None)
    if choices and len(choices) == 1 and getattr(choices[0], "index", None) == 0:
        delta = getattr(choices[0], "delta", None)
        if delta is not None and not any(
            getattr(delta, key, None) for key in NON_TEXT_FIELDS
        ):
            return delta
    return None


class SpainReasoningCallback(CustomLogger):
    async def async_post_call_streaming_iterator_hook(
        self, user_api_key_dict, response, request_data
    ):
        pending = []
        prefix = ""
        single_choice = request_data.get("n") in (None, 1)
        if single_choice and request_data.get("model") == SPAIN_MODEL:
            async for chunk in response:
                delta = _text_delta(chunk)
                content = getattr(delta, "content", None)
                if delta is not None and not pending and not content:
                    yield chunk
                    continue
                pending.append(chunk)
                if not isinstance(content, str) or not content:
                    break
                prefix += content
                marker = MARKER.search(prefix, 0, MAX_PREFIX_CHARS)
                if marker:
                    # A paired opening tag or Markdown code before the close needs no repair.
                    if marker.group() == "</think>":
                        first = pending[0].choices[0].delta
                        first.content = "<think>" + first.content
                    break
                if len(prefix) >= MAX_PREFIX_CHARS or len(pending) >= MAX_PREFIX_CHUNKS:
                    break

        for chunk in pending:
            yield chunk
        pending.clear()
        async for chunk in response:
            yield chunk


spain_reasoning_callback = SpainReasoningCallback()
