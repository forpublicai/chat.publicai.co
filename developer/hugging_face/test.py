#!/usr/bin/env python3
import os
import ssl
import sys
import time
import json
import argparse
import subprocess
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

def get_models_from_script(script_path, token):
    """Run get_models.sh and return list of model IDs."""
    if not os.path.exists(script_path):
        raise FileNotFoundError(f"Script not found at {script_path}")
    
    cmd = [script_path, "-t", token]
    try:
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        data = json.loads(result.stdout)
        models = []
        for category, category_models in data.items():
            if isinstance(category_models, dict):
                for hf_model_id in category_models.keys():
                    models.append(hf_model_id)
        return sorted(list(set(models)))
    except subprocess.CalledProcessError as e:
        print(f"Error running {script_path}: {e.stderr}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON from get_models.sh: {e}")
        sys.exit(1)

def measure_ttft(base_url, model_id, token, ssl_verify=True):
    """Call the Hugging Face router chat completion and measure Time to First Token (TTFT)."""
    url = f"{base_url.rstrip('/')}/chat/completions"
    
    # Model name format expected by router.huggingface.co
    model_name = f"{model_id}:publicai"
    
    payload = {
        "model": model_name,
        "messages": [
            {"role": "user", "content": "Respond with a single word hello"}
        ],
        "stream": True,
        "max_tokens": 10
    }
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
        "User-Agent": "Mozilla/5.0",
        # "X-HF-Bill-To": "publicai"
        "X-HF-Bill-To": "current-ai-official"
    }
    
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode('utf-8'),
        headers=headers,
        method='POST'
    )
    
    if not ssl_verify:
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
    else:
        context = None
        
    t0 = time.time()
    try:
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
    parser = argparse.ArgumentParser(description="Test Hugging Face Router endpoints for partner models")
    parser.add_argument("--insecure", action="store_true", help="Bypass SSL verification")
    parser.add_argument("--url", default="https://router.huggingface.co/v1", help="Base URL of Hugging Face router")
    parser.add_argument("--workers", type=int, default=5, help="Number of parallel workers to use")
    args = parser.parse_args()

    # Find env file in same directory as this script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    env_path = os.path.join(script_dir, '.env')
    load_env(env_path)
    
    # Load HF_TEST_TOKEN as requested
    token = os.environ.get("HF_TEST_TOKEN")
    if not token:
        print("Error: HF_TEST_TOKEN not found in environment or .env file.")
        sys.exit(1)
        
    ssl_verify = not args.insecure
    
    print(f"Connecting to Hugging Face Router at: {args.url}")
    print(f"SSL verification: {'ENABLED' if ssl_verify else 'DISABLED'}")
    print("Finding models on Hugging Face account via get_models.sh...")
    
    get_models_script = os.path.join(script_dir, "get_models.sh")
    models = get_models_from_script(get_models_script, token)
    
    if not models:
        print("No models found on Hugging Face account.")
        sys.exit(0)
        
    print(f"Found {len(models)} models: {', '.join(models)}")
    print(f"Testing {len(models)} models in parallel using {args.workers} workers...")
    print("-" * 120)
    
    results = [None] * len(models)
    
    def test_single_model(idx, model):
        success, ttft, error = measure_ttft(args.url, model, token, ssl_verify=ssl_verify)
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
