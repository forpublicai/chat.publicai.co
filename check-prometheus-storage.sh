#!/usr/bin/env bash
set -euo pipefail

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

NAMESPACE="${PROMETHEUS_NAMESPACE:-monitoring}"
CONTEXT="${KUBE_CONTEXT:-}"

echo -e "${BLUE}===============================================${NC}"
echo -e "${BLUE}   Prometheus Storage & Retention Status       ${NC}"
echo -e "${BLUE}===============================================${NC}"

REQUIRED_CONTEXT="arn:aws:eks:eu-central-2:901779868336:cluster/prod-main-cluster"

# 1. Check target context
CURRENT_CTX="${CONTEXT:-$(kubectl config current-context 2>/dev/null || echo "Unknown")}"

if [ "$CURRENT_CTX" != "$REQUIRED_CONTEXT" ]; then
    echo -e "${RED}Error: Cannot run this script on the current context!${NC}"
    echo -e "This script is restricted to production: ${GREEN}$REQUIRED_CONTEXT${NC}"
    echo -e "Current context is:                      ${YELLOW}$CURRENT_CTX${NC}"
    echo -e "\nPlease switch to the production context first:"
    echo -e "  ${BLUE}kubectl config use-context $REQUIRED_CONTEXT${NC}"
    exit 1
fi

KUBECTL_CMD="kubectl --context $REQUIRED_CONTEXT"

echo -e "${YELLOW}Context (Verified):${NC} $CURRENT_CTX"
echo -e "${YELLOW}Namespace:${NC}          $NAMESPACE"
echo ""

# 2. Get PVC Info
echo -e "${BLUE}[1/4] Checking PVC Status...${NC}"
$KUBECTL_CMD get pvc -n "$NAMESPACE" -l app.kubernetes.io/name=prometheus 2>/dev/null || \
$KUBECTL_CMD get pvc prometheus-server -n "$NAMESPACE" --no-headers -o custom-columns=\
"NAME:.metadata.name,STATUS:.status.phase,CAPACITY:.status.capacity.storage,STORAGECLASS:.spec.storageClassName,AGE:.metadata.creationTimestamp" || {
    echo -e "${RED}Failed to find Prometheus PVC in namespace '$NAMESPACE'.${NC}"
    exit 1
}
echo ""

# 3. Locate Prometheus Server Pod
echo -e "${BLUE}[2/4] Locating Prometheus Pod...${NC}"
PROMETHEUS_POD=$($KUBECTL_CMD get pods -n "$NAMESPACE" -l app.kubernetes.io/name=prometheus,app.kubernetes.io/component=server -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)

if [ -z "$PROMETHEUS_POD" ]; then
    # Fallback to any pod starting with prometheus-server
    PROMETHEUS_POD=$($KUBECTL_CMD get pods -n "$NAMESPACE" --no-headers -o custom-columns=":metadata.name" | grep '^prometheus-server-' | head -n 1 || true)
fi

if [ -z "$PROMETHEUS_POD" ]; then
    echo -e "${RED}Error: Could not find a running Prometheus server pod in namespace '$NAMESPACE'.${NC}"
    exit 1
fi
echo -e "Found Pod: ${GREEN}$PROMETHEUS_POD${NC}"
echo ""

# 4. Check Disk Usage inside the container
echo -e "${BLUE}[3/4] Disk Filesystem Usage (/data)...${NC}"
$KUBECTL_CMD exec -n "$NAMESPACE" "$PROMETHEUS_POD" -c prometheus-server -- df -h /data
echo ""

echo -e "${BLUE}[4/4] Data Directory Breakdown (/data)...${NC}"
$KUBECTL_CMD exec -n "$NAMESPACE" "$PROMETHEUS_POD" -c prometheus-server -- sh -c '
    echo "Total Data Size: $(du -sh /data | cut -f1)"
    echo "---"
    du -h -d 1 /data 2>/dev/null | sort -h
'
echo ""

# 5. Check Active Retention Flags
echo -e "${BLUE}Configured Retention Flags:${NC}"
$KUBECTL_CMD get deployment -n "$NAMESPACE" prometheus-server -o jsonpath='{.spec.template.spec.containers[?(@.name=="prometheus-server")].args}' | \
    grep -o -E '"--storage\.tsdb\.retention\.[^"]+"' | tr -d '"' | while read -r flag; do
        echo -e "  ${GREEN}✓${NC} $flag"
    done || true

echo ""
echo -e "${GREEN}Check completed successfully.${NC}"
