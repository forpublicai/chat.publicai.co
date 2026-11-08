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


def _install_passthrough_access_group_checks() -> None:
    """
    Hook LiteLLM's RouteChecks so auth=true pass-through endpoints:
    1. Are always enforced for non-admin virtual keys even when custom_auth is enabled in auto mode.
    2. Support `model_info.access_groups` / `access_groups` in pass-through endpoint YAML configs
       (matching `models/**/*.yaml`) in addition to `metadata.allowed_passthrough_routes`.
    """
    try:
        from litellm.proxy._types import LitellmUserRoles
        from litellm.proxy.auth.route_checks import RouteChecks
    except Exception as e:
        print(f"⚠️ Could not import RouteChecks for passthrough access groups: {e}")
        return

    if getattr(RouteChecks, "_publicai_passthrough_hooked", False):
        return

    _orig_check_passthrough = RouteChecks.check_passthrough_route_access
    _orig_should_call_route = RouteChecks.should_call_route

    def _get_endpoint_access_groups(route: str) -> list:
        try:
            from litellm.proxy.proxy_server import general_settings
        except Exception:
            return []

        endpoints = general_settings.get("pass_through_endpoints") or []
        for ep in endpoints:
            if not isinstance(ep, dict):
                continue
            ep_path = ep.get("path")
            if not isinstance(ep_path, str):
                continue
            normalized_ep = ep_path.rstrip("/") or "/"
            normalized_route = route.rstrip("/") or "/"
            matched = (
                normalized_route == normalized_ep
                or RouteChecks._route_matches_allowed_route(
                    route=route, allowed_route=normalized_ep
                )
            )
            if matched:
                groups = ep.get("access_groups")
                if not groups and isinstance(ep.get("model_info"), dict):
                    groups = ep["model_info"].get("access_groups")
                if isinstance(groups, list):
                    return [str(g) for g in groups]
        return []

    @staticmethod
    def _patched_check_passthrough_route_access(
        route: str, user_api_key_dict: UserAPIKeyAuth
    ) -> bool:
        # 1. Native LiteLLM check (metadata.allowed_passthrough_routes on key or team)
        if _orig_check_passthrough(route=route, user_api_key_dict=user_api_key_dict):
            return True

        # 2. Check access_groups / model_info.access_groups configured on the pass-through endpoint
        endpoint_groups = _get_endpoint_access_groups(route=route)
        if not endpoint_groups:
            return False

        key_models = list(getattr(user_api_key_dict, "models", None) or [])
        team_models = list(getattr(user_api_key_dict, "team_models", None) or [])
        has_team = getattr(user_api_key_dict, "team_id", None) is not None

        if "all-team-models" in key_models or (not key_models and has_team):
            effective_models = team_models
        else:
            effective_models = key_models

        if "all-proxy-models" in effective_models or "*" in effective_models:
            key_allowed = True
        else:
            key_allowed = bool(set(endpoint_groups) & set(effective_models))

        if not key_allowed:
            return False

        if has_team and team_models and effective_models is key_models:
            if "all-proxy-models" not in team_models and "*" not in team_models:
                if not (set(endpoint_groups) & set(team_models)):
                    return False

        return True

    @staticmethod
    def _patched_should_call_route(
        route: str,
        valid_token: UserAPIKeyAuth,
        request: Optional[Request] = None,
    ):
        result = _orig_should_call_route(
            route=route, valid_token=valid_token, request=request
        )
        if getattr(valid_token, "user_role", None) != LitellmUserRoles.PROXY_ADMIN:
            method = RouteChecks.get_request_method(request=request)
            if RouteChecks.is_auth_enforced_pass_through_route(
                route=route, method=method
            ):
                RouteChecks._require_auth_pass_through_access(
                    route=route,
                    valid_token=valid_token,
                    jwt_team_allowed_routes=RouteChecks._jwt_team_allowed_routes(
                        valid_token=valid_token
                    ),
                )
        return result

    RouteChecks.check_passthrough_route_access = _patched_check_passthrough_route_access
    RouteChecks.should_call_route = _patched_should_call_route
    RouteChecks._publicai_passthrough_hooked = True


_install_passthrough_access_group_checks()