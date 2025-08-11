#!/bin/bash
set -e

echo "🚀 Deploying Open WebUI to Kubernetes..."

# Check if kubectl is connected
if ! kubectl cluster-info > /dev/null 2>&1; then
    echo "❌ kubectl not connected to cluster. Please run: kubectl config use-context <your-cluster>"
    exit 1
fi

echo "📦 Installing ingress-nginx controller..."
helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
helm repo update
helm install ingress-nginx ingress-nginx/ingress-nginx \
    --namespace ingress-nginx \
    --create-namespace \
    -f web_services/ingress-nginx-values.yaml

echo "📊 Installing metrics server..."
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml

echo "⏳ Waiting for ingress controller to be ready..."
kubectl wait --namespace ingress-nginx \
    --for=condition=ready pod \
    --selector=app.kubernetes.io/component=controller \
    --timeout=300s

echo "🔧 Deploying application manifests..."
kubectl apply -f web_services/namespace.yaml
kubectl apply -f web_services/secrets.yaml
kubectl apply -f web_services/openwebui.yaml
kubectl apply -f web_services/ingress.yaml

echo "⏳ Waiting for OpenWebUI pods to be ready..."
kubectl wait --namespace web-services \
    --for=condition=ready pod \
    --selector=app=openwebui \
    --timeout=300s

echo "✅ Deployment complete!"
echo ""
echo "🔍 Status:"
kubectl get pods -n web-services -o wide
echo ""
kubectl get ingress -n web-services
echo ""
echo "🌐 Your application should be available at: https://app.publicai.company"