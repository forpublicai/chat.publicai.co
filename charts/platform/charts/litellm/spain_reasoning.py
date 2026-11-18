from litellm.integrations.custom_logger import CustomLogger

SPAIN_MODEL = "BSC-LT/ALIA-40b-instruct"
OPEN_TAG = "<think>"
CLOSE_TAG = "</think>"
MAX_PREFIX_CHARS = 8192
MAX_PREFIX_CHUNKS = 2048


class SpainReasoningCallback(CustomLogger):
    async def async_post_call_streaming_iterator_hook(
        self, user_api_key_dict, response, request_data
    ):
        if request_data.get("model") != SPAIN_MODEL or request_data.get("n", 1) not in (
            None,
            1,
        ):
            async for chunk in response:
                yield chunk
            return

        # Spain sometimes emits its initial reasoning with only a closing tag.
        # Hold the prefix so it never reaches the UI as ordinary answer text.
        pending = []
        prefix = ""
        async for chunk in response:
            choices = getattr(chunk, "choices", None) or []
            choice = choices[0] if len(choices) == 1 else None
            delta = (
                getattr(choice, "delta", None)
                if getattr(choice, "index", None) == 0
                else None
            )
            content = getattr(delta, "content", None)
            structured = any(
                getattr(delta, field, None)
                for field in (
                    "reasoning_content",
                    "reasoning",
                    "thinking",
                    "tool_calls",
                    "function_call",
                )
            )
            if not pending and not content and delta is not None and not structured:
                yield chunk
                continue
            if not isinstance(content, str) or not content or structured:
                break

            pending.append(chunk)
            prefix += content
            end = prefix.find(CLOSE_TAG)
            # Leave paired tags and Markdown code literals to the existing parser.
            if end != -1 and end + len(CLOSE_TAG) <= MAX_PREFIX_CHARS:
                if "<think" not in prefix[:end] and "`" not in prefix[:end]:
                    first = pending[0].choices[0].delta
                    first.content = OPEN_TAG + first.content
                chunk = None
                break
            if (
                "<think" in prefix
                or "`" in prefix
                or len(prefix) >= MAX_PREFIX_CHARS
                or len(pending) >= MAX_PREFIX_CHUNKS
            ):
                chunk = None
                break
        else:
            chunk = None

        for buffered_chunk in pending:
            yield buffered_chunk
        if chunk is not None:
            yield chunk
        async for chunk in response:
            yield chunk


spain_reasoning_callback = SpainReasoningCallback()
