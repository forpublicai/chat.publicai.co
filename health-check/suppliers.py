#!/usr/bin/env python3
import os
import re
import ssl
import sys
import time
import json
import argparse
import urllib.request
import urllib.error

def load_env(env_path, verbose=True):
    """Load environment variables from a .env file."""
    if not os.path.exists(env_path):
        if verbose:
            print(f"Warning: .env file not found at {env_path}", file=sys.stderr)
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

def parse_active_endpoints(models_dir, verbose=True):
    """Parse active LLM endpoints from the litellm models directory."""
    import yaml
    if not os.path.exists(models_dir):
        raise FileNotFoundError(f"models directory not found at {models_dir}")
        
    models = []
    
    for root_dir, _, files in sorted(os.walk(models_dir)):
        for file in sorted(files):
            if file.endswith('.yaml') or file.endswith('.yml'):
                file_path = os.path.join(root_dir, file)
                try:
                    with open(file_path, 'r') as f:
                        data = yaml.safe_load(f)
                    if not data or 'models' not in data:
                        continue
                    for m in data['models']:
                        model_name = m.get('model_name')
                        if not model_name:
                            continue
                        litellm_params = m.get('litellm_params', {})
                        # Only test endpoints that have api_base
                        if 'api_base' in litellm_params:
                            models.append({
                                'model_name': model_name,
                                'litellm_params': litellm_params
                            })
                except Exception as e:
                    if verbose:
                        print(f"Error parsing model file {file_path}: {e}", file=sys.stderr)
                    
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
    parser = argparse.ArgumentParser(description="Test Provider endpoints")
    parser.add_argument("-json", "--json", action="store_true", help="Output results in JSON format")
    args = parser.parse_args()
    
    json_mode = args.json
    
    def log(msg, *args_msg, **kwargs):
        if not json_mode:
            print(msg, *args_msg, **kwargs)

    try:
        # Determine directory paths relative to the script
        script_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Locate project root containing .env
        root_dir = script_dir
        while root_dir != os.path.dirname(root_dir):
            if os.path.exists(os.path.join(root_dir, '.env')):
                break
            root_dir = os.path.dirname(root_dir)
            
        env_path = os.path.join(root_dir, '.env')
        models_dir = os.path.join(root_dir, 'charts/web_services/charts/litellm/models')
        
        log(f"Loading environment from: {env_path}")
        load_env(env_path, verbose=not json_mode)
        
        log(f"Parsing active endpoints from: {models_dir}")
        active_endpoints = parse_active_endpoints(models_dir, verbose=not json_mode)
        
        if not active_endpoints:
            raise RuntimeError("No active HTTP endpoints found in models directory.")
            
        log(f"Found {len(active_endpoints)} active HTTP endpoints. Starting tests...")
        log("-" * 120)
        
        results = []
        for idx, ep in enumerate(active_endpoints, 1):
            model_name = ep['model_name']
            litellm_model = ep['litellm_params'].get('model', '')
            api_base = ep['litellm_params'].get('api_base', '')
            api_key_str = ep['litellm_params'].get('api_key', '')
            
            ssl_verify_val = ep['litellm_params'].get('ssl_verify', True)
            if isinstance(ssl_verify_val, str):
                ssl_verify = ssl_verify_val.strip().lower() != 'false'
            else:
                ssl_verify = bool(ssl_verify_val)
            
            log(f"[{idx}/{len(active_endpoints)}] Testing model: {model_name} at {api_base} ...")
            success, ttft, error = measure_ttft(model_name, litellm_model, api_base, api_key_str, ssl_verify)
            
            results.append({
                'model': model_name,
                'model_name': model_name,
                'api_base': api_base,
                'success': success,
                'ttft': ttft,
                'error': error
            })
            
        failures = [r for r in results if not r['success']]
        
        if json_mode:
            if failures:
                err_msgs = [f"{f['model_name']}: {f['error']}" for f in failures]
                err_obj = {
                    "message": f"{len(failures)} model(s) failed testing: {', '.join(err_msgs)}",
                    "code": "MODEL_TESTS_FAILED"
                }
                output = {
                    "success": False,
                    "error": err_obj,
                    "results": results
                }
            else:
                output = {
                    "success": True,
                    "error": None,
                    "results": results
                }
            print(json.dumps(output, indent=2))
            if failures:
                sys.exit(1)
            else:
                sys.exit(0)
                
        log("\n" + "=" * 120)
        log(f"{'Model Name':<45} | {'Status':<12} | {'TTFT (s)':<10} | {'Endpoint URL':<50}")
        log("-" * 120)
        
        for res in results:
            status_str = "SUCCESS" if res['success'] else "FAILED"
            ttft_str = f"{res['ttft']:.3f}s" if res['success'] else "N/A"
            log(f"{res['model_name']:<45} | {status_str:<12} | {ttft_str:<10} | {res['api_base']:<50}")
            
        log("=" * 120)
        
        if failures:
            log("\n" + "!" * 120)
            log("FAILURE DETAILS:")
            log("-" * 120)
            for idx, f in enumerate(failures, 1):
                log(f"{idx}. Model: {f['model_name']}")
                log(f"   URL: {f['api_base']}")
                log(f"   Error: {f['error']}")
                log("-" * 120)
            sys.exit(1)
        else:
            sys.exit(0)

    except Exception as e:
        if json_mode:
            code = "UNKNOWN_ERROR"
            msg = str(e)
            if "models directory not found" in msg:
                code = "MODELS_DIR_NOT_FOUND"
            elif "No active HTTP endpoints" in msg:
                code = "NO_ENDPOINTS_FOUND"
                
            err_obj = {
                "message": msg,
                "code": code
            }
            output = {
                "success": False,
                "error": err_obj,
                "results": []
            }
            print(json.dumps(output, indent=2))
            sys.exit(1)
        else:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)

if __name__ == "__main__":
    main()
