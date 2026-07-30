#!/bin/bash

# Script to update status of a model mapping item on Hugging Face API
# Endpoint: PUT /api/partners/publicai/models/{mapping_id}/status

# Exit immediately if a command exits with a non-zero status
set -e

# Base URL for Hugging Face API
BASE_URL="https://huggingface.co"
PROVIDER="publicai"

# Default values
MAPPING_ID=""
STATUS="live"
TOKEN=""

# Function to print usage
show_usage() {
    echo "Usage: $0 <mapping_id> [options]"
    echo "Options:"
    echo "  -i, --id <value>       Mapping ID (can also be passed as first positional argument)"
    echo "  -s, --status <value>   New status: 'live' or 'staging' (default: 'live')"
    echo "  --live | --prod        Set status to 'live'"
    echo "  --staging              Set status to 'staging'"
    echo "  --token <value>        Hugging Face API token (or set HF_TOKEN env var)"
    echo "  -h, --help             Show this help message"
}

# Parse positional argument first if it doesn't start with -
if [[ $# -gt 0 && ! "$1" =~ ^- ]]; then
    MAPPING_ID="$1"
    shift
fi

# Parse options
while [[ "$#" -gt 0 ]]; do
    case $1 in
        -i|--id) MAPPING_ID="$2"; shift ;;
        -s|--status) STATUS="$2"; shift ;;
        --live|--prod) STATUS="live" ;;
        --staging) STATUS="staging" ;;
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

# Check if jq is installed
if ! command -v jq &> /dev/null; then
    echo "Error: 'jq' is not installed. Please install it to format the JSON output." >&2
    exit 1
fi

# Validation
if [ -z "$MAPPING_ID" ]; then
    echo "Error: Missing required mapping ID." >&2
    show_usage
    exit 1
fi

if [ "$STATUS" != "live" ] && [ "$STATUS" != "staging" ]; then
    echo "Error: Status must be either 'live' or 'staging'." >&2
    exit 1
fi

# Build headers
HEADERS=(-H "Content-Type: application/json")
if [ -n "$TOKEN" ]; then
    HEADERS+=(-H "Authorization: Bearer $TOKEN")
else
    echo "Warning: No Hugging Face API token provided. The request might fail if authentication is required." >&2
fi

# Create JSON payload
PAYLOAD=$(jq -n --arg status "$STATUS" '{status: $status}')

echo "Updating model mapping status to '$STATUS' for ID '$MAPPING_ID'..."
curl -s -X PUT "${HEADERS[@]}" -d "$PAYLOAD" "${BASE_URL}/api/partners/${PROVIDER}/models/${MAPPING_ID}/status" | jq .
