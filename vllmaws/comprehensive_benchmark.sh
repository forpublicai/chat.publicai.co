#!/bin/bash

# Comprehensive LLM Deployment Benchmark v4
# Multi-model support with nginx routing
# Runtime: ~3-5 minutes per model

set -e

# Load environment variables from .env file if it exists
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -f "$SCRIPT_DIR/.env" ]; then
  set -a
  source "$SCRIPT_DIR/.env"
  set +a
fi

# Model selection
MODEL_CHOICE="${1:-apertus}"

case "$MODEL_CHOICE" in
  apertus)
    MODEL_NAME="swiss-ai/Apertus-8B-Instruct-2509"
    MODEL_PATH="/apertus"
    MODEL_DISPLAY="Apertus-8B"
    ;;
  olmo)
    MODEL_NAME="allenai/Olmo-3-7B-Instruct"
    MODEL_PATH="/olmo"
    MODEL_DISPLAY="Olmo-3-7B"
    ;;
  eurollm)
    MODEL_NAME="utter-project/EuroLLM-22B-Instruct-2512"
    MODEL_PATH="/eurollm"
    MODEL_DISPLAY="EuroLLM-22B"
    ;;
  *)
    echo "Usage: $0 [apertus|olmo|eurollm]"
    echo ""
    echo "Available models:"
    echo "  apertus  - swiss-ai/Apertus-8B-Instruct-2509"
    echo "  olmo     - allenai/Olmo-3-7B-Instruct"
    echo "  eurollm  - utter-project/EuroLLM-22B-Instruct-2512"
    exit 1
    ;;
esac

# Configuration
TMPDIR=$(mktemp -d)

echo "╔════════════════════════════════════════════════════╗"
echo "║   Comprehensive LLM Deployment Benchmark v4        ║"
echo "║   Multi-model nginx routing support                ║"
echo "╚════════════════════════════════════════════════════╝"
echo ""
echo "Testing model: $MODEL_DISPLAY"
echo "Model path: $MODEL_PATH"
echo ""

