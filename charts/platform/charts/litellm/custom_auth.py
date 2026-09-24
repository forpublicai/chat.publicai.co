"""
Custom auth function to assign budgets to OpenWebUI end-users.
Works in 'auto' mode - handles OpenWebUI users, falls back to normal auth for others.
Optimized with persistent HTTP connection pooling and in-memory TTL user caching.
"""
import os
import time
from typing import Dict, Optional, Union
import httpx
from fastapi import Request

from litellm.proxy._types import UserAPIKeyAuth

# Get master key from environment
MASTER_KEY = os.environ.get("LITELLM_MASTER_KEY", "")
LITELLM_BASE_URL = os.environ.get("LITELLM_BASE_URL", "http://localhost:4000")

# In-memory TTL cache for verified end-users: user_id -> expiry_timestamp
_USER_CACHE: Dict[str, float] = {}
_CACHE_TTL_SECONDS = 3600  # 1 hour TTL
_CACHE_MAX_ENTRIES = 10000

# Shared persistent async HTTP client
_http_client: Optional[httpx.AsyncClient] = None


def _get_http_client() -> httpx.AsyncClient:
    """Returns a shared, pooled AsyncClient instance."""
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(
            limits=httpx.Limits(max_keepalive_connections=20, max_connections=50),
            timeout=httpx.Timeout(5.0, connect=2.0),
        )
    return _http_client


def _is_user_cached(user_id: str) -> bool:
    """Check if user budget is already verified in cache and not expired."""
    now = time.monotonic()
    expiry = _USER_CACHE.get(user_id)
    if expiry is not None:
        if now < expiry:
            return True
        # Expired
        _USER_CACHE.pop(user_id, None)
    return False


def _cache_user(user_id: str):
    """Cache verified user with TTL and enforce max cache size."""
    now = time.monotonic()
    if len(_USER_CACHE) >= _CACHE_MAX_ENTRIES:
        # Prune expired entries
        expired = [uid for uid, exp in _USER_CACHE.items() if exp <= now]
        for uid in expired:
            _USER_CACHE.pop(uid, None)
        # If still over limit, drop oldest entries
        if len(_USER_CACHE) >= _CACHE_MAX_ENTRIES:
            oldest_keys = list(_USER_CACHE.keys())[:1000]
            for uid in oldest_keys:
                _USER_CACHE.pop(uid, None)
    _USER_CACHE[user_id] = now + _CACHE_TTL_SECONDS


async def ensure_end_user_with_budget(user_id: str, user_email: str = "") -> bool:
    """Check if customer exists, create with budget if they don't (cached)."""
    if _is_user_cached(user_id):
        return True

    try:
        client = _get_http_client()
        # First check if customer already exists
        info_response = await client.get(
            f"{LITELLM_BASE_URL}/customer/info",
            headers={
                "Authorization": f"Bearer {MASTER_KEY}",
            },
            params={"end_user_id": user_id},
        )

        if info_response.status_code == 200:
            _cache_user(user_id)
            return True
        elif info_response.status_code == 400:
            print(f"📝 Customer {user_id} doesn't exist, creating with budget...")
            # Customer doesn't exist, create them with budget
            create_response = await client.post(
                f"{LITELLM_BASE_URL}/customer/new",
                headers={
                    "Authorization": f"Bearer {MASTER_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "user_id": user_id,
                    "budget_id": "public_ai_free",
                },
            )

            if create_response.status_code in [200, 201]:
                print(f"✅ Created customer with budget: {user_id}")
                _cache_user(user_id)
                return True
            else:
                print(
                    f"⚠️ Failed to create customer {user_id}: {create_response.status_code} - {create_response.text}"
                )
                return False
        else:
            print(
                f"⚠️ Error checking customer {user_id}: {info_response.status_code} - {info_response.text}"
            )
            return False

    except Exception as e:
        print(f"❌ Error ensuring customer exists: {str(e)}")
        return False


async def user_api_key_auth(
    request: Request, api_key: str
) -> Union[UserAPIKeyAuth, str]:
    """
    Custom auth in 'auto' mode:
    - If OpenWebUI headers present: create customer with budget, return api_key for fallback auth
    - If Zuplo headers present: create customer with budget, return api_key for fallback auth
    - If no headers: return api_key for normal LiteLLM auth
    """
    try:
        # Only apply custom auth logic for completion requests
        request_path = (
            str(request.url.path) if hasattr(request.url, "path") else str(request.url)
        )
        if "completions" not in request_path:
            # Not a completion request, skip custom auth
            return api_key

        # Extract user info using .lower() for reliable header parsing
        headers_lower = {k.lower(): v for k, v in request.headers.items()}

        # Check for OpenWebUI headers
        openwebui_user_id = headers_lower.get("x-openwebui-user-id")
        openwebui_user_email = headers_lower.get("x-openwebui-user-email", "")

        # Check for Zuplo headers
        zuplo_user_id = headers_lower.get("x-zuplo-user-id")
        zuplo_user_email = headers_lower.get("x-zuplo-user-email", "")

        # Determine user_id and email
        if openwebui_user_id:
            user_id = openwebui_user_id
            user_email = openwebui_user_email
        elif zuplo_user_id:
            user_id = zuplo_user_id
            user_email = zuplo_user_email
        else:
            user_id = None
            user_email = ""

        if user_id:
            # This is an OpenWebUI or Zuplo request - ensure user has budget (cached)
            await ensure_end_user_with_budget(user_id, user_email)
            return api_key
        else:
            # No OpenWebUI or Zuplo headers - let LiteLLM handle normal auth
            return api_key

    except Exception as e:
        print(f"❌ Custom auth error: {str(e)}")
        # On any error, fall back to normal auth
        return api_key