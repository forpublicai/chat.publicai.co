#!/bin/bash
set -e

# Function to show usage
show_usage() {
    echo "Web Services Management Script"
    echo ""
    echo "Usage: $0 [COMMAND]"
    echo ""
    echo "Commands:"
    echo "  --deploy   Deploy web services to Kubernetes"
    echo "  --cleanup  Remove web services deployment (preserves ingress + load balancer)"
    echo "  --monitor  Monitor deployment status"
    echo ""
    echo "Examples:"
    echo "  $0 --deploy   # Deploy OpenWebUI (with ingress) and SearXNG"
    echo "  $0 --monitor  # Check deployment status"
    echo "  $0 --cleanup  # Remove applications but preserve ingress-nginx controller"
    exit 1
}

# Function to cleanup deployment
cleanup() {
    echo "🧹 Cleaning up web services deployment..."
    
    # Remove only the application components, preserve ingress-nginx
    helm uninstall openwebui --ignore-not-found || true
    helm uninstall searxng --ignore-not-found || true
    
    # Remove only the web-services namespace (preserves ingress-nginx namespace)
    kubectl delete namespace web-services --ignore-not-found
    
    echo "ℹ️  LoadBalancer and ingress preserved (maintains domain IP address)"
    echo "🔍 Checking ingress-nginx status..."
    kubectl get svc -n ingress-nginx 2>/dev/null || echo "⚠️  ingress-nginx namespace not found"
    echo "✅ Cleanup complete!"
    exit 0
}

# Function to monitor deployment
monitor() {
    echo "📊 Monitoring web services deployment..."
    
    echo ""
    echo "🏊 Cluster node pools:"
    kubectl get nodes -o custom-columns="NAME:.metadata.name,STATUS:.status.conditions[?(@.type==\"Ready\")].status,ROLES:.metadata.labels.kubernetes\.io/role,INSTANCE-TYPE:.metadata.labels.node\.kubernetes\.io/instance-type,ZONE:.metadata.labels.topology\.kubernetes\.io/zone" 2>/dev/null || kubectl get nodes
    
    echo ""
    echo "📦 All pods across cluster:"
    kubectl get pods --all-namespaces -o wide
    
    echo ""
    echo "📍 Pods grouped by node:"
    for node in $(kubectl get nodes -o jsonpath='{.items[*].metadata.name}'); do
        echo ""
        echo "🖥️  Node: $node"
        kubectl get pods --all-namespaces --field-selector spec.nodeName=$node -o custom-columns="NAMESPACE:.metadata.namespace,NAME:.metadata.name,STATUS:.status.phase,READY:.status.containerStatuses[*].ready" 2>/dev/null || echo "  No pods on this node"
    done
    
    echo ""
    echo "🔍 Helm release status:"
    helm status openwebui || echo "❌ OpenWebUI Helm release not found"
    helm status searxng || echo "❌ SearXNG Helm release not found"
    
    echo ""
    echo "🔍 Application pods (OpenWebUI + SearXNG):"
    kubectl get pods -n web-services -o wide || echo "❌ web-services namespace not found"
    
    echo ""
    echo "🔍 Application services:"
    kubectl get svc -n web-services || echo "❌ No services found in web-services"
    
    echo ""
    echo "🔍 Ingress controller (infrastructure):"
    kubectl get pods,svc -n ingress-nginx || echo "❌ ingress-nginx namespace not found"
    
    echo ""
    echo "🔍 Ingress resources:"
    kubectl get ingress -n web-services || echo "❌ No ingress found"
    
    echo ""
    echo "🔍 HPA status:"
    kubectl get hpa -n web-services || echo "❌ No HPA found"
    
    echo ""
    echo "📝 Recent events (application):"
    kubectl get events -n web-services --sort-by='.lastTimestamp' | tail -5 || echo "❌ No events found"
    
    echo ""
    echo "📝 Recent events (ingress):"
    kubectl get events -n ingress-nginx --sort-by='.lastTimestamp' | tail -5 || echo "❌ No ingress events found"
    
    exit 0
}

# Function to deploy web services
deploy() {
    echo "🚀 Deploying Open WebUI to Kubernetes with Helm..."
    
    # Check if .env file exists
    if [ ! -f ".env" ]; then
        echo "❌ .env file not found. Please create .env with required variables."
        exit 1
    fi
    
    # Load environment variables from .env file
    set -a && source .env && set +a
    
    # Validate required environment variables
    required_vars=(
        "LICENSE_KEY"
        "WEBUI_SECRET_KEY"
        "DATABASE_URL"
        "REDIS_URL"
        "S3_ACCESS_KEY_ID"
        "S3_SECRET_ACCESS_KEY"
        "GOOGLE_CLIENT_ID"
        "GOOGLE_CLIENT_SECRET"
    )
    
    for var in "${required_vars[@]}"; do
        if [ -z "${!var}" ]; then
            echo "❌ Missing required environment variable: $var"
            exit 1
        fi
    done
    
    echo "✅ All required environment variables found"
    
    echo "🔧 Creating ingress-nginx namespace..."
    kubectl create namespace ingress-nginx --dry-run=client -o yaml | kubectl apply -f -
    
    echo "🌐 Installing ingress-nginx controller..."
    helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
    helm repo update
    helm upgrade --install ingress-nginx ingress-nginx/ingress-nginx \
        --namespace ingress-nginx \
        --set controller.service.type=LoadBalancer
    
    
    # Deploy Open WebUI with Helm (includes ingress)
    echo "📦 Deploying Open WebUI..."
    helm upgrade --install openwebui web_services/open-webui/ \
        --create-namespace \
        --set secrets.licenseKey="$LICENSE_KEY" \
        --set secrets.webuiSecretKey="$WEBUI_SECRET_KEY" \
        --set secrets.databaseUrl="$DATABASE_URL" \
        --set secrets.redisUrl="$REDIS_URL" \
        --set secrets.s3AccessKeyId="$S3_ACCESS_KEY_ID" \
        --set secrets.s3SecretAccessKey="$S3_SECRET_ACCESS_KEY" \
        --set secrets.googleClientId="$GOOGLE_CLIENT_ID" \
        --set secrets.googleClientSecret="$GOOGLE_CLIENT_SECRET"
    
    # Deploy SearXNG (optional)
    echo "🔍 Deploying SearXNG..."
    helm upgrade --install searxng web_services/searxng/ \
        --create-namespace
    
    echo "✅ Deployment complete!"
    exit 0
}

# Check arguments
if [ "$1" = "--deploy" ]; then
    deploy
elif [ "$1" = "--cleanup" ]; then
    cleanup
elif [ "$1" = "--monitor" ]; then
    monitor
else
    show_usage
fi