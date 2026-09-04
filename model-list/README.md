# Model List Service & Cache API

A lightweight, Helm-compatible service that periodically queries the LiteLLM `/model/info` endpoint (default: every 10 minutes / 600s), filters out excluded models using pattern rules, strips internal team access IDs (`access_via_team_ids`), caches the model info data in memory, and serves it via an HTTP API.

This avoids hitting the upstream LiteLLM service on every client request and prevents hardcoding model configurations into downstream applications.

---

## Configuration Options

Configuration can be supplied via **Environment Variables**, a **Config File** (JSON or YAML, mounted via Kubernetes ConfigMap), or **Command Line Arguments**.

| Parameter | Environment Variable | Config File Key | Description | Default |
| :--- | :--- | :--- | :--- | :--- |
| Config File Path | `CONFIG_FILE` | N/A | Path to mounted YAML or JSON config file | `/etc/model-list/config.yaml` (if present) |
| LiteLLM Endpoint | `LITELLM_ENDPOINT` | `endpoint` | Base URL for LiteLLM service | `http://litellm-service.platform.svc.cluster.local:4000` |
| LiteLLM API Key | `LITELLM_API_KEY` | `api_key` | API key / Bearer token for LiteLLM | `""` |
| Exclude Filters | `EXCLUDE_MODELS` | `exclude_patterns` | Comma-separated or list of model substring patterns to exclude | `[]` (none excluded) |
| Poll Interval | `CHECK_INTERVAL_SECONDS` | `interval` | Seconds between LiteLLM background queries | `600` (10 minutes) |
| HTTP Port | `PORT` | `port` | HTTP API server port | `8000` |
| SSL Verification | `SSL_VERIFY` | `ssl_verify` | Enable or disable SSL certificate check (`true` / `false`) | `true` |

---

## Model Exclusion & Sanitization Logic

- **Exclusion Rules (`EXCLUDE_MODELS` / `exclude_patterns`)**:  
  Any model matching **any** of the configured substring patterns (case-insensitive) across `model_name`, `litellm_params.model`, `model_info.id`, or `model_info.key` will be filtered out.
- **Sanitization**:  
  Internal team access IDs (`access_via_team_ids`), internal endpoint URLs (`api_base`), and internal model IDs (`model_info.id`) are automatically removed before serving on the `/info` endpoint.

### Example Filter Setting:
- `EXCLUDE_MODELS="mock,test,rerank,cohere"`: Filters out all mock, test, rerank, or cohere models.

---

## Helm Chart Integration Guide

You can integrate this service into a Helm chart using **Option A (Environment Variables)** or **Option B (ConfigMap Mounting)**.

### Option A: Environment Variables in Helm (`values.yaml`)

#### `values.yaml`
```yaml
modelList:
  image:
    repository: ghcr.io/forpublicai/model-list
    tag: latest
  litellmEndpoint: "http://litellm-service.platform.svc.cluster.local:4000"
  secretName: "health-check-secrets" # Secret containing LITELLM_API_KEY
  checkIntervalSeconds: 600
  excludeModels: "mock,test,rerank"
```

#### `templates/model-list-deployment.yaml`
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: model-list
  namespace: {{ .Values.global.namespace | default "platform" }}
spec:
  replicas: 1
  selector:
    matchLabels:
      app: model-list
  template:
    metadata:
      labels:
        app: model-list
    spec:
      containers:
        - name: model-list
          image: "{{ .Values.modelList.image.repository }}:{{ .Values.modelList.image.tag }}"
          ports:
            - containerPort: 8000
              name: http
          env:
            - name: LITELLM_ENDPOINT
              value: {{ .Values.modelList.litellmEndpoint | quote }}
            - name: CHECK_INTERVAL_SECONDS
              value: {{ .Values.modelList.checkIntervalSeconds | quote }}
            - name: EXCLUDE_MODELS
              value: {{ .Values.modelList.excludeModels | quote }}
            - name: LITELLM_API_KEY
              valueFrom:
                secretKeyRef:
                  name: {{ .Values.modelList.secretName }}
                  key: LITELLM_API_KEY
```

---

### Option B: Mounted ConfigMap (`config.yaml`)

#### `templates/model-list-configmap.yaml`
```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: model-list-config
spec:
  config.yaml: |
    endpoint: "http://litellm-service.platform.svc.cluster.local:4000"
    interval: 600
    exclude_patterns:
      - "mock"
      - "test"
      - "rerank"
```

Mount the ConfigMap to `/etc/model-list/config.yaml` in the deployment container.

---

## API Endpoints

- **`GET /`** (and `/healthz`, `/health`)  
  Returns the service health, exclude rules, latency, and cached model list:
  ```json
  {
    "status": "healthy",
    "last_run_timestamp": "2026-09-04T12:00:00.000000+00:00",
    "last_run_latency_seconds": 0.231,
    "filtered_model_count": 10,
    "total_unfiltered_model_count": 13,
    "models": [
      "aisingapore/Gemma-SEA-LION-v4-27B-IT",
      "swiss-ai/apertus-70b-instruct"
    ],
    "last_error": null
  }
  ```

- **`GET /info`** (and `/model/info`)  
  Returns the cached LiteLLM `/model/info` JSON payload with excluded models filtered and sensitive fields (`access_via_team_ids`, `api_base`, `model_info.id`) stripped:
  ```json
  {
    "data": [
      {
        "model_name": "aisingapore/Gemma-SEA-LION-v4-27B-IT",
        "litellm_params": {
          "model": "openai/aisingapore/Gemma-SEA-LION-v4-27B-IT",
          "supports_vision": true
        },
        "model_info": {
          "input_cost_per_token": 2e-07,
          "output_cost_per_token": 4e-07,
          "direct_access": true
        }
      }
    ]
  }
  ```

- **`GET /docs`**  
  Interactive Swagger UI documentation generated automatically by FastAPI.

---

## Local Manual Testing

### Test model info filter locally:
```bash
python3 model-list/main.py \
  --url https://api-internal.ai-staging.chat \
  --key <YOUR_KEY> \
  --exclude "mock,test,rerank" \
  --port 8000
```

Query the filtered result:
```bash
curl http://localhost:8000/
curl http://localhost:8000/info
```
