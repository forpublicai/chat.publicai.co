#!/usr/bin/env python3
"""
Model & Configuration Validator for LiteLLM Helm Chart.

Validates:
1. Model YAML formatting, structure, types, and parameters under charts/platform/charts/litellm/models/
2. Secret passing pipeline across:
   - Model YAML (os.environ/<VAR>)
   - secrets.yaml (ExternalSecret spec.data & template.data)
   - deployment.yaml (container env vars & secretKeyRef)
3. Lago billing callback normalization mapping in custom_lago_callback.py
4. Fallback model references, broken links, typos, and circular fallback loops
5. Detection of human errors (copy-paste mismatches, size mismatches, syntax errors, typos)
"""

import os
import sys
import re
import ast
import json
import difflib
import argparse
from typing import Dict, List, Set, Any, Optional, Tuple

try:
    import yaml
except ImportError:
    print("Error: 'pyyaml' is required. Run 'pip install pyyaml'.", file=sys.stderr)
    sys.exit(1)


# ANSI Color Codes for pretty terminal output
class Colors:
    HEADER = "\033[95m"
    OKBLUE = "\033[94m"
    OKCYAN = "\033[96m"
    OKGREEN = "\033[92m"
    WARNING = "\033[93m"
    FAIL = "\033[91m"
    ENDC = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"

    @classmethod
    def disable(cls):
        cls.HEADER = ""
        cls.OKBLUE = ""
        cls.OKCYAN = ""
        cls.OKGREEN = ""
        cls.WARNING = ""
        cls.FAIL = ""
        cls.ENDC = ""
        cls.BOLD = ""
        cls.DIM = ""


class ValidationIssue:
    def __init__(
        self,
        severity: str,  # "ERROR", "WARNING", "INFO"
        category: str,
        message: str,
        file_path: Optional[str] = None,
        suggestion: Optional[str] = None,
    ):
        self.severity = severity
        self.category = category
        self.message = message
        self.file_path = file_path
        self.suggestion = suggestion

    def to_dict(self) -> Dict[str, Any]:
        data = {
            "severity": self.severity,
            "category": self.category,
            "message": self.message,
        }
        if self.file_path:
            data["file_path"] = self.file_path
        if self.suggestion:
            data["suggestion"] = self.suggestion
        return data


