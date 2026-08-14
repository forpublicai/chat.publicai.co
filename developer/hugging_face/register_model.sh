#!/bin/bash

# Script to register a model mapping item with the Hugging Face API
# Endpoint: POST /api/partners/publicai/models

# Exit immediately if a command exits with a non-zero status
set -e

# Base URL for Hugging Face API
BASE_URL="https://huggingface.co"
ENDPOINT="/api/partners/publicai/models"

# Allowed tasks (WidgetType)
VALID_TASKS=(
    "text-generation"
    "conversational"
    "image-text-to-text"
    "feature-extraction"
    "text-classification"
    "token-classification"
    "question-answering"
    "fill-mask"
    "summarization"
    "translation"
    "text2text-generation"
    "text-to-image"
    "image-classification"
    "object-detection"
    "image-segmentation"
    "image-to-image"
    "automatic-speech-recognition"
    "text-to-speech"
    "audio-classification"
    "audio-to-audio"
    "zero-shot-classification"
    "zero-shot-image-classification"
    "visual-question-answering"
    "document-question-answering"
    "depth-estimation"
    "video-classification"
    "text-to-video"
)

# Default values
TASK=""
HF_MODEL=""
PROVIDER_MODEL=""
STATUS="staging"
TOKEN=""

# Function to print usage
show_usage() {
    echo "Usage: $0 [options]"
    echo "Options:"
    echo "  -t, --task <value>             Required: Task/widget type (e.g. text-generation)"
    echo "  -m, --hf-model <value>         Required: Hugging Face model path (namespace/model-name)"
    echo "  -p, --provider-model <value>   Required: Partner model ID on your side"
    echo "  --live | --prod                Set status to 'live' (default is 'staging')"
    echo "  --token <value>                Hugging Face API token (or set HF_TOKEN env var)"
    echo "  -h, --help                     Show this help message"
}

# Parse options
while [[ "$#" -gt 0 ]]; do
    case $1 in
        -t|--task) TASK="$2"; shift ;;
        -m|--hf-model) HF_MODEL="$2"; shift ;;
        -p|--provider-model) PROVIDER_MODEL="$2"; shift ;;
        --live|--prod) STATUS="live" ;;
        --token) TOKEN="$2"; shift ;;
        -h|--help)
            show_usage
            exit 0
            ;;
        *) echo "Unknown parameter: $1"; show_usage; exit 1 ;;
    esac
    shift
done

# Fallback to HF_TOKEN env var if token option is not set
if [ -z "$TOKEN" ] && [ -n "$HF_TOKEN" ]; then
    TOKEN="$HF_TOKEN"
fi

# Fallback to token in the root .env file if still not set
if [ -z "$TOKEN" ]; then
    SCRIPT_DIR="$(dirname "${BASH_SOURCE[0]}")"
    ROOT_ENV="$SCRIPT_DIR/../../.env"
    if [ -f "$ROOT_ENV" ]; then
        ENV_TOKEN=$(grep -E '^(HF_TOKEN|HF|HF_TEST_TOKEN)=' "$ROOT_ENV" | cut -d= -f2- | tr -d '"'\' | tr -d '\r')
        if [ -n "$ENV_TOKEN" ]; then
            TOKEN="$ENV_TOKEN"
        fi
    fi
fi

# Check if jq is installed
if ! command -v jq &> /dev/null; then
    echo "Error: 'jq' is not installed. Please install it to format the JSON output." >&2
    exit 1
fi

# Validation
MISSING_ARGS=()
if [ -z "$TASK" ]; then MISSING_ARGS+=("task (-t/--task)"); fi
if [ -z "$HF_MODEL" ]; then MISSING_ARGS+=("hf-model (-m/--hf-model)"); fi
if [ -z "$PROVIDER_MODEL" ]; then MISSING_ARGS+=("provider-model (-p/--provider-model)"); fi

if [ ${#MISSING_ARGS[@]} -ne 0 ]; then
    echo "Error: Missing required argument(s): ${MISSING_ARGS[*]}" >&2
    show_usage
    exit 1
fi

# Validate task value
VALID=false
for valid in "${VALID_TASKS[@]}"; do
    if [ "$TASK" = "$valid" ]; then
        VALID=true
        break
    fi
done

if [ "$VALID" = false ]; then
    echo "Error: Invalid task value '$TASK'." >&2
    echo "It must be one of these values:" >&2
    for valid in "${VALID_TASKS[@]}"; do
        echo "  - $valid" >&2
    done
    exit 1
fi

# Build headers
HEADERS=(-H "Content-Type: application/json")
if [ -n "$TOKEN" ]; then
    HEADERS+=(-H "Authorization: Bearer $TOKEN")
else
    echo "Warning: No Hugging Face API token provided. The request might fail if authentication is required." >&2
fi

# Create JSON payload using jq to ensure correct escaping
PAYLOAD=$(jq -n \
  --arg task "$TASK" \
  --arg hfModel "$HF_MODEL" \
  --arg providerModel "$PROVIDER_MODEL" \
  --arg status "$STATUS" \
  '{task: $task, hfModel: $hfModel, providerModel: $providerModel, status: $status}')

echo "Registering model mapping item with Hugging Face..."
curl -s -X POST "${HEADERS[@]}" -d "$PAYLOAD" "${BASE_URL}${ENDPOINT}" | jq .