# Determine if we should use HTTP or HTTPS
BASE_URL="http://localhost"
echo "[1/7] Testing connectivity..."
test_response=$(curl -s -o /dev/null -w "%{http_code}" http://localhost${MODEL_PATH}/v1/models 2>/dev/null || echo "000")
if [ "$test_response" = "301" ] || [ "$test_response" = "302" ]; then
  BASE_URL="https://localhost"
  test_response=$(curl -s -k -o /dev/null -w "%{http_code}" https://localhost${MODEL_PATH}/v1/models 2>/dev/null || echo "000")
fi

if [ "$test_response" != "200" ] && [ "$test_response" != "401" ]; then
  echo "❌ ERROR: Server not reachable (HTTP $test_response)"
  echo "   Make sure your vLLM server is running and nginx is configured"
  echo "   Testing path: ${BASE_URL}${MODEL_PATH}/v1/models"
  rm -rf "$TMPDIR"
  exit 1
fi
echo "   ✓ Server reachable at ${BASE_URL}${MODEL_PATH}/v1"
echo ""

# Helper function to make requests and measure timing
make_request() {
  local prompt="$1"
  local max_tokens="$2"
  local output_file="$3"

  local start_time=$(date +%s.%N)

  response=$(curl -s -k -X POST "${BASE_URL}${MODEL_PATH}/v1/completions" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer ${VLLM_API_KEY}" \
    -d "{\"model\":\"${MODEL_NAME}\",\"prompt\":\"${prompt}\",\"max_tokens\":${max_tokens}}" \
    2>/dev/null)

  local end_time=$(date +%s.%N)
  local total_time=$(echo "$end_time - $start_time" | bc -l)

  # Extract metrics from response
  local completion_tokens=$(echo "$response" | grep -o '"completion_tokens":[0-9]*' | grep -o '[0-9]*' | head -1)
  local prompt_tokens=$(echo "$response" | grep -o '"prompt_tokens":[0-9]*' | grep -o '[0-9]*' | head -1)

  # Set defaults if empty
  completion_tokens=${completion_tokens:-0}
  prompt_tokens=${prompt_tokens:-0}

  # Estimate TTFT and TPOT
  local ttft=$(echo "$total_time * 0.25" | bc -l)
  local decode_time=$(echo "$total_time - $ttft" | bc -l)
  local tpot=0

  if [ "$completion_tokens" -gt 0 ]; then
    tpot=$(echo "scale=4; $decode_time / $completion_tokens" | bc -l)
  fi

  # Check if request succeeded
  if echo "$response" | grep -q '"choices"'; then
    echo "SUCCESS:$total_time:$ttft:$tpot:$prompt_tokens:$completion_tokens" >> "$output_file"
  else
    echo "FAILED:$total_time:0:0:0:0" >> "$output_file"
  fi
}

# Test 1: Sequential baseline (for per-request metrics)
echo "[2/7] Sequential baseline (5 requests, one at a time)..."
for i in {1..5}; do
  make_request "What is machine learning?" 50 "$TMPDIR/sequential.txt"
done
echo "   ✓ Sequential test complete"
echo ""

# Test 2: Variable input lengths
echo "[3/7] Testing variable input lengths (9 requests)..."
for i in {1..3}; do
  make_request "Hi" 30 "$TMPDIR/short_input.txt" &
done
wait
for i in {1..3}; do
  make_request "Explain the concept of artificial intelligence and its impact on modern society in detail." 50 "$TMPDIR/medium_input.txt" &
done
wait
for i in {1..3}; do
  make_request "Provide a comprehensive analysis of machine learning algorithms, including supervised learning techniques like linear regression and decision trees, unsupervised learning methods such as clustering and dimensionality reduction, and reinforcement learning approaches. Discuss their applications in real-world scenarios." 50 "$TMPDIR/long_input.txt" &
done
wait
echo "   ✓ Variable input test complete"
echo ""

# Test 3: Variable output lengths
echo "[4/7] Testing variable output lengths (9 requests)..."
for i in {1..3}; do
  make_request "Say hello" 10 "$TMPDIR/short_output.txt" &
done
wait
for i in {1..3}; do
  make_request "Explain quantum computing" 100 "$TMPDIR/medium_output.txt" &
done
wait
for i in {1..3}; do
  make_request "Write a detailed essay about climate change" 200 "$TMPDIR/long_output.txt" &
done
wait
echo "   ✓ Variable output test complete"
echo ""

# Test 4: Concurrent load (WALL CLOCK TIME)
echo "[5/7] Testing concurrent throughput (wall-clock timing)..."

# 2 concurrent
start_2=$(date +%s.%N)
for i in {1..2}; do
  make_request "Test query $i" 50 "$TMPDIR/concurrent_2.txt" &
done
wait
end_2=$(date +%s.%N)
duration_2=$(echo "$end_2 - $start_2" | bc -l)

# 5 concurrent
start_5=$(date +%s.%N)
for i in {1..5}; do
  make_request "Test query $i" 50 "$TMPDIR/concurrent_5.txt" &
done
wait
end_5=$(date +%s.%N)
duration_5=$(echo "$end_5 - $start_5" | bc -l)

# 10 concurrent
start_10=$(date +%s.%N)
for i in {1..10}; do
  make_request "Test query $i" 50 "$TMPDIR/concurrent_10.txt" &
done
wait
end_10=$(date +%s.%N)
duration_10=$(echo "$end_10 - $start_10" | bc -l)

# 20 concurrent
start_20=$(date +%s.%N)
for i in {1..20}; do
  make_request "Test query $i" 50 "$TMPDIR/concurrent_20.txt" &
done
wait
end_20=$(date +%s.%N)
duration_20=$(echo "$end_20 - $start_20" | bc -l)

# 30 concurrent
start_30=$(date +%s.%N)
for i in {1..30}; do
  make_request "Test query $i" 50 "$TMPDIR/concurrent_30.txt" &
done
wait
end_30=$(date +%s.%N)
duration_30=$(echo "$end_30 - $start_30" | bc -l)

# 40 concurrent
start_40=$(date +%s.%N)
for i in {1..40}; do
  make_request "Test query $i" 50 "$TMPDIR/concurrent_40.txt" &
done
wait
end_40=$(date +%s.%N)
duration_40=$(echo "$end_40 - $start_40" | bc -l)

# 60 concurrent (heavy load)
start_60=$(date +%s.%N)
for i in {1..60}; do
  make_request "Test query $i" 50 "$TMPDIR/concurrent_60.txt" &
done
wait
end_60=$(date +%s.%N)
duration_60=$(echo "$end_60 - $start_60" | bc -l)

# 80 concurrent (heavy load)
start_80=$(date +%s.%N)
for i in {1..80}; do
  make_request "Test query $i" 50 "$TMPDIR/concurrent_80.txt" &
done
wait
end_80=$(date +%s.%N)
duration_80=$(echo "$end_80 - $start_80" | bc -l)

# 100 concurrent (heavy load)
start_100=$(date +%s.%N)
for i in {1..100}; do
  make_request "Test query $i" 50 "$TMPDIR/concurrent_100.txt" &
done
wait
end_100=$(date +%s.%N)
duration_100=$(echo "$end_100 - $start_100" | bc -l)

# 120 concurrent (maximum stress test)
start_120=$(date +%s.%N)
for i in {1..120}; do
  make_request "Test query $i" 50 "$TMPDIR/concurrent_120.txt" &
done
wait
end_120=$(date +%s.%N)
duration_120=$(echo "$end_120 - $start_120" | bc -l)

echo "   ✓ Concurrent load test complete"
echo ""

# Test 5: Sustained load
echo "[6/7] Testing sustained throughput (30 requests over time)..."
start_sustained=$(date +%s)
for i in {1..30}; do
  make_request "Query $i" 50 "$TMPDIR/sustained.txt" &
  sleep 0.3  # Realistic request rate
done
wait
end_sustained=$(date +%s)
sustained_duration=$((end_sustained - start_sustained))
echo "   ✓ Sustained load test complete"
echo ""

# Test 6: Maximum burst throughput
echo "[7/7] Testing maximum burst throughput (30 requests, all at once)..."
start_burst=$(date +%s.%N)
for i in {1..30}; do
  make_request "Burst test $i" 50 "$TMPDIR/burst.txt" &
done
wait
end_burst=$(date +%s.%N)
burst_duration=$(echo "$end_burst - $start_burst" | bc -l)
echo "   ✓ Burst test complete"
echo ""

# Calculate statistics
echo "╔════════════════════════════════════════════════════╗"
echo "║                  BENCHMARK RESULTS                 ║"
echo "╚════════════════════════════════════════════════════╝"
echo ""

# Function to calculate percentiles
calculate_percentile() {
  local values="$1"
  local percentile="$2"

  local count=$(echo "$values" | wc -l | tr -d ' ')
  if [ "$count" -eq 0 ]; then
    echo "0"
    return
  fi

  local idx=$(echo "($count * $percentile / 100)" | bc)
  [ "$idx" -lt 1 ] && idx=1

  echo "$values" | sed -n "${idx}p"
}

# Overall success rate
total_requests=$(cat "$TMPDIR"/*.txt 2>/dev/null | wc -l | tr -d ' ')
successful_requests=$(grep -h "^SUCCESS" "$TMPDIR"/*.txt 2>/dev/null | wc -l | tr -d ' ')
failed_requests=$(grep -h "^FAILED" "$TMPDIR"/*.txt 2>/dev/null | wc -l | tr -d ' ')

echo "═══════════════════════════════════════════════════"
echo "1. OVERALL PERFORMANCE"
echo "═══════════════════════════════════════════════════"
echo "Total Requests:     $total_requests"
if [ "$total_requests" -gt 0 ]; then
  success_pct=$(echo "scale=1; $successful_requests * 100 / $total_requests" | bc -l)
  echo "Successful:         $successful_requests (${success_pct}%)"
else
  echo "Successful:         $successful_requests"
fi
echo "Failed:             $failed_requests"
echo ""

# Sequential performance (true per-request metrics)
echo "═══════════════════════════════════════════════════"
echo "2. SINGLE-REQUEST PERFORMANCE (Sequential Test)"
echo "═══════════════════════════════════════════════════"

if [ -f "$TMPDIR/sequential.txt" ]; then
  seq_latencies=$(grep "^SUCCESS" "$TMPDIR/sequential.txt" | cut -d: -f2 | sort -n)
  seq_ttft=$(grep "^SUCCESS" "$TMPDIR/sequential.txt" | cut -d: -f3 | sort -n)
  seq_tpot=$(grep "^SUCCESS" "$TMPDIR/sequential.txt" | cut -d: -f4 | grep -v "^0$\|^0\.0*$" | sort -n)
  seq_tokens=$(grep "^SUCCESS" "$TMPDIR/sequential.txt" | cut -d: -f6)

  avg_latency=$(echo "$seq_latencies" | awk '{sum+=$1; count+=1} END {if(count>0) printf "%.2f", sum/count; else print "0.00"}')
  avg_ttft=$(echo "$seq_ttft" | awk '{sum+=$1; count+=1} END {if(count>0) printf "%.2f", sum/count; else print "0.00"}')
  avg_tpot=$(echo "$seq_tpot" | awk '{sum+=$1; count+=1} END {if(count>0) printf "%.4f", sum/count; else print "0.0000"}')
  avg_tokens=$(echo "$seq_tokens" | awk '{sum+=$1; count+=1} END {if(count>0) printf "%.0f", sum/count; else print "0"}')

  per_request_tok_s=$(echo "scale=2; 1 / $avg_tpot" | bc -l)

  echo "Avg End-to-End:     ${avg_latency}s"
  echo "Avg TTFT:           ${avg_ttft}s"
  echo "Avg TPOT:           ${avg_tpot}s ($(echo "$avg_tpot * 1000" | bc -l | awk '{printf "%.0f", $1}')ms)"
  echo "Avg tokens/request: ${avg_tokens}"
  echo "Per-request speed:  ${per_request_tok_s} tokens/s (streaming)"
  echo ""
  echo "Interpretation: A single user sees tokens appear at"
  echo "                ${per_request_tok_s} tokens/second"
fi
echo ""

# Concurrent throughput (REAL system throughput)
echo "═══════════════════════════════════════════════════"
echo "3. CONCURRENT THROUGHPUT (System Capacity)"
echo "═══════════════════════════════════════════════════"

calc_throughput() {
  local file="$1"
  local duration="$2"
  local num_requests="$3"

  if [ -f "$file" ]; then
    local success=$(grep -c "^SUCCESS" "$file" 2>/dev/null || echo 0)
    local total_tokens=$(grep "^SUCCESS" "$file" | cut -d: -f6 | awk '{sum+=$1} END {print sum}')
    local avg_latency=$(grep "^SUCCESS" "$file" | cut -d: -f2 | awk '{sum+=$1; count+=1} END {if(count>0) printf "%.2f", sum/count; else print "0.00"}')

    local req_per_sec=$(echo "scale=2; $success / $duration" | bc -l)
    local tok_per_sec=$(echo "scale=2; $total_tokens / $duration" | bc -l)

    printf "%2d concurrent: %7.2f tokens/s | %5.2f req/s | %5.2fs avg latency\n" \
      "$num_requests" "$tok_per_sec" "$req_per_sec" "$avg_latency"
  fi
}

calc_throughput "$TMPDIR/concurrent_2.txt" "$duration_2" 2
calc_throughput "$TMPDIR/concurrent_5.txt" "$duration_5" 5
calc_throughput "$TMPDIR/concurrent_10.txt" "$duration_10" 10
calc_throughput "$TMPDIR/concurrent_20.txt" "$duration_20" 20
calc_throughput "$TMPDIR/concurrent_30.txt" "$duration_30" 30
calc_throughput "$TMPDIR/concurrent_40.txt" "$duration_40" 40

echo ""
echo "Heavy Load Tests:"
calc_throughput "$TMPDIR/concurrent_60.txt" "$duration_60" 60
calc_throughput "$TMPDIR/concurrent_80.txt" "$duration_80" 80
calc_throughput "$TMPDIR/concurrent_100.txt" "$duration_100" 100
calc_throughput "$TMPDIR/concurrent_120.txt" "$duration_120" 120

echo ""
echo "Interpretation: With N users, the system produces X tokens/second"
echo "                total across all users simultaneously."
echo ""

# Maximum burst throughput
echo "═══════════════════════════════════════════════════"
echo "4. MAXIMUM BURST CAPACITY"
echo "═══════════════════════════════════════════════════"

if [ -f "$TMPDIR/burst.txt" ]; then
  burst_success=$(grep -c "^SUCCESS" "$TMPDIR/burst.txt" 2>/dev/null || echo 0)
  burst_tokens=$(grep "^SUCCESS" "$TMPDIR/burst.txt" | cut -d: -f6 | awk '{sum+=$1} END {print sum}')
  burst_tok_per_sec=$(echo "scale=2; $burst_tokens / $burst_duration" | bc -l)
  burst_req_per_sec=$(echo "scale=2; $burst_success / $burst_duration" | bc -l)

  printf "30 requests sent simultaneously:\n"
  printf "  Completed in:     %.2fs\n" "$burst_duration"
  printf "  Total tokens:     %d\n" "$burst_tokens"
  printf "  Throughput:       %.2f tokens/s\n" "$burst_tok_per_sec"
  printf "  Request rate:     %.2f req/s\n" "$burst_req_per_sec"

  echo ""
  echo "Interpretation: Maximum throughput when system is fully loaded"
fi
echo ""

# Sustained load
echo "═══════════════════════════════════════════════════"
echo "5. SUSTAINED LOAD (Realistic Traffic)"
echo "═══════════════════════════════════════════════════"

sustained_success=$(grep -c "^SUCCESS" "$TMPDIR/sustained.txt" 2>/dev/null || echo 0)
sustained_tokens=$(grep "^SUCCESS" "$TMPDIR/sustained.txt" | cut -d: -f6 | awk '{sum+=$1} END {print sum}')

if [ "$sustained_duration" -gt 0 ]; then
  sustained_throughput=$(echo "scale=2; $sustained_success / $sustained_duration" | bc -l)
  sustained_tok_per_sec=$(echo "scale=2; $sustained_tokens / $sustained_duration" | bc -l)

  printf "30 requests over %ds (0.3s between requests):\n" "$sustained_duration"
  printf "  Throughput:       %.2f tokens/s\n" "$sustained_tok_per_sec"
  printf "  Request rate:     %.2f req/s\n" "$sustained_throughput"
fi
echo ""

# Latency percentiles (all requests)
echo "═══════════════════════════════════════════════════"
echo "6. LATENCY DISTRIBUTION (All Requests)"
echo "═══════════════════════════════════════════════════"

if [ "$successful_requests" -gt 0 ]; then
  all_latencies=$(grep -h "^SUCCESS" "$TMPDIR"/*.txt 2>/dev/null | cut -d: -f2 | sort -n)

  mean=$(echo "$all_latencies" | awk '{sum+=$1; count+=1} END {if(count>0) printf "%.2f", sum/count; else print "0.00"}')
  p50=$(calculate_percentile "$all_latencies" 50)
  p90=$(calculate_percentile "$all_latencies" 90)
  p95=$(calculate_percentile "$all_latencies" 95)
  p99=$(calculate_percentile "$all_latencies" 99)

  printf "Mean:               %.2f s\n" $mean
  printf "P50 (median):       %.2f s\n" $p50
  printf "P90:                %.2f s\n" $p90
  printf "P95:                %.2f s\n" $p95
  printf "P99:                %.2f s\n" $p99
else
  echo "No successful requests"
fi
echo ""

# TTFT percentiles
echo "═══════════════════════════════════════════════════"
echo "7. TIME TO FIRST TOKEN - TTFT (estimated)"
echo "═══════════════════════════════════════════════════"

if [ "$successful_requests" -gt 0 ]; then
  all_ttft=$(grep -h "^SUCCESS" "$TMPDIR"/*.txt 2>/dev/null | cut -d: -f3 | sort -n)

  mean=$(echo "$all_ttft" | awk '{sum+=$1; count+=1} END {if(count>0) printf "%.2f", sum/count; else print "0.00"}')
  p50=$(calculate_percentile "$all_ttft" 50)
  p95=$(calculate_percentile "$all_ttft" 95)

  printf "Mean:               %.2f s\n" $mean
  printf "P50 (median):       %.2f s\n" $p50
  printf "P95:                %.2f s " $p95
  if (( $(echo "$p95 <= 0.5" | bc -l) )); then
    echo "✓ (target: ≤0.5s interactive)"
  else
    echo "⚠ (target: ≤0.5s interactive, ≤6s batch)"
  fi

  echo ""
  echo "Interpretation: Time before user sees first word"
else
  echo "No successful requests"
fi
echo ""

# TPOT percentiles
echo "═══════════════════════════════════════════════════"
echo "8. TIME PER OUTPUT TOKEN - TPOT (estimated)"
echo "═══════════════════════════════════════════════════"

if [ "$successful_requests" -gt 0 ]; then
  all_tpot=$(grep -h "^SUCCESS" "$TMPDIR"/*.txt 2>/dev/null | cut -d: -f4 | grep -v "^0$\|^0\.0*$" | sort -n)

  if [ ! -z "$all_tpot" ]; then
    mean=$(echo "$all_tpot" | awk '{sum+=$1; count+=1} END {if(count>0) printf "%.4f", sum/count; else print "0.0000"}')
    p50=$(calculate_percentile "$all_tpot" 50)
    p95=$(calculate_percentile "$all_tpot" 95)

    mean_ms=$(echo "$mean * 1000" | bc -l | awk '{printf "%.0f", $1}')
    p50_ms=$(echo "$p50 * 1000" | bc -l | awk '{printf "%.0f", $1}')
    p95_ms=$(echo "$p95 * 1000" | bc -l | awk '{printf "%.0f", $1}')

    printf "Mean:               %.4f s (%s ms)\n" $mean $mean_ms
    printf "P50 (median):       %.4f s (%s ms)\n" $p50 $p50_ms
    printf "P95:                %.4f s (%s ms) " $p95 $p95_ms
    if (( $(echo "$p95 <= 0.03" | bc -l) )); then
      echo "✓ (target: ≤30ms interactive)"
    else
      echo "⚠ (target: ≤30ms interactive, ≤175ms batch)"
    fi

    echo ""
    echo "Interpretation: Time between each token during streaming"
  else
    echo "No TPOT data available"
  fi
else
  echo "No successful requests"
fi
echo ""

# Variable length analysis
echo "═══════════════════════════════════════════════════"
echo "9. VARIABLE LENGTH IMPACT"
echo "═══════════════════════════════════════════════════"

echo "Input Length Impact:"
for type in short medium long; do
  file="$TMPDIR/${type}_input.txt"
  if [ -f "$file" ] && [ -s "$file" ]; then
    avg=$(grep "^SUCCESS" "$file" 2>/dev/null | cut -d: -f2 | awk '{sum+=$1; count+=1} END {if(count>0) printf "%.2f", sum/count; else print "N/A"}')
    echo "  ${type^} input:       ${avg}s avg"
  fi
done

echo ""
echo "Output Length Impact:"
for type in short medium long; do
  file="$TMPDIR/${type}_output.txt"
  if [ -f "$file" ] && [ -s "$file" ]; then
    avg=$(grep "^SUCCESS" "$file" 2>/dev/null | cut -d: -f2 | awk '{sum+=$1; count+=1} END {if(count>0) printf "%.2f", sum/count; else print "N/A"}')
    tokens=$(grep "^SUCCESS" "$file" 2>/dev/null | cut -d: -f6 | awk '{sum+=$1; count+=1} END {if(count>0) printf "%.0f", sum/count; else print "N/A"}')
    echo "  ${type^} output (~${tokens} tokens): ${avg}s avg"
  fi
done
echo ""

echo "═══════════════════════════════════════════════════"
echo "SUMMARY & RECOMMENDATIONS"
echo "═══════════════════════════════════════════════════"
echo ""
echo "Model tested: $MODEL_DISPLAY ($MODEL_NAME)"
echo ""

# Calculate best concurrent throughput
best_concurrent_throughput=0
best_concurrent_level=0

for level in 2 5 10 20 30 40 60 80 100 120; do
  file="$TMPDIR/concurrent_${level}.txt"
  if [ "$level" -eq 2 ]; then duration="$duration_2"
  elif [ "$level" -eq 5 ]; then duration="$duration_5"
  elif [ "$level" -eq 10 ]; then duration="$duration_10"
  elif [ "$level" -eq 20 ]; then duration="$duration_20"
  elif [ "$level" -eq 30 ]; then duration="$duration_30"
  elif [ "$level" -eq 40 ]; then duration="$duration_40"
  elif [ "$level" -eq 60 ]; then duration="$duration_60"
  elif [ "$level" -eq 80 ]; then duration="$duration_80"
  elif [ "$level" -eq 100 ]; then duration="$duration_100"
  elif [ "$level" -eq 120 ]; then duration="$duration_120"
  fi

  if [ -f "$file" ]; then
    tokens=$(grep "^SUCCESS" "$file" | cut -d: -f6 | awk '{sum+=$1} END {print sum}')
    throughput=$(echo "scale=2; $tokens / $duration" | bc -l)

    if (( $(echo "$throughput > $best_concurrent_throughput" | bc -l) )); then
      best_concurrent_throughput=$throughput
      best_concurrent_level=$level
    fi
  fi
done

if [ "$successful_requests" -gt 0 ] && [ -f "$TMPDIR/sequential.txt" ]; then
  per_req=$(echo "scale=2; 1 / $avg_tpot" | bc -l)

  echo "✓ Deployment Status: HEALTHY ($successful_requests/$total_requests successful)"
  echo ""
  echo "Key Metrics:"
  printf "  • Single-user experience:  %.1f tokens/s streaming\n" "$per_req"
  printf "  • Best system throughput:  %.1f tokens/s (%d concurrent)\n" "$best_concurrent_throughput" "$best_concurrent_level"
  printf "  • Time to first token:     %.2fs average\n" "$avg_ttft"
  printf "  • Latency (single user):   %.2fs average\n" "$avg_latency"
  echo ""
  echo "Recommended concurrent users: ${best_concurrent_level}"
fi

echo ""
echo "═══════════════════════════════════════════════════"

# Cleanup
rm -rf "$TMPDIR"
