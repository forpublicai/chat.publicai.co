#!/bin/bash
set -e

echo "🧹 Cleaning up Open WebUI deployment..."

echo "🗑️ Removing application resources..."
kubectl delete -f web_services/ingress.yaml --ignore-not-found
kubectl delete -f web_services/openwebui.yaml --ignore-not-found
kubectl delete -f web_services/secrets.yaml --ignore-not-found
kubectl delete -f web_services/namespace.yaml --ignore-not-found

echo "🗑️ Removing ingress controller..."
helm uninstall ingress-nginx -n ingress-nginx || true
kubectl delete namespace ingress-nginx --ignore-not-found

echo "🗑️ Removing metrics server..."
kubectl delete -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml --ignore-not-found

echo "✅ Cleanup complete!"