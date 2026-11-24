import os
import sys
import types
import uuid as uuid_module
from pathlib import Path
from unittest.mock import MagicMock

LITELLM_GLUE_DIR = (
    Path(__file__).resolve().parent
    / "charts"
    / "platform"
    / "charts"
    / "litellm"
)
sys.path.insert(0, str(LITELLM_GLUE_DIR))

os.environ.setdefault("LITELLM_MASTER_KEY", "test-master-key")
os.environ.setdefault("LITELLM_BASE_URL", "http://litellm.test")
os.environ.setdefault("LAGO_API_KEY", "test-lago-key")
os.environ.setdefault("LAGO_API_BASE", "http://lago.test")
os.environ.setdefault("LAGO_API_EVENT_CODE", "public_ai_models")


def _install_fake_module(name, **attrs):
    if name in sys.modules:
        return sys.modules[name]
    mod = types.ModuleType(name)
    for key, value in attrs.items():
        setattr(mod, key, value)
    sys.modules[name] = mod
    return mod


# --- fastapi stub (only what custom_auth.py touches: Request as a type hint) ---
if "fastapi" not in sys.modules:
    fastapi_mod = _install_fake_module("fastapi")

    class Request:  # minimal stand-in, real prod code uses the real fastapi.Request
        def __init__(self, headers=None, url=""):
            self.headers = headers or {}
            self.url = url

    fastapi_mod.Request = Request

# --- httpx stub (tests patch httpx.AsyncClient per-case) ---
if "httpx" not in sys.modules:
    _install_fake_module("httpx", AsyncClient=MagicMock())

# --- litellm stub tree, just enough surface for custom_auth.py / custom_lago_callback.py ---
if "litellm" not in sys.modules:
    litellm_mod = _install_fake_module("litellm")

    class ModelResponse(dict):
        def __getattr__(self, item):
            try:
                return self[item]
            except KeyError:
                raise AttributeError(item)

    class EmbeddingResponse(dict):
        def __getattr__(self, item):
            try:
                return self[item]
            except KeyError:
                raise AttributeError(item)

    litellm_mod.ModelResponse = ModelResponse
    litellm_mod.EmbeddingResponse = EmbeddingResponse

    _install_fake_module("litellm._uuid", uuid=uuid_module)

    class _VerboseLogger:
        def debug(self, *args, **kwargs):
            pass

        def error(self, *args, **kwargs):
            pass

        def info(self, *args, **kwargs):
            pass

    _install_fake_module("litellm._logging", verbose_logger=_VerboseLogger())

    _install_fake_module("litellm.integrations")

    class CustomLogger:
        def __init__(self, *args, **kwargs):
            pass

    _install_fake_module(
        "litellm.integrations.custom_logger", CustomLogger=CustomLogger
    )

    _install_fake_module("litellm.llms")
    _install_fake_module("litellm.llms.custom_httpx")

    class HTTPHandler:
        def post(self, *args, **kwargs):
            raise NotImplementedError("stub - patch sync_http_handler in tests")

    class httpxSpecialProvider:
        LoggingCallback = "logging_callback"

    def get_async_httpx_client(*args, **kwargs):
        return MagicMock()

    _install_fake_module(
        "litellm.llms.custom_httpx.http_handler",
        HTTPHandler=HTTPHandler,
        get_async_httpx_client=get_async_httpx_client,
        httpxSpecialProvider=httpxSpecialProvider,
    )

    _install_fake_module("litellm.proxy")

    class UserAPIKeyAuth:
        pass

    _install_fake_module("litellm.proxy._types", UserAPIKeyAuth=UserAPIKeyAuth)
