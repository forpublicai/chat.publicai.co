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
    deploy
elif [ "$1" = "--cleanup" ]; then
    cleanup
else
    show_usage
fi