#!/usr/bin/env bash
set -euo pipefail

NAMESPACE="${NAMESPACE:-monitoring}"

echo "============================================="
echo " Prometheus Storage Usage Check"
echo " Namespace: ${NAMESPACE}"
echo "============================================="
echo ""

# Check PVC info
echo "[1] PersistentVolumeClaim Status:"
kubectl get pvc -n "${NAMESPACE}" -l "app.kubernetes.io/name=prometheus,app.kubernetes.io/component=server" 2>/dev/null || \
kubectl get pvc prometheus-server -n "${NAMESPACE}" 2>/dev/null || \
kubectl get pvc -n "${NAMESPACE}"

echo ""
echo "[2] Live Filesystem Usage (/data):"

# Find the Prometheus server pod
POD=$(kubectl get pods -n "${NAMESPACE}" -l "app.kubernetes.io/name=prometheus,app.kubernetes.io/component=server" -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)

if [ -z "${POD}" ]; then
  # Fallback to finding pod by prefix
  POD=$(kubectl get pods -n "${NAMESPACE}" --no-headers -o custom-columns=":metadata.name" | grep -E '^prometheus-server' | head -n 1 || true)
fi

if [ -z "${POD}" ]; then
  echo "Error: Could not locate Prometheus server pod in namespace '${NAMESPACE}'." >&2
  exit 1
fi

echo "Pod: ${POD}"
echo "---------------------------------------------"
kubectl exec -n "${NAMESPACE}" "${POD}" -c prometheus-server -- df -h /data

echo ""
echo "============================================="
