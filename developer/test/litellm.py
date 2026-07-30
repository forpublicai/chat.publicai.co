#!/usr/bin/env python3
import os
import ssl
import sys
import time
import json
import argparse
import urllib.request
import urllib.error
import concurrent.futures

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

def list_models(base_url, api_key, ssl_verify=True):
    """Fetch the list of models from LiteLLM."""
    url = f"{base_url.rstrip('/')}/v1/models"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "User-Agent": "Mozilla/5.0"
    }
    
    req = urllib.request.Request(url, headers=headers, method='GET')
    
    if not ssl_verify:
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
    else:
        context = None
        
    try:
        with urllib.request.urlopen(req, context=context, timeout=15) as response:
            res_data = json.loads(response.read().decode('utf-8'))
            models = []
            if isinstance(res_data, dict) and 'data' in res_data:
                for item in res_data['data']:
                    if isinstance(item, dict) and 'id' in item:
                        models.append(item['id'])
            return models, None
    except urllib.error.HTTPError as e:
        try:
            error_body = e.read().decode('utf-8')
            return None, f"HTTP Error {e.code}: {e.reason} - Details: {error_body}"
        except Exception:
            return None, f"HTTP Error {e.code}: {e.reason}"
    except urllib.error.URLError as e:
        return None, f"URL Error: {e.reason}"
    except Exception as e:
        return None, f"Exception: {type(e).__name__} - {str(e)}"

def measure_ttft(base_url, model_name, api_key, ssl_verify=True):
    """Call a model (chat completion, embedding, or rerank) and measure latency/TTFT."""
    model_lower = model_name.lower()
    
    if "embed" in model_lower:
        url = f"{base_url.rstrip('/')}/v1/embeddings"
        payload = {
            "model": model_name,
            "input": ["hello"]
        }
        is_streaming = False
    elif "rerank" in model_lower:
        url = f"{base_url.rstrip('/')}/v1/rerank"
        payload = {
            "model": model_name,
            "query": "hello",
            "documents": ["hello", "world"]
        }
        is_streaming = False
    else:
        url = f"{base_url.rstrip('/')}/v1/chat/completions"
        payload = {
            "model": model_name,
            "messages": [
                {"role": "user", "content": "Respond with a single word hello"}
            ],
            "stream": True,
            "max_tokens": 10
        }
        is_streaming = True

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
        "User-Agent": "Mozilla/5.0"
    }

    if not ssl_verify:
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
    else:
        context = None

    def execute_request(req_url, req_payload, stream_mode):
        req = urllib.request.Request(
            req_url,
            data=json.dumps(req_payload).encode('utf-8'),
            headers=headers,
            method='POST'
        )
        t0 = time.time()
        
        if stream_mode:
            # 30-second timeout to establish connection and receive stream
            with urllib.request.urlopen(req, context=context, timeout=30) as response:
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
                return False, None, "Response stream ended without any tokens"
        else:
            with urllib.request.urlopen(req, context=context, timeout=30) as response:
                response.read()
                latency = time.time() - t0
                return True, latency, None

    try:
        if is_streaming:
            try:
                return execute_request(url, payload, stream_mode=True)
            except urllib.error.HTTPError as e:
                # If streaming fails, retry non-streaming
                error_body = ""
                try:
                    error_body = e.read().decode('utf-8')
                except Exception:
                    pass
                
                payload["stream"] = False
                try:
                    return execute_request(url, payload, stream_mode=False)
                except Exception as retry_err:
                    err_msg = error_body if error_body else str(e)
                    return False, None, f"HTTP Error {e.code}: {e.reason} (Streaming failed: {err_msg}) - Non-streaming retry failed: {retry_err}"
        else:
            try:
                return execute_request(url, payload, stream_mode=False)
            except urllib.error.HTTPError as e:
                if "rerank" in model_lower and e.code == 404 and "/v1/rerank" in url:
                    alt_url = f"{base_url.rstrip('/')}/rerank"
                    try:
                        return execute_request(alt_url, payload, stream_mode=False)
                    except Exception:
                        pass
                raise e
    except urllib.error.HTTPError as e:
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
    parser = argparse.ArgumentParser(description="Test LiteLLM endpoints on api-internal.publicai.co")
    parser.add_argument("--insecure", action="store_true", help="Bypass SSL verification")
    parser.add_argument("--url", default="https://api-internal.publicai.co", help="Base URL of LiteLLM proxy")
    parser.add_argument("--workers", type=int, default=10, help="Number of parallel workers to use")
    args = parser.parse_args()

    # Find project root and load .env
    script_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = script_dir
    while root_dir != os.path.dirname(root_dir):
        if os.path.exists(os.path.join(root_dir, '.env')):
            break
        root_dir = os.path.dirname(root_dir)
        
    env_path = os.path.join(root_dir, '.env')
    load_env(env_path)
    
    api_key = os.environ.get("LITELLM_API_KEY")
    if not api_key:
        print("Error: LITELLM_API_KEY not found in environment or .env file.")
        sys.exit(1)
        
    ssl_verify = not args.insecure
    
    print(f"Connecting to LiteLLM at: {args.url}")
    print(f"SSL verification: {'ENABLED' if ssl_verify else 'DISABLED'}")
    print("Listing models...")
    
    models, err = list_models(args.url, api_key, ssl_verify=ssl_verify)
    if err:
        print(f"Error listing models: {err}")
        sys.exit(1)
        
    if not models:
        print("No models returned by LiteLLM.")
        sys.exit(0)
        
    print(f"Found {len(models)} models: {', '.join(models)}")
    print(f"Testing {len(models)} models in parallel using {args.workers} workers...")
    print("-" * 120)
    
    results = [None] * len(models)
    
    def test_single_model(idx, model):
        success, ttft, error = measure_ttft(args.url, model, api_key, ssl_verify=ssl_verify)
        if success:
            print(f"[{idx}/{len(models)}] {model}: SUCCESS (TTFT: {ttft:.3f}s)")
        else:
            print(f"[{idx}/{len(models)}] {model}: FAILED (Error: {error})")
        return {
            'model': model,
            'success': success,
            'ttft': ttft,
            'error': error
        }

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(test_single_model, idx, model): idx - 1 for idx, model in enumerate(models, 1)}
        for future in concurrent.futures.as_completed(futures):
            idx_zero = futures[future]
            try:
                results[idx_zero] = future.result()
            except Exception as e:
                model = models[idx_zero]
                print(f"[{idx_zero+1}/{len(models)}] {model}: FAILED (Exception: {e})")
                results[idx_zero] = {
                    'model': model,
                    'success': False,
                    'ttft': None,
                    'error': f"Thread Exception: {e}"
                }
        
    print("\n" + "=" * 120)
    print(f"{'Model Name':<50} | {'Status':<12} | {'TTFT (s)':<10}")
    print("-" * 120)
    
    for res in results:
        status_str = "SUCCESS" if res['success'] else "FAILED"
        ttft_str = f"{res['ttft']:.3f}s" if res['success'] else "N/A"
        print(f"{res['model']:<50} | {status_str:<12} | {ttft_str:<10}")
        
    print("=" * 120)
    
    failures = [r for r in results if not r['success']]
    if failures:
        print("\n" + "!" * 120)
        print("FAILURE DETAILS:")
        print("-" * 120)
        for idx, f in enumerate(failures, 1):
            print(f"{idx}. Model: {f['model']}")
            print(f"   Error: {f['error']}")
            print("-" * 120)

if __name__ == "__main__":
    main()
