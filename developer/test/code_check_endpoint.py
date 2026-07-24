#!/usr/bin/env python3
import os
import re
import sys

def find_project_root():
    """Locate the project root directory containing the .env file."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    current = script_dir
    while current != os.path.dirname(current):
        if os.path.exists(os.path.join(current, '.env')):
            return current
        current = os.path.dirname(current)
    return current

def parse_env(env_path):
    """Parse key-value pairs from .env."""
    env_vars = {}
    if not os.path.exists(env_path):
        print(f"Warning: .env file not found at {env_path}")
        return env_vars
    with open(env_path, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if '=' in line:
                key, val = line.split('=', 1)
                env_vars[key.strip()] = val.strip().strip('"').strip("'")
    return env_vars

def parse_web_sh(web_sh_path):
    """Parse required_vars and --set mappings from web.sh."""
    required_vars = []
    set_mappings = {}  # helm_key -> env_var
    
    if not os.path.exists(web_sh_path):
        print(f"Warning: web.sh not found at {web_sh_path}")
        return required_vars, set_mappings
        
    with open(web_sh_path, 'r') as f:
        content = f.read()
        
    # Extract required_vars array content
    req_match = re.search(r'local required_vars=\((.*?)\)', content, re.DOTALL)
    if req_match:
        req_content = req_match.group(1)
        for var in re.findall(r'"([^"]+)"|\'([^\']+)\'', req_content):
            val = var[0] or var[1]
            if val:
                required_vars.append(val.strip())
                
    # Extract --set parameter mappings
    # e.g., --set litellm.secrets.togetherApiKey="$TOGETHER_API_KEY"
    set_matches = re.findall(r'--set\s+([a-zA-Z0-9_.-]+)=["\']?\$([a-zA-Z0-9_]+)["\']?', content)
    for path, var in set_matches:
        set_mappings[path.strip()] = var.strip()
        
    return required_vars, set_mappings

def parse_secrets_yaml(secrets_path):
    """Parse secret key to helm value mappings from secrets.yaml stringData."""
    mappings = {}  # secret_key -> helm_key
    if not os.path.exists(secrets_path):
        print(f"Warning: secrets.yaml not found at {secrets_path}")
        return mappings
        
    with open(secrets_path, 'r') as f:
        for line in f:
            stripped = line.strip()
            if not stripped or stripped.startswith('#'):
                continue
            # Match "together_api_key: {{ .Values.secrets.togetherApiKey | quote }}"
            match = re.match(r'^([a-zA-Z0-9_-]+):\s*\{\{\s*\.Values\.secrets\.([a-zA-Z0-9_-]+)(?:\s*\|\s*\w+)*\s*\}\}', stripped)
            if match:
                mappings[match.group(1)] = match.group(2)
    return mappings

def parse_deployment_yaml(deployment_path):
    """Parse environment variable to secret key mappings from deployment.yaml."""
    mappings = {}  # env_var -> secret_key
    if not os.path.exists(deployment_path):
        print(f"Warning: deployment.yaml not found at {deployment_path}")
        return mappings
        
    current_name = None
    with open(deployment_path, 'r') as f:
        for line in f:
            stripped = line.strip()
            if not stripped or stripped.startswith('#'):
                continue
            # Match "- name: TOGETHER_API_KEY"
            name_match = re.match(r'^-\s*name:\s*([A-Z0-9_]+)', stripped)
            if name_match:
                current_name = name_match.group(1)
                continue
            # Match "key: together_api_key" under secretKeyRef
            key_match = re.match(r'^key:\s*([a-z0-9_-]+)', stripped)
            if key_match and current_name:
                mappings[current_name] = key_match.group(1)
                current_name = None
    return mappings

def parse_values_secrets(values_path):
    """Parse keys defined in values.yaml secrets section."""
    secrets = set()
    if not os.path.exists(values_path):
        print(f"Warning: values.yaml not found at {values_path}")
        return secrets
        
    in_secrets = False
    with open(values_path, 'r') as f:
        for line in f:
            stripped = line.strip()
            if stripped.startswith('#') or not stripped:
                continue
            if stripped.startswith('secrets:'):
                in_secrets = True
                continue
            if in_secrets:
                # If we encounter a new top level block (starts with no indentation or starts with non-space)
                # but allow secrets indentation of usually 2 spaces
                leading_spaces = len(line) - len(line.lstrip(' '))
                if leading_spaces == 0 and ':' in stripped:
                    in_secrets = False
                    continue
                # If indentation is greater, we are inside secrets
                match = re.match(r'^([a-zA-Z0-9_-]+):', stripped)
                if match:
                    key = match.group(1)
                    if key != 'name':
                        secrets.add(key)
    return secrets

def parse_models(models_dir):
    """Parse active model endpoint definitions from all YAML files in models_dir."""
    import yaml
    models = []
    if not os.path.exists(models_dir):
        print(f"Warning: models directory not found at {models_dir}")
        return models
        
    for root_dir, _, files in sorted(os.walk(models_dir)):
        for file in sorted(files):
            if file.endswith('.yaml') or file.endswith('.yml'):
                file_path = os.path.join(root_dir, file)
                try:
                    with open(file_path, 'r') as f:
                        data = yaml.safe_load(f)
                    if not data or 'models' not in data:
                        continue
                    
                    file_fallbacks = data.get('fallbacks', [])
                    
                    for m in data['models']:
                        model_name = m.get('model_name')
                        if not model_name:
                            continue
                        litellm_params = m.get('litellm_params', {})
                        api_base = litellm_params.get('api_base')
                        api_key = litellm_params.get('api_key')
                        
                        models.append({
                            'model_name': model_name,
                            'litellm_model': litellm_params.get('model'),
                            'api_key': api_key,
                            'api_base': api_base,
                            'is_active': True,
                            'fallbacks': file_fallbacks,
                            'file_path': file_path
                        })
                except Exception as e:
                    print(f"Error parsing model file {file_path}: {e}")
    return models

def parse_lago_mappings(callback_path):
    """Parse model billing mappings from custom_lago_callback.py."""
    mappings = {}
    if not os.path.exists(callback_path):
        print(f"Warning: custom_lago_callback.py not found at {callback_path}")
        return mappings
        
    in_mapping = False
    with open(callback_path, 'r') as f:
        for line in f:
            stripped = line.strip()
            if 'model_mapping = {' in stripped:
                in_mapping = True
                continue
            if in_mapping:
                if stripped == '}':
                    in_mapping = False
                    continue
                # Match "key": "value" or 'key': 'value'
                match = re.match(r'^["\']([^"\']+)["\']\s*:\s*["\']([^"\']+)["\']', stripped)
                if match:
                    mappings[match.group(1)] = match.group(2)
    return mappings

def env_var_to_helm_key(env_var):
    """Convert env var name to camelCase Helm key (e.g. TOGETHER_API_KEY -> togetherApiKey)."""
    parts = env_var.lower().split('_')
    return parts[0] + ''.join(x.title() for x in parts[1:])

def helm_key_to_env_var(helm_key):
    """Convert camelCase Helm key to UPPER_SNAKE_CASE (e.g. togetherApiKey -> TOGETHER_API_KEY)."""
    s = re.sub(r'(?<!^)(?=[A-Z])', '_', helm_key)
    return s.upper()

def main():
    root = find_project_root()
    print(f"🔍 Analyzing configuration in project root: {root}\n")
    
    # Define paths
    env_path = os.path.join(root, '.env')
    web_sh_path = os.path.join(root, 'web.sh')
    secrets_yaml_path = os.path.join(root, 'charts/web_services/charts/litellm/templates/secrets.yaml')
    deployment_yaml_path = os.path.join(root, 'charts/web_services/charts/litellm/templates/deployment.yaml')
    values_yaml_path = os.path.join(root, 'charts/web_services/charts/litellm/values.yaml')
    models_dir = os.path.join(root, 'charts/web_services/charts/litellm/models')
    lago_callback_path = os.path.join(root, 'charts/web_services/charts/litellm/custom_lago_callback.py')
    
    # Parse files
    env_vars = parse_env(env_path)
    web_required_vars, web_set_mappings = parse_web_sh(web_sh_path)
    secrets_mappings = parse_secrets_yaml(secrets_yaml_path)
    deployment_mappings = parse_deployment_yaml(deployment_yaml_path)
    values_secrets = parse_values_secrets(values_yaml_path)
    values_models = parse_models(models_dir)
    lago_mappings = parse_lago_mappings(lago_callback_path)
    
    # Collect all API keys / env vars to test
    discovered_keys = set()
    
    # 1. Any var in .env containing _API_KEY
    for k in env_vars:
        if '_API_KEY' in k:
            discovered_keys.add(k)
            
    # 2. Any var in web.sh required_vars containing _API_KEY
    for k in web_required_vars:
        if '_API_KEY' in k:
            discovered_keys.add(k)
            
    # 3. Any var mapped in web.sh --set that contains _API_KEY
    for helm_path, env_var in web_set_mappings.items():
        if '_API_KEY' in env_var:
            discovered_keys.add(env_var)
            
    # 4. Any secrets defined in values.yaml secrets section containing api_key or apikey
    for helm_key in values_secrets:
        if 'apikey' in helm_key.lower() or 'api_key' in helm_key.lower():
            discovered_keys.add(helm_key_to_env_var(helm_key))
            
    # 5. Any os.environ/ references in values.yaml models
    for model in values_models:
        if model['api_key'] and model['api_key'].startswith('os.environ/'):
            var = model['api_key'].split('/', 1)[1]
            discovered_keys.add(var)
            
    # 6. Any var in deployment mappings containing _API_KEY
    for env_var in deployment_mappings:
        if '_API_KEY' in env_var:
            discovered_keys.add(env_var)
            
    # Filter out ignored keys
    IGNORE_KEYS = {"LAGO_API_KEY", "LITELLM_API_KEY"}
    discovered_keys = {k for k in discovered_keys if k not in IGNORE_KEYS}
    
    # We sort them for clean display
    sorted_keys = sorted(list(discovered_keys))
    
    # Print Alignment Table Header
    print(f"{'API Key Env Variable':<28} | {'Env':<4} | {'Req':<4} | {'Set':<4} | {'Val':<4} | {'Sec':<4} | {'Dep':<4} | {'Active Models':<22} | {'Commented Models':<22}")
    print("-" * 120)
    
    alignment_issues = []
    missing_api_keys = []
    unused_api_keys = []
    
    for key in sorted_keys:
        expected_helm = env_var_to_helm_key(key)
        expected_sec_key = key.lower()
        
        # 1. Check in .env
        in_env = key in env_vars
        env_status = "✅" if in_env else "❌"
        
        # 2. Check in web.sh required_vars
        in_web_req = key in web_required_vars
        web_req_status = "✅" if in_web_req else "❌"
        
        # 3. Check in web.sh helm --set
        # e.g., --set litellm.secrets.togetherApiKey="$TOGETHER_API_KEY"
        web_set_status = "❌"
        actual_set_var = None
        for path, var in web_set_mappings.items():
            if path.endswith(expected_helm) or path == f"litellm.secrets.{expected_helm}":
                actual_set_var = var
                if var == key:
                    web_set_status = "✅"
                else:
                    web_set_status = "⚠️"
                    alignment_issues.append(f"web.sh: Helm key 'litellm.secrets.{expected_helm}' maps to variable '{var}', expected '{key}'")
                break
        if web_set_status == "❌":
            # Check if variable itself is mapped under a different Helm key
            for path, var in web_set_mappings.items():
                if var == key:
                    web_set_status = "⚠️"
                    alignment_issues.append(f"web.sh: Variable '{key}' maps to Helm key '{path}', expected 'litellm.secrets.{expected_helm}'")
                    break
        
        # 4. Check in values.yaml secrets section
        in_val = expected_helm in values_secrets
        val_status = "✅" if in_val else "❌"
        
        # 5. Check in secrets.yaml
        sec_status = "❌"
        if expected_sec_key in secrets_mappings:
            actual_helm = secrets_mappings[expected_sec_key]
            if actual_helm == expected_helm:
                sec_status = "✅"
            else:
                sec_status = "⚠️"
                alignment_issues.append(f"secrets.yaml: Secret key '{expected_sec_key}' maps to Helm value '.Values.secrets.{actual_helm}', expected '.Values.secrets.{expected_helm}'")
        else:
            # Check if expected_helm is mapped to a different secret key
            for sk, hk in secrets_mappings.items():
                if hk == expected_helm:
                    sec_status = "⚠️"
                    alignment_issues.append(f"secrets.yaml: Helm value '.Values.secrets.{expected_helm}' maps to secret key '{sk}', expected '{expected_sec_key}'")
                    break
                    
        # 6. Check in deployment.yaml
        dep_status = "❌"
        if key in deployment_mappings:
            actual_sec = deployment_mappings[key]
            if actual_sec == expected_sec_key:
                dep_status = "✅"
            else:
                dep_status = "⚠️"
                alignment_issues.append(f"deployment.yaml: Env var '{key}' injected from secret key '{actual_sec}', expected '{expected_sec_key}'")
        else:
            # Check if expected_sec_key is mapped to a different Env var
            for ev, sk in deployment_mappings.items():
                if sk == expected_sec_key:
                    dep_status = "⚠️"
                    alignment_issues.append(f"deployment.yaml: Secret key '{expected_sec_key}' maps to Env var '{ev}', expected '{key}'")
                    break
                    
        # Find active/commented models referencing this api key
        active_models = []
        commented_models = []
        for m in values_models:
            if m['api_key'] == f"os.environ/{key}":
                if m['is_active']:
                    active_models.append(m['model_name'])
                else:
                    commented_models.append(m['model_name'])
                    
        act_str = ",".join(active_models) if active_models else "❌"
        if len(act_str) > 22:
            act_str = act_str[:19] + "..."
        com_str = ",".join(commented_models) if commented_models else "None"
        if len(com_str) > 22:
            com_str = com_str[:19] + "..."
            
        print(f"{key:<28} | {env_status:<3} | {web_req_status:<3} | {web_set_status:<3} | {val_status:<3} | {sec_status:<3} | {dep_status:<3} | {act_str:<22} | {com_str:<22}")
        
        # Analyze findings
        is_missing_any_config = (env_status != "✅" or web_req_status != "✅" or web_set_status != "✅" 
                                 or val_status != "✅" or sec_status != "✅" or dep_status != "✅")
                                 
        if active_models and is_missing_any_config:
            missing_api_keys.append({
                'key': key,
                'models': active_models,
                'details': {
                    'env': env_status,
                    'web_req': web_req_status,
                    'web_set': web_set_status,
                    'values': val_status,
                    'secrets_yaml': sec_status,
                    'deployment_yaml': dep_status
                }
            })
            
        if not active_models and in_env:
            unused_api_keys.append({
                'key': key,
                'commented': commented_models
            })

    print("-" * 120)
    print("Legend: Env = .env | Req = web.sh required_vars | Set = web.sh helm --set")
    print("        Val = values.yaml secrets | Sec = secrets.yaml | Dep = deployment.yaml\n")
    
    # ----------------------------------------------------
    # Report Section 1: Alignment Mismatches
    # ----------------------------------------------------
    if alignment_issues:
        print("⚠️  ALIGNMENT MISMATCHES FOUND:")
        for idx, issue in enumerate(alignment_issues, 1):
            print(f"  {idx}. {issue}")
        print()
        
    # ----------------------------------------------------
    # Report Section 2: Active Endpoints with Missing Configurations (Endpoint but no API Key)
    # ----------------------------------------------------
    print("🔍 CHECK: ENDPOINT BUT NO API KEY (Active endpoints with incomplete configurations)")
    if missing_api_keys:
        for item in missing_api_keys:
            print(f"❌ Key '{item['key']}' is required by active model(s): {', '.join(item['models'])}")
            missing_parts = []
            for name, status in item['details'].items():
                if status != "✅":
                    missing_parts.append(name)
            print(f"   Missing/Misconfigured in: {', '.join(missing_parts)}")
    else:
        print("✅ No active endpoints have missing API Key configurations.")
    print()

    # ----------------------------------------------------
    # Report Section 3: API Key in .env but No Active Endpoint (API Key but no Endpoint)
    # ----------------------------------------------------
    print("🔍 CHECK: API KEY BUT NO ENDPOINT (Keys in .env with no active endpoints)")
    if unused_api_keys:
        for item in unused_api_keys:
            if item['commented']:
                print(f"ℹ️  Key '{item['key']}' is defined in .env, but corresponding model(s) are COMMENTED-OUT: {', '.join(item['commented'])}")
            else:
                print(f"ℹ️  Key '{item['key']}' is defined in .env, but has NO model configuration (active or commented-out).")
    else:
        print("✅ All defined API Keys are currently mapped to active endpoints.")
    print()

    # ----------------------------------------------------
    # Report Section 4: Lago Callback Mappings
    # ----------------------------------------------------
    print("🔍 CHECK: LAGO BILLING CALLBACK MODEL MAPPINGS")
    active_models_with_keys = [m for m in values_models if m['is_active']]
    missing_lago_mappings = []
    
    for m in active_models_with_keys:
        # Check if the model or its litellm model mapping exists in custom_lago_callback.py
        model_name = m['model_name']
        litellm_model = m['litellm_model']
        
        # Check direct mapping keys
        mapped = False
        if litellm_model in lago_mappings:
            mapped = True
        elif model_name in lago_mappings:
            mapped = True
        else:
            # Check litellm model without standard provider prefix e.g. "openai/"
            stripped_model = litellm_model
            if stripped_model and '/' in stripped_model:
                parts = stripped_model.split('/', 1)
                # If first part is a known provider, strip it
                if parts[0].lower() in ['openai', 'bedrock', 'azure', 'anthropic']:
                    stripped_model = parts[1]
                    if stripped_model in lago_mappings:
                        mapped = True
                        
        if not mapped:
            missing_lago_mappings.append(m)
            
    if missing_lago_mappings:
        for m in missing_lago_mappings:
            print(f"❌ Active model '{m['model_name']}' (model: '{m['litellm_model']}') is MISSING from custom_lago_callback.py mappings!")
    else:
        print("✅ All active models are mapped in custom_lago_callback.py.")
    print()

    # ----------------------------------------------------
    # Report Section 5: Model Configuration Sanity Checks
    # ----------------------------------------------------
    print("🔍 CHECK: MODEL CONFIGURATION AND SANITY CHECKS")
    model_checks_failed = False
    
    # We sort values_models to ensure stable order
    sorted_models = sorted(values_models, key=lambda x: x['model_name'])
    
    for m in sorted_models:
        model_name = m['model_name']
        api_base = m.get('api_base')
        api_key = m.get('api_key')
        fallbacks = m.get('fallbacks', [])
        
        errors = []
        
        # 1. Fallback configured check
        if not fallbacks:
            errors.append("Missing fallback configuration")
            
        # 2. API base check: starts with https:// and ends with v1
        if not api_base:
            errors.append("Missing api_base")
        else:
            if not api_base.startswith("https://"):
                errors.append(f"api_base '{api_base}' does not start with 'https://'")
            if not (api_base.endswith("v1") or api_base.endswith("v1/")):
                errors.append(f"api_base '{api_base}' does not end with 'v1'")
                
        # 3. Valid api key identifier check
        if not api_key:
            errors.append("Missing api_key")
        else:
            if not api_key.startswith("os.environ/"):
                errors.append(f"api_key '{api_key}' is not a valid environment reference (must start with 'os.environ/')")
            else:
                env_var_part = api_key.split('/', 1)[1]
                if not re.match(r'^[A-Z][A-Z0-9_]*$', env_var_part):
                    errors.append(f"api_key reference environment variable '{env_var_part}' is invalid (must be UPPER_SNAKE_CASE)")
                    
        if errors:
            model_checks_failed = True
            print(f"❌ Model '{model_name}':")
            for err in errors:
                print(f"   - {err}")
        else:
            print(f"✅ Model '{model_name}': Passed all sanity checks")
    print()

if __name__ == '__main__':
    main()
