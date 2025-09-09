#!/bin/bash
set -e

# Function to show usage
show_usage() {
    echo "LLM Services Management Script"
    echo ""
    echo "Usage: $0 [COMMAND]"
    echo ""
    echo "Commands:"
    echo "  --deploy        Deploy LLM services"
    echo "  --cleanup       Remove LLM services"
    echo ""
    echo "Examples:"
    echo "  $0 --deploy     # Deploy vLLM services (ClusterIP only)"
    echo "  $0 --cleanup    # Remove vLLM services"
    echo ""
    echo "Note: LLM services use ClusterIP - access via LiteLLM API gateway"
    exit 1
}

# Function to validate environment variables
validate_env() {
    # Check if .env file exists
    if [ ! -f ".env" ]; then
        echo "❌ .env file not found. Please create .env with required variables."
        exit 1
    fi
    
    # Load environment variables from .env file
    set -a && source .env && set +a
    
    local required_vars=(
        "VLLM_API_KEY"
        "EXPECTED_KUBE_CONTEXT"
    )
    
    for var in "${required_vars[@]}"; do
        if [ -z "${!var}" ]; then
            echo "❌ Missing required environment variable: $var"
            exit 1
        fi
    done
    
    echo "✅ Environment variables validated"
}

# Function to set Kubernetes context
set_kube_context() {
    local current_context=$(kubectl config current-context 2>/dev/null)
    
    if [ "$current_context" != "$EXPECTED_KUBE_CONTEXT" ]; then
        echo "🔄 Switching Kubernetes context..."
        echo "   From: $current_context"
        echo "   To: $EXPECTED_KUBE_CONTEXT"
        kubectl config use-context "$EXPECTED_KUBE_CONTEXT"
    fi
    
    echo "✅ Using Kubernetes context: $EXPECTED_KUBE_CONTEXT"
}

# Function to deploy LLM services
deploy_services() {
    echo "🔧 Building LLM services dependencies..."
    helm repo add vllm https://vllm-project.github.io/production-stack
    helm repo update
    helm dependency build charts/llm_services/
    
    echo "📦 Deploying LLM services..."
    helm upgrade --install llm-services charts/llm_services/ \
        -n llm-services \
        --create-namespace \
        --set-string vllm-stack.servingEngineSpec.vllmApiKey="$VLLM_API_KEY"
    
    echo "✅ LLM services deployment complete!"
}

# Function to show service information
show_service_info() {
    echo ""
    echo "🔗 LLM services (internal ClusterIP):"
    kubectl get services -n llm-services 2>/dev/null || echo "  No LLM services found"
    echo ""
    echo "💡 Access via LiteLLM API gateway at api.publicai.co (when enabled)"
}

# Cleanup functions
cleanup_services() {
    echo "🧹 Cleaning up LLM services..."
    helm uninstall llm-services -n llm-services --ignore-not-found || true
    # Clean up any remaining llm-ingress (legacy)
    helm uninstall llm-ingress -n llm-services --ignore-not-found || true
    kubectl delete namespace llm-services --ignore-not-found
    echo "✅ LLM services cleanup complete!"
}

# Check arguments
if [ "$1" = "--deploy" ]; then
    echo "🚀 Deploying LLM services (ClusterIP only)..."
    validate_env
    set_kube_context
    deploy_services
    show_service_info
elif [ "$1" = "--cleanup" ]; then
    cleanup_services
else
    show_usage
fi