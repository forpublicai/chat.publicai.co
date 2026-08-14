#!/bin/bash

# Script to fetch Public AI partner models from Hugging Face API
# Endpoint: GET /api/partners/publicai/models?status=staging|live

# Exit immediately if a command exits with a non-zero status
set -e

# Base URL for Hugging Face API
BASE_URL="https://huggingface.co"
ENDPOINT="/api/partners/publicai/models"

# Default values
STATUS="staging|live"
TOKEN=""

# Parse options
while [[ "$#" -gt 0 ]]; do
    case $1 in
        -t|--token) TOKEN="$2"; shift ;;
        -s|--status) STATUS="$2"; shift ;;
        -h|--help)
            echo "Usage: $0 [options]"
            echo "Options:"
            echo "  -s, --status <status>   Status to filter by (default: 'staging|live', can be pipe-separated)"
            echo "  -t, --token <token>     Hugging Face API token (or set HF_TOKEN env var)"
            echo "  -h, --help              Show this help message"
            exit 0
            ;;
        *) echo "Unknown parameter: $1"; exit 1 ;;
    esac
    shift
done

# Fallback to HF_TOKEN or HF env var if token option is not set
if [ -z "$TOKEN" ]; then
    if [ -n "$HF_TOKEN" ]; then
        TOKEN="$HF_TOKEN"
    elif [ -n "$HF" ]; then
        TOKEN="$HF"
    fi
fi

# Fallback to HF token in the root .env file if still not set
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

# Build curl headers
HEADERS=()
if [ -n "$TOKEN" ]; then
    HEADERS+=(-H "Authorization: Bearer $TOKEN")
fi

# If status contains '|', split and query each status individually, then merge the JSON outputs
if [[ "$STATUS" == *"|"* ]]; then
    IFS='|' read -ra STATUS_LIST <<< "$STATUS"
    JSON_RESPONSES=()
    for s in "${STATUS_LIST[@]}"; do
        # Fetch individual status
        RESPONSE=$(curl -s "${HEADERS[@]}" "${BASE_URL}${ENDPOINT}?status=${s}")
        JSON_RESPONSES+=("$RESPONSE")
    done
    
    # Merge responses using jq
    # We pass all responses to jq and merge their fields
    jq -n '[ $ARGS.positional[] | fromjson ] | reduce .[] as $item ({}; . * $item)' --args "${JSON_RESPONSES[@]}"
else
    # Fetch single status
    curl -s "${HEADERS[@]}" "${BASE_URL}${ENDPOINT}?status=${STATUS}" | jq .
fi
