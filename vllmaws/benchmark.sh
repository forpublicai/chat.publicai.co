#!/bin/bash

# Load environment variables from .env file if it exists
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -f "$SCRIPT_DIR/.env" ]; then
  set -a
  source "$SCRIPT_DIR/.env"
  set +a
fi

NUM_REQUESTS=${1:-30}
CONCURRENT=${2:-5}

echo "╔════════════════════════════════════════╗"
echo "║   vLLM Deployment Benchmark            ║"
echo "╚════════════════════════════════════════╝"
echo ""
echo "Configuration:"
echo "  Total requests: $NUM_REQUESTS"
echo "  Concurrent requests: $CONCURRENT"
echo "  Model: swiss-ai/Apertus-8B-Instruct-2509"
echo ""

# Check if VLLM_API_KEY is set
if [ -z "$VLLM_API_KEY" ]; then
  echo "⚠️  WARNING: VLLM_API_KEY environment variable is not set"
  echo "  If your server requires authentication, the requests will fail."
  echo ""
fi

# Determine if we should use HTTP or HTTPS
BASE_URL="http://localhost"
echo "Testing connectivity..."
test_response=$(curl -s -o /dev/null -w "%{http_code}" http://localhost/v1/models)
if [ "$test_response" = "301" ] || [ "$test_response" = "302" ]; then
  echo "Detected redirect, using HTTPS..."
  BASE_URL="https://localhost"
  test_response=$(curl -s -k -o /dev/null -w "%{http_code}" https://localhost/v1/models)
fi

if [ "$test_response" != "200" ] && [ "$test_response" != "401" ]; then
  echo "⚠️  WARNING: Server may not be reachable (HTTP $test_response)"
  echo "  Make sure your vLLM server is running"
  echo ""
fi
echo "Using endpoint: ${BASE_URL}/v1"
echo ""

# Create temp directory for results
TMPDIR=$(mktemp -d)

# Run benchmark
echo "Starting benchmark..."
start=$(date +%s.%N)

for batch in $(seq 0 $((($NUM_REQUESTS - 1) / $CONCURRENT))); do
  for i in $(seq 1 $CONCURRENT); do
    req_num=$((batch * CONCURRENT + i))
    if [ $req_num -le $NUM_REQUESTS ]; then
      (
        req_start=$(date +%s.%N)
        response=$(curl -s -k -X POST ${BASE_URL}/v1/completions \
          -H "Content-Type: application/json" \
          -H "Authorization: Bearer ${VLLM_API_KEY}" \
          -d '{"model":"swiss-ai/Apertus-8B-Instruct-2509","prompt":"Explain machine learning briefly.","max_tokens":50}')
        req_end=$(date +%s.%N)

        latency=$(echo "$req_end - $req_start" | bc)

        if echo "$response" | grep -q '"choices"'; then
          tokens=$(echo "$response" | grep -o '"completion_tokens":[0-9]*' | grep -o '[0-9]*')
          [ -z "$tokens" ] && tokens=0
          echo "SUCCESS:$latency:$tokens" >> "$TMPDIR/results.txt"
        else
          echo "FAILED:$latency:0" >> "$TMPDIR/results.txt"
          # Save first failure for debugging
          if [ ! -f "$TMPDIR/first_error.txt" ]; then
            echo "$response" > "$TMPDIR/first_error.txt"
          fi
        fi
      ) &
    fi
  done
  wait
done

end=$(date +%s.%N)

# Calculate statistics
total_time=$(echo "$end - $start" | bc)
success_count=$(grep -c "^SUCCESS" "$TMPDIR/results.txt" 2>/dev/null || echo 0)
failed_count=$(grep -c "^FAILED" "$TMPDIR/results.txt" 2>/dev/null || echo 0)

echo ""
echo "╔════════════════════════════════════════╗"
echo "║         Benchmark Results              ║"
echo "╚════════════════════════════════════════╝"
echo ""
echo "Requests:"
echo "  ✓ Successful: $success_count"
echo "  ✗ Failed: $failed_count"
echo ""
echo "Performance:"
echo "  Total time: $(printf '%.2f' $total_time) seconds"

if [ "$success_count" -gt 0 ]; then
  throughput=$(echo "scale=2; $success_count / $total_time" | bc)
  echo "  Throughput: $throughput req/s"

  avg_latency=$(grep "^SUCCESS" "$TMPDIR/results.txt" | cut -d: -f2 | awk '{sum+=$1; count+=1} END {print sum/count}')
  total_tokens=$(grep "^SUCCESS" "$TMPDIR/results.txt" | cut -d: -f3 | awk '{sum+=$1} END {print sum}')
  tokens_per_sec=$(echo "scale=2; $total_tokens / $total_time" | bc)

  echo "  Avg latency: $(printf '%.2f' $avg_latency) seconds"
  echo "  Total tokens: $total_tokens"
  echo "  Token throughput: $tokens_per_sec tokens/s"
else
  echo "  Throughput: 0 req/s"
  echo ""
  echo "❌ All requests failed!"

  if [ -f "$TMPDIR/first_error.txt" ]; then
    echo ""
    echo "First error response:"
    echo "────────────────────────────────────────"
    cat "$TMPDIR/first_error.txt"
    echo "────────────────────────────────────────"
  fi
fi

echo ""

# Cleanup
rm -rf "$TMPDIR"
