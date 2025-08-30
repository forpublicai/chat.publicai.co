"""
Custom auth function to log user info headers and forward requests.
"""
import logging
from typing import Union

from fastapi import Request

from litellm.proxy._types import UserAPIKeyAuth

# Set up logging
logger = logging.getLogger(__name__)

async def user_api_key_auth(
    request: Request, api_key: str
) -> Union[UserAPIKeyAuth, str]:
    try:
        # Log all OpenWebUI user-related headers
        user_headers = {}
        for header_name, header_value in request.headers.items():
            if header_name.lower().startswith('x-openwebui-user') or header_name.lower().startswith('x-openwebui-chat'):
                user_headers[header_name] = header_value
        
        print(f"🔑 CUSTOM AUTH CALLED - API Key: {api_key[:10]}..., User Headers: {user_headers}")
        logger.info(f"🔑 CUSTOM AUTH CALLED - API Key: {api_key[:10]}..., User Headers: {user_headers}")
        
        # Forward the original API key (no modification)
        return api_key
        
    except Exception as e:
        logger.error(f"Error in custom auth: {str(e)}")
        return api_key