class ModelCodeChecker:
    VALID_ENVIRONMENTS = {"staging", "prod"}
    TYPO_ENV_MAP = {
        "production": "prod",
        "prd": "prod",
        "stg": "staging",
        "stagging": "staging",
        "stagin": "staging",
        "development": "staging",
        "dev": "staging",
    }

    def __init__(self, repo_root: Optional[str] = None, verbose: bool = False, strict: bool = False):
        self.verbose = verbose
        self.strict = strict
        self.repo_root = self._detect_repo_root(repo_root)

        # File and directory paths
        self.litellm_chart_dir = os.path.join(self.repo_root, "charts/platform/charts/litellm")
        self.models_dir = os.path.join(self.litellm_chart_dir, "models")
        self.secrets_yaml_path = os.path.join(self.litellm_chart_dir, "templates/secrets.yaml")
        self.deployment_yaml_path = os.path.join(self.litellm_chart_dir, "templates/deployment.yaml")
        self.configmap_yaml_path = os.path.join(self.litellm_chart_dir, "templates/configmap.yaml")
        self.lago_callback_path = os.path.join(self.litellm_chart_dir, "custom_lago_callback.py")

        self.issues: List[ValidationIssue] = []

        # Parsed state
        self.model_files_data: Dict[str, Any] = {}
        self.active_models: List[Dict[str, Any]] = []
        self.all_model_names_by_env: Dict[str, Set[str]] = {"staging": set(), "prod": set()}
        self.required_env_vars: Set[str] = set()

        # Secret configuration mappings
        self.external_secret_spec_data: Dict[str, str] = {}  # secretKey -> property
        self.external_secret_template_data: Dict[str, List[str]] = {}  # k8s_secret_key -> [REF_VARS]
        self.deployment_env_vars: Dict[str, str] = {}  # ENV_NAME -> secretKeyRef.key
        self.lago_model_mapping: Dict[str, str] = {}

    def _detect_repo_root(self, candidate: Optional[str]) -> str:
        if candidate and os.path.isdir(candidate):
            return os.path.abspath(candidate)

        # Search upwards from current script location
        current = os.path.abspath(os.path.dirname(__file__))
        while current and current != os.path.dirname(current):
            if os.path.exists(os.path.join(current, "charts/platform/charts/litellm")):
                return current
            current = os.path.dirname(current)

        # Fallback to current working directory
        cwd = os.getcwd()
        if os.path.exists(os.path.join(cwd, "charts/platform/charts/litellm")):
            return cwd

        return os.path.abspath(".")

    def add_issue(
        self,
        severity: str,
        category: str,
        message: str,
        file_path: Optional[str] = None,
        suggestion: Optional[str] = None,
    ):
        rel_path = os.path.relpath(file_path, self.repo_root) if file_path else None
        self.issues.append(ValidationIssue(severity, category, message, rel_path, suggestion))

    def run_all_checks(self, target_env: Optional[str] = None) -> bool:
        """Executes all validation checks. Returns True if no ERRORs found (and no WARNINGs if strict)."""
        self.issues.clear()

        # Step 1: Check critical files exist
        if not self._check_required_files():
            return False

        # Step 2: Parse secrets.yaml, deployment.yaml, and custom_lago_callback.py
        self._parse_secrets_yaml()
        self._parse_deployment_yaml()
        self._parse_lago_callback()

        # Step 3: Parse and validate all model YAML files
        self._parse_and_validate_models(target_env)

        # Step 4: Validate Secret passing pipeline
        self._validate_secrets_pipeline()

        # Step 5: Validate Fallbacks & Circular dependency checks
        self._validate_fallbacks()

        # Step 6: Validate Lago billing normalization
        self._validate_lago_normalization()

        # Step 7: Check for orphaned secrets or mappings
        self._check_orphaned_configs()

        has_errors = any(i.severity == "ERROR" for i in self.issues)
        has_warnings = any(i.severity == "WARNING" for i in self.issues)

        if self.strict:
            return not (has_errors or has_warnings)
        return not has_errors

    def _check_required_files(self) -> bool:
        required_paths = [
            ("Models Directory", self.models_dir, True),
            ("Secrets Template", self.secrets_yaml_path, False),
            ("Deployment Template", self.deployment_yaml_path, False),
            ("Lago Callback", self.lago_callback_path, False),
            ("ConfigMap Template", self.configmap_yaml_path, False),
        ]

        all_ok = True
        for name, path, is_dir in required_paths:
            rel = os.path.relpath(path, self.repo_root)
            if is_dir:
                if not os.path.isdir(path):
                    self.add_issue("ERROR", "File Structure", f"Required directory not found: {rel}")
                    all_ok = False
            else:
                if not os.path.isfile(path):
                    self.add_issue("ERROR", "File Structure", f"Required file not found: {rel}")
                    all_ok = False
        return all_ok

    def _parse_secrets_yaml(self):
        """Extracts secret mappings from charts/platform/charts/litellm/templates/secrets.yaml."""
        if not os.path.isfile(self.secrets_yaml_path):
            return

        with open(self.secrets_yaml_path, "r") as f:
            content = f.read()

        # 1. Parse template.data section
        # Format: <k8s_key>: '{{ "{{ .<REMOTE_VAR> }}" }}' or postgres URL with multiple variables
        template_match = re.search(
            r"template:\s*(?:engineVersion:[^\n]*\n\s*)?data:\s*\n((?:[ \t]+[a-zA-Z0-9_-]+:[^\n]*\n?)+)",
            content,
        )
        if template_match:
            lines = template_match.group(1).splitlines()
            for line in lines:
                m = re.match(r"^\s*([a-zA-Z0-9_-]+)\s*:\s*(.*)", line)
                if m:
                    k8s_key = m.group(1)
                    val = m.group(2)
                    # Find all references to .VAR
                    refs = re.findall(r"\.([A-Za-z0-9_]+)", val)
                    self.external_secret_template_data[k8s_key] = refs

        # 2. Parse spec.data section (secretKey to remote property)
        # Format: `- secretKey: FOO` followed by `property: BAR`
        spec_data_match = re.search(
            r"spec:.*?data:\s*\n((?:[ \t]+-[^\n]*\n?(?:[ \t]+[^\n]*\n?)*)+)",
            content,
            re.DOTALL,
        )
        if spec_data_match:
            entries = re.split(r"\n\s*-\s*", spec_data_match.group(1))
            for entry in entries:
                sk_m = re.search(r"secretKey:\s*([A-Za-z0-9_]+)", entry)
                prop_m = re.search(r"property:\s*([A-Za-z0-9_]+)", entry)
                if sk_m:
                    sec_key = sk_m.group(1)
                    prop_key = prop_m.group(1) if prop_m else sec_key
                    self.external_secret_spec_data[sec_key] = prop_key

    def _parse_deployment_yaml(self):
        """Extracts env variables from charts/platform/charts/litellm/templates/deployment.yaml."""
        if not os.path.isfile(self.deployment_yaml_path):
            return

        with open(self.deployment_yaml_path, "r") as f:
            content = f.read()

        # Find container env block
        env_match = re.search(
            r"containers:.*?env:\s*\n((?:[ \t]+-[^\n]*\n?(?:[ \t]+[^\n]*\n?)*)+)",
            content,
            re.DOTALL,
        )
        if env_match:
            entries = re.split(r"\n\s*-\s*", env_match.group(1))
            for entry in entries:
                name_m = re.search(r"name:\s*([A-Za-z0-9_]+)", entry)
                key_m = re.search(r"secretKeyRef:.*?key:\s*([A-Za-z0-9_-]+)", entry, re.DOTALL)
                if name_m:
                    env_name = name_m.group(1)
                    if key_m:
                        self.deployment_env_vars[env_name] = key_m.group(1)
                    else:
                        self.deployment_env_vars[env_name] = ""

    def _parse_lago_callback(self):
        """Extracts model_mapping dict from custom_lago_callback.py using AST."""
        if not os.path.isfile(self.lago_callback_path):
            return

        try:
            with open(self.lago_callback_path, "r") as f:
                tree = ast.parse(f.read())

            for node in ast.walk(tree):
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name) and target.id == "model_mapping":
                            if isinstance(node.value, ast.Dict):
                                for k, v in zip(node.value.keys, node.value.values):
                                    if isinstance(k, ast.Constant) and isinstance(v, ast.Constant):
                                        self.lago_model_mapping[str(k.value)] = str(v.value)
        except Exception as e:
            self.add_issue(
                "ERROR",
                "Lago Callback",
                f"Failed to parse custom_lago_callback.py: {e}",
                self.lago_callback_path,
            )

    def _parse_and_validate_models(self, target_env: Optional[str] = None):
        """Scans and validates all model YAML files under charts/platform/charts/litellm/models/."""
        if not os.path.isdir(self.models_dir):
            return

        yaml_files = []
        for root_dir, _, files in os.walk(self.models_dir):
            for file in files:
                if file.endswith((".yaml", ".yml")):
                    yaml_files.append(os.path.join(root_dir, file))

        if not yaml_files:
            self.add_issue(
                "WARNING",
                "Model Directory",
                f"No YAML files found in {self.models_dir}",
                self.models_dir,
            )
            return

        for file_path in sorted(yaml_files):
            self._validate_single_model_file(file_path, target_env)

    def _validate_single_model_file(self, file_path: str, target_env: Optional[str] = None):
        rel_path = os.path.relpath(file_path, self.repo_root)

        # Check directory structure: should be models/<provider>/<model>.yaml
        parts = os.path.normpath(os.path.relpath(file_path, self.models_dir)).split(os.sep)
        if len(parts) < 2:
            self.add_issue(
                "WARNING",
                "File Organization",
                f"Model file '{rel_path}' is placed directly in models root. Recommended: models/<provider>/<model_name>.yaml",
                file_path,
            )

        try:
            with open(file_path, "r") as f:
                content = f.read()
                data = yaml.safe_load(content)
        except yaml.YAMLError as e:
            self.add_issue("ERROR", "YAML Syntax", f"Malformed YAML file: {e}", file_path)
            return
        except Exception as e:
            self.add_issue("ERROR", "File Read", f"Error reading file: {e}", file_path)
            return

        if data is None:
            self.add_issue("WARNING", "Empty File", "File is completely empty", file_path)
            return

        if not isinstance(data, dict):
            self.add_issue("ERROR", "Schema", "Root element must be a YAML mapping/dictionary", file_path)
            return

        # 1. Validate 'environments'
        environments = data.get("environments")
        if environments is None:
            self.add_issue(
                "ERROR",
                "Schema",
                "Missing required field 'environments'",
                file_path,
                "Add 'environments:\n  - staging\n  - prod'",
            )
            environments = []
        elif not isinstance(environments, list) or len(environments) == 0:
            self.add_issue(
                "ERROR",
                "Schema",
                "'environments' must be a non-empty list of environment names",
                file_path,
            )
            environments = []
        else:
            for env in environments:
                if not isinstance(env, str):
                    self.add_issue(
                        "ERROR",
                        "Schema",
                        f"Environment name must be a string, got: {type(env).__name__}",
                        file_path,
                    )
                    continue
                env_lower = env.lower()
                if env_lower in self.TYPO_ENV_MAP:
                    suggested = self.TYPO_ENV_MAP[env_lower]
                    self.add_issue(
                        "ERROR",
                        "Typo",
                        f"Unrecognized environment '{env}'. Did you mean '{suggested}'?",
                        file_path,
                        f"Change '{env}' to '{suggested}'",
                    )
                elif env_lower not in self.VALID_ENVIRONMENTS:
                    self.add_issue(
                        "WARNING",
                        "Schema",
                        f"Non-standard environment name '{env}'. Expected one of {sorted(list(self.VALID_ENVIRONMENTS))}",
                        file_path,
                    )

        # 2. Validate 'models'
        models = data.get("models")
        if models is None or (isinstance(models, list) and len(models) == 0):
            # Check if models were commented out
            if re.search(r"^\s*#\s*models\s*:", content, re.MULTILINE):
                self.add_issue(
                    "INFO",
                    "Inactive Model",
                    "Model definition is commented out in YAML",
                    file_path,
                )
            else:
                self.add_issue(
                    "WARNING",
                    "Schema",
                    "No 'models' list defined in this file",
                    file_path,
                )
            return

        if not isinstance(models, list):
            self.add_issue("ERROR", "Schema", "'models' must be a list of model configurations", file_path)
            return

        # Store validated models
        self.model_files_data[file_path] = data

        for idx, model_entry in enumerate(models):
            if not isinstance(model_entry, dict):
                self.add_issue("ERROR", "Schema", f"Model item #{idx+1} must be a dictionary", file_path)
                continue

            self._validate_model_entry(file_path, idx, model_entry, environments, target_env)

    def _extract_model_size_and_traits(self, text: str) -> Dict[str, Any]:
        """Extracts model capacity (e.g. 8b, 70b) and traits (e.g. thinking) for consistency checks."""
        text_lower = text.lower()
        size_match = re.search(r"[-_]([0-9]+(?:\.[0-9]+)?[bmk])(?:[-_./]|$)", text_lower)
        size = size_match.group(1) if size_match else None
        is_thinking = "thinking" in text_lower or "think" in text_lower
        return {"size": size, "thinking": is_thinking}

    def _validate_model_entry(
        self,
        file_path: str,
        index: int,
        entry: Dict[str, Any],
        environments: List[str],
        target_env: Optional[str] = None,
    ):
        model_name = entry.get("model_name")
        file_basename = os.path.basename(file_path)

        # Validate model_name
        if not model_name or not isinstance(model_name, str):
            self.add_issue(
                "ERROR",
                "Schema",
                f"Model item #{index+1} is missing required string 'model_name'",
                file_path,
            )
            return

        # Check model_name format
        if " " in model_name:
            self.add_issue("ERROR", "Model Name", f"Model name '{model_name}' contains whitespace", file_path)
        if "/" not in model_name:
            self.add_issue(
                "WARNING",
                "Model Name",
                f"Model name '{model_name}' does not follow '<provider>/<name>' naming convention",
                file_path,
            )

        # Record active model for environments
        for env in environments:
            if target_env and env != target_env:
                continue
            if env in self.all_model_names_by_env:
                self.all_model_names_by_env[env].add(model_name)

        # Validate litellm_params
        litellm_params = entry.get("litellm_params")
        if not litellm_params or not isinstance(litellm_params, dict):
            self.add_issue(
                "ERROR",
                "Schema",
                f"Model '{model_name}' is missing required dictionary 'litellm_params'",
                file_path,
            )
            return

        # Validate litellm_params.model
        param_model = litellm_params.get("model")
        if not param_model or not isinstance(param_model, str):
            self.add_issue(
                "ERROR",
                "Schema",
                f"Model '{model_name}' litellm_params is missing required string 'model' (e.g. 'openai/...', 'bedrock/...')",
                file_path,
            )
        else:
            # Check for copy-paste parameter mismatches between filename, model_name, and litellm_params.model
            name_traits = self._extract_model_size_and_traits(model_name)
            param_traits = self._extract_model_size_and_traits(param_model)
            file_traits = self._extract_model_size_and_traits(file_basename)

            # Check size mismatch (e.g. 8b vs 70b copy-paste bug)
            if name_traits["size"] and param_traits["size"] and name_traits["size"] != param_traits["size"]:
                self.add_issue(
                    "WARNING",
                    "Copy-Paste Mismatch",
                    f"Model size mismatch in '{model_name}': model_name indicates '{name_traits['size']}' but litellm_params.model is '{param_model}' (indicates '{param_traits['size']}')",
                    file_path,
                )
            elif file_traits["size"] and param_traits["size"] and file_traits["size"] != param_traits["size"]:
                self.add_issue(
                    "WARNING",
                    "Copy-Paste Mismatch",
                    f"Filename indicates '{file_traits['size']}' ({file_basename}) but litellm_params.model indicates '{param_traits['size']}' ({param_model})",
                    file_path,
                )

            # Check thinking variant mismatch
            if name_traits["thinking"] != param_traits["thinking"]:
                variant_desc = "thinking" if name_traits["thinking"] else "standard"
                param_desc = "thinking" if param_traits["thinking"] else "standard"
                self.add_issue(
                    "WARNING",
                    "Variant Mismatch",
                    f"Variant mismatch in '{model_name}': model_name is {variant_desc} variant, but litellm_params.model is {param_desc} ({param_model})",
                    file_path,
                )

        # Validate api_base if present
        api_base = litellm_params.get("api_base")
        if api_base is not None:
            if not isinstance(api_base, str) or not (api_base.startswith("http://") or api_base.startswith("https://")):
                self.add_issue(
                    "ERROR",
                    "API Base",
                    f"Model '{model_name}' has invalid api_base '{api_base}'. Must start with http:// or https://",
                    file_path,
                )
            if " " in str(api_base):
                self.add_issue("ERROR", "API Base", f"Model '{model_name}' api_base contains whitespace", file_path)

        # Validate api_key if present
        api_key = litellm_params.get("api_key")
        env_var_name = None
        if api_key is not None:
            if isinstance(api_key, str) and api_key.startswith("os.environ/"):
                env_var_name = api_key[len("os.environ/") :].strip()
                if not env_var_name:
                    self.add_issue(
                        "ERROR",
                        "Secret Config",
                        f"Model '{model_name}' has empty env variable in api_key: '{api_key}'",
                        file_path,
                    )
                elif not re.match(r"^[A-Z0-9_]+$", env_var_name):
                    self.add_issue(
                        "ERROR",
                        "Secret Config",
                        f"Model '{model_name}' environment variable '{env_var_name}' must be uppercase alphanumeric with underscores",
                        file_path,
                    )
                else:
                    self.required_env_vars.add(env_var_name)
            elif isinstance(api_key, str) and api_key.startswith("os.environ."):
                self.add_issue(
                    "ERROR",
                    "Secret Config",
                    f"Model '{model_name}' has typo in api_key: '{api_key}'. Must use slash: 'os.environ/<VAR>'",
                    file_path,
                    f"Change '{api_key}' to 'os.environ/{api_key[len('os.environ.'):]}'",
                )
            elif isinstance(api_key, str) and ("os.getenv" in api_key or "${" in api_key):
                self.add_issue(
                    "ERROR",
                    "Secret Config",
                    f"Model '{model_name}' has invalid api_key syntax: '{api_key}'. Must be 'os.environ/<VAR>'",
                    file_path,
                )

        # Type checks for optional numeric/bool params
        bool_params = ["ssl_verify", "supports_vision"]
        for bp in bool_params:
            if bp in litellm_params and not isinstance(litellm_params[bp], bool):
                self.add_issue(
                    "ERROR",
                    "Param Type",
                    f"Model '{model_name}' parameter '{bp}' must be boolean (true/false)",
                    file_path,
                )

        float_params = ["temperature", "top_p", "weight"]
        for fp in float_params:
            if fp in litellm_params and not isinstance(litellm_params[fp], (int, float)):
                self.add_issue(
                    "ERROR",
                    "Param Type",
                    f"Model '{model_name}' parameter '{fp}' must be a number",
                    file_path,
                )

        if "temperature" in litellm_params and isinstance(litellm_params["temperature"], (int, float)):
            if not (0.0 <= litellm_params["temperature"] <= 2.0):
                self.add_issue(
                    "WARNING",
                    "Param Range",
                    f"Model '{model_name}' temperature '{litellm_params['temperature']}' is outside normal range [0.0, 2.0]",
                    file_path,
                )

        if "top_p" in litellm_params and isinstance(litellm_params["top_p"], (int, float)):
            if not (0.0 <= litellm_params["top_p"] <= 1.0):
                self.add_issue(
                    "WARNING",
                    "Param Range",
                    f"Model '{model_name}' top_p '{litellm_params['top_p']}' is outside normal range [0.0, 1.0]",
                    file_path,
                )

        if "max_tokens" in litellm_params and (not isinstance(litellm_params["max_tokens"], int) or litellm_params["max_tokens"] <= 0):
            self.add_issue(
                "ERROR",
                "Param Type",
                f"Model '{model_name}' 'max_tokens' must be a positive integer",
                file_path,
            )

        # Validate model_info if present
        model_info = entry.get("model_info")
        if model_info is not None:
            if not isinstance(model_info, dict):
                self.add_issue(
                    "ERROR",
                    "Schema",
                    f"Model '{model_name}' 'model_info' must be a dictionary",
                    file_path,
                )
            else:
                for cost_key in ["input_cost_per_token", "output_cost_per_token"]:
                    if cost_key in model_info and not isinstance(model_info[cost_key], (int, float)):
                        self.add_issue(
                            "ERROR",
                            "Pricing",
                            f"Model '{model_name}' model_info '{cost_key}' must be a number",
                            file_path,
                        )

        # Save active model record
        self.active_models.append(
            {
                "file_path": file_path,
                "model_name": model_name,
                "param_model": param_model,
                "api_key_env": env_var_name,
                "environments": environments,
                "fallbacks": entry.get("fallbacks") or self.model_files_data.get(file_path, {}).get("fallbacks", []),
            }
        )

    def _validate_secrets_pipeline(self):
        """Validates that every os.environ/<VAR> is wired up in secrets.yaml and deployment.yaml."""
        for env_var in sorted(self.required_env_vars):
            # 1. Check spec.data in secrets.yaml
            if env_var not in self.external_secret_spec_data:
                close_matches = difflib.get_close_matches(env_var, self.external_secret_spec_data.keys(), n=1)
                hint = f" Did you mean '{close_matches[0]}'?" if close_matches else ""
                self.add_issue(
                    "ERROR",
                    "Missing Secret",
                    f"Environment variable '{env_var}' is used in a model but is missing from ExternalSecret 'spec.data' in secrets.yaml.{hint}",
                    self.secrets_yaml_path,
                    f"Add to secrets.yaml spec.data:\n  - secretKey: {env_var}\n    remoteRef:\n      key: {{{{ .Values.secrets.manualSecretsName }}}}\n      property: {env_var}",
                )

            # 2. Check spec.target.template.data in secrets.yaml
            matching_k8s_keys = [
                k8s_key
                for k8s_key, refs in self.external_secret_template_data.items()
                if env_var in refs or k8s_key.upper() == env_var.upper()
            ]

            if not matching_k8s_keys:
                suggested_k8s_key = env_var.lower()
                self.add_issue(
                    "ERROR",
                    "Missing Secret Template",
                    f"Secret key mapping for '{env_var}' is missing in ExternalSecret 'spec.target.template.data' in secrets.yaml.",
                    self.secrets_yaml_path,
                    f"Add to secrets.yaml spec.target.template.data:\n  {suggested_k8s_key}: '{{{{ \"{{ .{env_var} }}\" }}}}'",
                )
                k8s_secret_key = suggested_k8s_key
            else:
                k8s_secret_key = matching_k8s_keys[0]

            # 3. Check deployment.yaml container env
            if env_var not in self.deployment_env_vars:
                close_matches = difflib.get_close_matches(env_var, self.deployment_env_vars.keys(), n=1)
                hint = f" Did you mean '{close_matches[0]}'?" if close_matches else ""
                self.add_issue(
                    "ERROR",
                    "Missing Deployment Env",
                    f"Environment variable '{env_var}' is referenced in model YAML but not exposed in deployment.yaml container 'env'.{hint}",
                    self.deployment_yaml_path,
                    f"Add to deployment.yaml container env:\n  - name: {env_var}\n    valueFrom:\n      secretKeyRef:\n        name: {{{{ .Values.secrets.name }}}}\n        key: {k8s_secret_key}\n        optional: true",
                )
            else:
                # Check that secretKeyRef.key matches k8s_secret_key
                dep_key = self.deployment_env_vars[env_var]
                if matching_k8s_keys and dep_key and dep_key not in matching_k8s_keys:
                    self.add_issue(
                        "ERROR",
                        "Secret Key Mismatch",
                        f"Deployment env '{env_var}' references secret key '{dep_key}', but secrets.yaml template defines '{matching_k8s_keys[0]}'",
                        self.deployment_yaml_path,
                        f"Change deployment.yaml secretKeyRef key from '{dep_key}' to '{matching_k8s_keys[0]}'",
                    )

    def _validate_fallbacks(self):
        """Checks fallback model references for broken links, typos, and circular cycles."""
        fallback_graph: Dict[str, List[str]] = {}

        for model in self.active_models:
            model_name = model["model_name"]
            fallbacks = model.get("fallbacks") or []
            file_path = model["file_path"]

            if not fallbacks:
                continue

            if not isinstance(fallbacks, list):
                self.add_issue(
                    "ERROR",
                    "Fallback Schema",
                    f"Fallbacks for '{model_name}' must be a list of model names",
                    file_path,
                )
                continue

            fallback_graph[model_name] = fallbacks

            for fb in fallbacks:
                if not isinstance(fb, str):
                    self.add_issue(
                        "ERROR",
                        "Fallback Schema",
                        f"Fallback entry must be a string, got {type(fb).__name__}",
                        file_path,
                    )
                    continue

                if fb == model_name:
                    self.add_issue(
                        "ERROR",
                        "Fallback Cycle",
                        f"Model '{model_name}' lists itself as a fallback target (self-referencing cycle)",
                        file_path,
                    )
                    continue

                # Verify fallback exists in at least one environment where the model is active
                for env in model["environments"]:
                    if env in self.all_model_names_by_env:
                        available = self.all_model_names_by_env[env]
                        if available and fb not in available:
                            close = difflib.get_close_matches(fb, available, n=1)
                            hint = f" Did you mean '{close[0]}'?" if close else ""
                            self.add_issue(
                                "ERROR",
                                "Broken Fallback",
                                f"Fallback '{fb}' for model '{model_name}' in environment '{env}' does not match any active model.{hint}",
                                file_path,
                            )

        # Check for circular cycles (e.g. A -> B -> A)
        for start_node in fallback_graph:
            visited = set()
            stack = [start_node]
            while stack:
                curr = stack.pop()
                for nxt in fallback_graph.get(curr, []):
                    if nxt == start_node:
                        self.add_issue(
                            "WARNING",
                            "Circular Fallback",
                            f"Detected circular fallback chain involving '{start_node}' and '{curr}'",
                        )
                        break
                    if nxt not in visited and nxt in fallback_graph:
                        visited.add(nxt)
                        stack.append(nxt)

    def _validate_lago_normalization(self):
        """Validates that custom_lago_callback.py handles all active models."""
        if not self.lago_model_mapping:
            return

        for model in self.active_models:
            model_name = model["model_name"]
            param_model = model.get("param_model", "")

            # Bedrock models or models with prefix like 'openai/' need mapping
            needs_mapping = (
                param_model.startswith("openai/")
                or param_model.startswith("bedrock/")
                or ":" in param_model
                or param_model != model_name
            )

            # Check if mapped
            has_param_mapping = param_model in self.lago_model_mapping
            has_name_mapping = model_name in self.lago_model_mapping

            if needs_mapping and not (has_param_mapping or has_name_mapping):
                self.add_issue(
                    "WARNING",
                    "Lago Callback Mapping",
                    f"Model '{model_name}' (litellm model: '{param_model}') is not explicitly mapped in custom_lago_callback.py 'model_mapping'",
                    self.lago_callback_path,
                    f"Add to model_mapping in custom_lago_callback.py:\n  \"{param_model}\": \"{model_name}\",\n  \"{model_name}\": \"{model_name}\",",
                )
            elif has_param_mapping:
                # Check mapped target
                target = self.lago_model_mapping[param_model]
                # If target is neither the full model_name nor matches its organization suffix, flag warning
                if target != model_name and not model_name.endswith(target) and not target.endswith(model_name):
                    self.add_issue(
                        "WARNING",
                        "Lago Callback Mapping",
                        f"Model mapping for '{param_model}' maps to '{target}', but model_name is '{model_name}'",
                        self.lago_callback_path,
                    )

    def _check_orphaned_configs(self):
        """Identifies unused secrets to keep the codebase clean."""
        all_model_files = []
        for root_dir, _, files in os.walk(self.models_dir):
            for file in files:
                if file.endswith((".yaml", ".yml")):
                    all_model_files.append(os.path.join(root_dir, file))

        all_file_content = ""
        for p in all_model_files:
            try:
                with open(p, "r") as f:
                    all_file_content += f.read() + "\n"
            except Exception:
                pass

        # Standard system secrets to ignore
        system_secrets = {
            "AWS_REGION",
            "LITELLM_MODE",
            "LITELLM_SALT_KEY",
            "USE_PRISMA_MIGRATE",
            "LITELLM_MASTER_KEY",
            "DATABASE_URL",
            "REDIS_URL",
            "REDIS_HOST",
            "REDIS_PORT",
            "LITELLM_REDIS_PORT",
            "LAGO_API_BASE",
            "LAGO_API_KEY",
            "LAGO_API_EVENT_CODE",
            "LAGO_API_CHARGE_BY",
            "SLACK_WEBHOOK_URL",
        }

        for env_name in self.deployment_env_vars:
            if env_name in system_secrets:
                continue
            if env_name not in self.required_env_vars and f"os.environ/{env_name}" not in all_file_content:
                self.add_issue(
                    "INFO",
                    "Orphaned Config",
                    f"Environment variable '{env_name}' is defined in deployment.yaml but not referenced by any model YAML",
                    self.deployment_yaml_path,
                )

    def format_cli_report(self) -> str:
        """Generates a formatted human-readable report."""
        lines = []
        lines.append(f"{Colors.BOLD}{Colors.HEADER}================================================================={Colors.ENDC}")
        lines.append(f"{Colors.BOLD}{Colors.HEADER}              LiteLLM Model & Configuration Checker              {Colors.ENDC}")
        lines.append(f"{Colors.BOLD}{Colors.HEADER}================================================================={Colors.ENDC}")

        # Summary statistics
        total_files = len(self.model_files_data)
        total_active_models = len(self.active_models)
        errors = [i for i in self.issues if i.severity == "ERROR"]
        warnings = [i for i in self.issues if i.severity == "WARNING"]
        infos = [i for i in self.issues if i.severity == "INFO"]

        lines.append(f"Repository Root: {Colors.OKCYAN}{self.repo_root}{Colors.ENDC}")
        lines.append(f"Active Models:   {Colors.BOLD}{total_active_models}{Colors.ENDC} across {total_files} active files")
        lines.append(
            f"Results:         "
            f"{Colors.FAIL}{len(errors)} Errors{Colors.ENDC}, "
            f"{Colors.WARNING}{len(warnings)} Warnings{Colors.ENDC}, "
            f"{Colors.OKBLUE}{len(infos)} Info{Colors.ENDC}"
        )
        lines.append("-----------------------------------------------------------------")

        if not self.issues:
            lines.append(f"\n{Colors.OKGREEN}{Colors.BOLD}✅ ALL CHECKS PASSED! All models and configurations are properly formatted.{Colors.ENDC}\n")
            return "\n".join(lines)

        # Group issues by severity
        for sev, title, color in [
            ("ERROR", "❌ ERRORS (Must Fix):", Colors.FAIL),
            ("WARNING", "⚠️  WARNINGS (Should Review):", Colors.WARNING),
            ("INFO", "ℹ️  INFO & NOTICES:", Colors.OKBLUE),
        ]:
            sev_issues = [i for i in self.issues if i.severity == sev]
            if not sev_issues:
                continue

            lines.append(f"\n{Colors.BOLD}{color}{title}{Colors.ENDC}")
            for idx, issue in enumerate(sev_issues, 1):
                file_str = f" [{Colors.DIM}{issue.file_path}{Colors.ENDC}]" if issue.file_path else ""
                lines.append(f"  {idx}. {color}[{issue.category}]{Colors.ENDC} {issue.message}{file_str}")
                if issue.suggestion:
                    indent_sugg = issue.suggestion.replace("\n", "\n       ")
                    lines.append(f"     {Colors.OKGREEN}↳ Suggestion:{Colors.ENDC} {indent_sugg}")

        # Final verdict
        lines.append("\n=================================================================")
        if errors:
            lines.append(f"{Colors.FAIL}{Colors.BOLD}STATUS: FAILED ({len(errors)} errors found){Colors.ENDC}")
        elif warnings and self.strict:
            lines.append(f"{Colors.WARNING}{Colors.BOLD}STATUS: FAILED STRICT CHECK ({len(warnings)} warnings found){Colors.ENDC}")
        else:
            lines.append(f"{Colors.OKGREEN}{Colors.BOLD}STATUS: SUCCESS (No blocking errors){Colors.ENDC}")
        lines.append("=================================================================\n")

        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        """Generates machine-readable dictionary."""
        errors = [i for i in self.issues if i.severity == "ERROR"]
        warnings = [i for i in self.issues if i.severity == "WARNING"]
        infos = [i for i in self.issues if i.severity == "INFO"]

        return {
            "status": "FAILED" if errors or (warnings and self.strict) else "PASSED",
            "summary": {
                "total_active_models": len(self.active_models),
                "total_model_files": len(self.model_files_data),
                "errors_count": len(errors),
                "warnings_count": len(warnings),
                "info_count": len(infos),
            },
            "issues": [i.to_dict() for i in self.issues],
            "active_models": [
                {
                    "model_name": m["model_name"],
                    "param_model": m["param_model"],
                    "environments": m["environments"],
                    "api_key_env": m["api_key_env"],
                    "file_path": os.path.relpath(m["file_path"], self.repo_root),
                }
                for m in self.active_models
            ],
        }


def main():
    parser = argparse.ArgumentParser(
        description="Verify LiteLLM models, secrets wiring, and Lago billing mappings."
    )
    parser.add_argument(
        "--repo-root",
        "-r",
        type=str,
        default=None,
        help="Path to repository root (auto-detected if omitted)",
    )
    parser.add_argument(
        "-json",
        "--json",
        action="store_true",
        help="Output results in JSON format (for automation / health-check)",
    )
    parser.add_argument(
        "--strict",
        "-s",
        action="store_true",
        help="Treat warnings as errors (fail if any warnings found)",
    )
    parser.add_argument(
        "--env",
        "-e",
        type=str,
        default=None,
        help="Filter checks for a specific environment (staging/prod)",
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="Disable ANSI color output",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Display verbose output",
    )

    args = parser.parse_args()

    if args.no_color or not sys.stdout.isatty():
        Colors.disable()

    checker = ModelCodeChecker(
        repo_root=args.repo_root,
        verbose=args.verbose,
        strict=args.strict,
    )

    success = checker.run_all_checks(target_env=args.env)

    if args.json:
        print(json.dumps(checker.to_dict(), indent=2))
    else:
        print(checker.format_cli_report())

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
