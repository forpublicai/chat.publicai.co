#!/bin/bash
set -e

# Function to show usage
show_usage() {
    echo "LLM Services Management Script"
    echo ""
    echo "Usage: $0 [COMMAND]"
    echo ""
    echo "Commands:"
    echo "  --deploy        Deploy LLM services only"
    echo "  --deploy-all    Deploy LLM services and ingress"
    echo "  --cleanup       Remove LLM services only"
    echo "  --cleanup-all   Remove LLM services and ingress"
    echo ""
    echo "Examples:"
    echo "  $0 --deploy     # Deploy services only"
    echo "  $0 --deploy-all # Deploy services + ingress"
    echo "  $0 --cleanup    # Remove services only"
    echo "  $0 --cleanup-all # Remove services + ingress"
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
    )
    
    for var in "${required_vars[@]}"; do
        if [ -z "${!var}" ]; then
            echo "❌ Missing required environment variable: $var"
            exit 1
        fi
    done
    
    echo "✅ Environment variables validated"
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

# Function to deploy LLM ingress
deploy_ingress() {
    echo "📦 Deploying LLM ingress..."
    helm upgrade --install llm-ingress charts/llm_ingress/ \
        -n llm-services \
        --create-namespace
    
    echo "✅ LLM ingress deployment complete!"
}

# Function to deploy everything (ingress first, then services)
deploy_all() {
    echo "🚀 Deploying LLM services and ingress..."
    validate_env
    deploy_ingress
    deploy_services
    show_ingress_info
}

# Function to show ingress information
show_ingress_info() {
    echo ""
    echo "🌐 LLM services access:"
    kubectl get ingress -n llm-services 2>/dev/null || echo "  No LLM ingress found"
}

# Cleanup functions
cleanup_services() {
    echo "🧹 Cleaning up LLM services..."
    helm uninstall llm-services -n llm-services --ignore-not-found || true
    echo "✅ LLM services cleanup complete!"
}

cleanup_ingress() {
    echo "🧹 Cleaning up LLM ingress..."
    helm uninstall llm-ingress -n llm-services --ignore-not-found || true
    echo "✅ LLM ingress cleanup complete!"
}

cleanup_all() {
    echo "🧹 Cleaning up LLM services and ingress..."
    cleanup_services
    cleanup_ingress
    kubectl delete namespace llm-services --ignore-not-found
    echo "✅ LLM cleanup complete!"
}

# Check arguments
if [ "$1" = "--deploy" ]; then
    echo "🚀 Deploying LLM services only..."
    validate_env
    deploy_services
    show_ingress_info
elif [ "$1" = "--deploy-all" ]; then
    deploy_all
elif [ "$1" = "--cleanup" ]; then
    cleanup_services
elif [ "$1" = "--cleanup-all" ]; then
    cleanup_all
else
    show_usage
fi