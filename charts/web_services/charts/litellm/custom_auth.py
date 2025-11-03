"""
Custom auth function to assign budgets to OpenWebUI end-users.
Works in 'auto' mode - handles OpenWebUI users, falls back to normal auth for others.
"""
import json
import os
import httpx
from typing import Union

from fastapi import Request

from litellm.proxy._types import UserAPIKeyAuth

# Get master key from environment
MASTER_KEY = os.environ.get("LITELLM_MASTER_KEY", "")
LITELLM_BASE_URL = os.environ.get("LITELLM_BASE_URL", "http://localhost:4000")

async def ensure_end_user_with_budget(user_id: str, user_email: str = "") -> bool:
    """Check if customer exists, create with budget if they don't"""
    try:
        async with httpx.AsyncClient() as client:
            # First check if customer already exists
            info_response = await client.get(
                f"{LITELLM_BASE_URL}/customer/info",
                headers={
                    "Authorization": f"Bearer {MASTER_KEY}",
                },
                params={"end_user_id": user_id}
            )
            
            if info_response.status_code == 200:
                print(f"ℹ️ Customer {user_id} already exists")
                return True
            elif info_response.status_code == 400:
                print(f"📝 Customer {user_id} doesn't exist, creating with budget...")
                # Customer doesn't exist, create them with budget
                create_response = await client.post(
                    f"{LITELLM_BASE_URL}/customer/new",
                    headers={
                        "Authorization": f"Bearer {MASTER_KEY}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "user_id": user_id,
                        "budget_id": "public_ai_free"
                    }
                )
                
                if create_response.status_code in [200, 201]:
                    print(f"✅ Created customer with budget: {user_id}")
                    return True
                else:
                    print(f"⚠️ Failed to create customer {user_id}: {create_response.status_code} - {create_response.text}")
                    return False
            else:
                print(f"⚠️ Error checking customer {user_id}: {info_response.status_code} - {info_response.text}")
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
        request_path = str(request.url.path) if hasattr(request.url, 'path') else str(request.url)
        if "completions" not in request_path:
            # Not a completion request, skip custom auth
            return api_key

        # Extract user info using .lower() for reliable header parsing
        headers_lower = {k.lower(): v for k, v in request.headers.items()}

        # Check for OpenWebUI headers
        openwebui_user_id = headers_lower.get('x-openwebui-user-id')
        openwebui_user_email = headers_lower.get('x-openwebui-user-email', '')
        user_name = headers_lower.get('x-openwebui-user-name', '')
        user_role = headers_lower.get('x-openwebui-user-role', '')

        # Check for Zuplo headers
        zuplo_user_id = headers_lower.get('x-zuplo-user-id')
        zuplo_user_email = headers_lower.get('x-zuplo-user-email', '')

        # Determine user_id, source, and email (prioritize source-specific email)
        if openwebui_user_id:
            user_id = openwebui_user_id
            user_email = openwebui_user_email
            source = "OpenWebUI"
        elif zuplo_user_id:
            user_id = zuplo_user_id
            user_email = zuplo_user_email
            source = "Zuplo"
        else:
            user_id = None
            user_email = ''
            source = None

        print(f"🔑 CUSTOM AUTH - Source: {source}, user_id={user_id}")

        if user_id:
            # This is an OpenWebUI or Zuplo request - ensure user has budget
            print(f"📋 {source} request detected, ensuring customer {user_id} has budget...")
            await ensure_end_user_with_budget(user_id, user_email)

            # Return the API key to let LiteLLM handle normal auth
            # But now the end-user will have rate limits applied
            print(f"✅ Returning API key for LiteLLM auth with end-user: {user_id}")
            return api_key
        else:
            # No OpenWebUI or Zuplo headers - let LiteLLM handle normal auth
            print("ℹ️ No OpenWebUI or Zuplo headers, returning API key for normal auth")
            return api_key

    except Exception as e:
        print(f"❌ Custom auth error: {str(e)}")
        # On any error, fall back to normal auth
        return api_key
    

# Budget Limiting by spend