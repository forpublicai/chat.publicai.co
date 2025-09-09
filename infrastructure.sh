#!/bin/bash
set -e

# Function to show usage
show_usage() {
    echo "Infrastructure Management Script"
    echo ""
    echo "Usage: $0 [COMMAND]"
    echo ""
    echo "Commands:"
    echo "  --deploy     Deploy ALB controller and IngressClasses"
    echo "  --cleanup    Remove ALB controller and IngressClasses"
    echo ""
    echo "Examples:"
    echo "  $0 --deploy   # Deploy infrastructure"
    echo "  $0 --cleanup  # Remove infrastructure"
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

# Function to deploy infrastructure
deploy() {
    echo "🚀 Deploying shared infrastructure..."
    echo "📦 Installing ALB controller and IngressClasses..."
    helm repo add eks https://aws.github.io/eks-charts
    helm repo update
    helm dependency build charts/infrastructure/
    helm upgrade --install infrastructure charts/infrastructure/ \
        --namespace kube-system
    
    # Wait for AWS Load Balancer Controller to be ready
    echo "⏳ Waiting for AWS Load Balancer Controller to be ready..."
    kubectl wait --for=condition=available --timeout=60s deployment/infrastructure-aws-load-balancer-controller -n kube-system
    echo "✅ AWS Load Balancer Controller is ready!"
    
    # Verify IngressClasses
    echo "📋 Verifying IngressClasses..."
    kubectl get ingressclass alb-web alb-llm
    echo "✅ Infrastructure deployment complete!"
}

# Function to cleanup infrastructure
cleanup() {
    echo "🧹 Cleaning up shared infrastructure..."
    helm uninstall infrastructure -n kube-system --ignore-not-found || true
    echo "✅ Infrastructure cleanup complete!"
}

# Check arguments
if [ "$1" = "--deploy" ]; then
    validate_env
    set_kube_context
    deploy
elif [ "$1" = "--cleanup" ]; then
    cleanup
else
    show_usage
fi