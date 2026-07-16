#!/usr/bin/env python3
import os
import re
import ssl
import sys
import time
import json
import urllib.request
import urllib.error

def load_env(env_path):
    """Load environment variables from a .env file."""
    if not os.path.exists(env_path):
        print(f"Warning: .env file not found at {env_path}")
        return
    with open(env_path, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if '=' in line:
                key, val = line.split('=', 1)
                key = key.strip()
                val = val.strip().strip('"').strip("'")
                os.environ[key] = val

def parse_active_endpoints(values_path):
    """Parse active LLM endpoints from the litellm values.yaml file."""
    if not os.path.exists(values_path):
        print(f"Error: values.yaml file not found at {values_path}")
        sys.exit(1)
        
    models = []
    current_model = None
    in_params = False
    
    with open(values_path, 'r') as f:
        for line in f:
            stripped = line.strip()
            # If line is empty or is a comment, skip it
            if not stripped or stripped.startswith('#'):
                continue
            
            # Check if this line starts a model configuration block
            model_match = re.match(r'^-\s+model_name:\s*(.+)$', stripped)
            if model_match:
                # If we were building a model block, save it if it has an api_base
                if current_model and 'api_base' in current_model.get('litellm_params', {}):
                    models.append(current_model)
                
                current_model = {
                    'model_name': model_match.group(1).strip().strip('"').strip("'"),
                    'litellm_params': {}
                }
                in_params = False
                continue
            
            if current_model is not None:
                # Check if we are entering litellm_params
                if stripped.startswith('litellm_params:'):
                    in_params = True
                    continue
                
                if in_params:
                    # Check indentation to see if we left litellm_params
                    # All parameters inside litellm_params are indented with 8+ spaces
                    leading_spaces = len(line) - len(line.lstrip(' '))
                    if leading_spaces < 8:
                        in_params = False
                        continue
                    
                    # Parse parameter key-value pairs
                    param_match = re.match(r'^([a-zA-Z0-9_]+):\s*([^#]+)', stripped)
                    if param_match:
                        key = param_match.group(1)
                        val = param_match.group(2).strip().strip('"').strip("'")
                        current_model['litellm_params'][key] = val
                        
    # Append the last model if it qualifies
    if current_model and 'api_base' in current_model.get('litellm_params', {}):
        models.append(current_model)
        
    return models

def resolve_api_key(api_key_str):
    """Resolve API key which may refer to an environment variable."""
    if not api_key_str:
        return ""
    if api_key_str.startswith("os.environ/"):
        env_var = api_key_str.split("/", 1)[1]
        return os.environ.get(env_var, "")
    return api_key_str

def measure_ttft(model_name, litellm_model, api_base, api_key_str, ssl_verify=True):
    """Call the LLM endpoint and measure Time to First Token (TTFT) with a 30s timeout."""
    api_key = resolve_api_key(api_key_str)
    
    # Strip OpenAI provider prefix if present
    backend_model = litellm_model
    if backend_model.startswith("openai/"):
        backend_model = backend_model[len("openai/"):]
        
    url = api_base.rstrip('/') + '/chat/completions'
    
    payload = {
        "model": backend_model,
        "messages": [
            {"role": "user", "content": "Respond with a single word hello"}
        ],
        "stream": True,
        "max_tokens": 10
    }
    
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
        
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode('utf-8'),
        headers=headers,
        method='POST'
    )
    
    # SSL context creation
    if not ssl_verify:
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
    else:
        context = None
        
    t0 = time.time()
    try:
        # Establish connection and send request with 30s timeout
        with urllib.request.urlopen(req, context=context, timeout=30) as response:
            # Read streaming response line by line to get the first token
            while True:
                line = response.readline()
                if not line:
                    break
                line_str = line.decode('utf-8').strip()
                if line_str.startswith('data:'):
                    data_str = line_str[5:].strip()
                    if data_str == '[DONE]':
                        break
                    try:
                        data = json.loads(data_str)
                        choices = data.get('choices', [])
                        if choices:
                            delta = choices[0].get('delta', {})
                            # Check for any generated content/token
                            if delta.get('content') or delta.get('reasoning_content') or delta.get('text') or delta:
                                ttft = time.time() - t0
                                return True, ttft, None
                    except json.JSONDecodeError:
                        pass
                        
            return False, None, "Response finished without returning any tokens"
            
    except urllib.error.HTTPError as e:
        # Try to read the error body for more details
        try:
            error_body = e.read().decode('utf-8')
            return False, None, f"HTTP Error {e.code}: {e.reason} - Details: {error_body}"
        except Exception:
            return False, None, f"HTTP Error {e.code}: {e.reason}"
    except urllib.error.URLError as e:
        return False, None, f"URL Error: {e.reason}"
    except Exception as e:
        return False, None, f"Exception: {type(e).__name__} - {str(e)}"

def main():
    # Determine directory paths relative to the script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Locate project root containing .env
    root_dir = script_dir
    while root_dir != os.path.dirname(root_dir):
        if os.path.exists(os.path.join(root_dir, '.env')):
            break
        root_dir = os.path.dirname(root_dir)
        
    env_path = os.path.join(root_dir, '.env')
    values_path = os.path.join(root_dir, 'charts/web_services/charts/litellm/values.yaml')
    
    print(f"Loading environment from: {env_path}")
    load_env(env_path)
    
    print(f"Parsing active endpoints from: {values_path}")
    active_endpoints = parse_active_endpoints(values_path)
    
    if not active_endpoints:
        print("No active HTTP endpoints found in values.yaml.")
        return
        
    print(f"Found {len(active_endpoints)} active HTTP endpoints. Starting tests...")
    print("-" * 120)
    
    results = []
    for idx, ep in enumerate(active_endpoints, 1):
        model_name = ep['model_name']
        litellm_model = ep['litellm_params'].get('model', '')
        api_base = ep['litellm_params'].get('api_base', '')
        api_key_str = ep['litellm_params'].get('api_key', '')
        
        ssl_verify_str = ep['litellm_params'].get('ssl_verify', 'true').strip().lower()
        ssl_verify = ssl_verify_str != 'false'
        
        print(f"[{idx}/{len(active_endpoints)}] Testing model: {model_name} at {api_base} ...")
        success, ttft, error = measure_ttft(model_name, litellm_model, api_base, api_key_str, ssl_verify)
        
        results.append({
            'model_name': model_name,
            'api_base': api_base,
            'success': success,
            'ttft': ttft,
            'error': error
        })
        
    print("\n" + "=" * 120)
    print(f"{'Model Name':<45} | {'Status':<12} | {'TTFT (s)':<10} | {'Endpoint URL':<50}")
    print("-" * 120)
    
    for res in results:
        status_str = "SUCCESS" if res['success'] else "FAILED"
        ttft_str = f"{res['ttft']:.3f}s" if res['success'] else "N/A"
        print(f"{res['model_name']:<45} | {status_str:<12} | {ttft_str:<10} | {res['api_base']:<50}")
        
    print("=" * 120)
    
    failures = [r for r in results if not r['success']]
    if failures:
        print("\n" + "!" * 120)
        print("FAILURE DETAILS:")
        print("-" * 120)
        for idx, f in enumerate(failures, 1):
            print(f"{idx}. Model: {f['model_name']}")
            print(f"   URL: {f['api_base']}")
            print(f"   Error: {f['error']}")
            print("-" * 120)

if __name__ == "__main__":
    main()
