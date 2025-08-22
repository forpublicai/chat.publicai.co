#!/bin/bash
set -e

# Function to show usage
show_usage() {
    echo "Web Services Management Script"
    echo ""
    echo "Usage: $0 [COMMAND]"
    echo ""
    echo "Commands:"
    echo "  --deploy-all   Deploy infrastructure and web services"
    echo "  --cleanup-all  Remove everything (infrastructure + web services)"
    echo "  --deploy       Deploy web services only"
    echo "  --cleanup      Remove web services only"
    echo ""
    echo "Examples:"
    echo "  $0 --deploy-all  # Deploy infrastructure + web services"
    echo "  $0 --deploy      # Deploy web services only"
    echo "  $0 --cleanup     # Remove web services only"
    echo "  $0 --cleanup-all # Remove everything"
    exit 1
}

# Function to cleanup web services only
cleanup() {
    echo "🧹 Cleaning up web services deployment..."
    
    helm uninstall web-services -n web-services --ignore-not-found || true
    kubectl delete namespace web-services --ignore-not-found
    
    echo "✅ Web services cleanup complete!"
    exit 0
}

# Function to cleanup everything
cleanup_all() {
    echo "🧹 Cleaning up everything (infrastructure + web services)..."
    
    # Remove web services first
    helm uninstall web-services -n web-services --ignore-not-found || true
    kubectl delete namespace web-services --ignore-not-found
    
    # Remove infrastructure
    helm uninstall infrastructure -n kube-system --ignore-not-found || true
    
    echo "✅ Complete cleanup finished!"
    exit 0
}

# Function to deploy infrastructure only
deploy_infrastructure() {
    echo "🏗️  Deploying infrastructure..."
    echo "📦 Installing infrastructure chart..."
    helm repo add eks https://aws.github.io/eks-charts
    helm repo update
    helm dependency build charts/infrastructure/
    helm upgrade --install infrastructure charts/infrastructure/ \
        --namespace kube-system \
        --create-namespace
    
    # Wait for AWS Load Balancer Controller to be ready
    echo "⏳ Waiting for AWS Load Balancer Controller to be ready..."
    kubectl wait --for=condition=available --timeout=60s deployment/infrastructure-aws-load-balancer-controller -n kube-system
    echo "✅ AWS Load Balancer Controller is ready!"
}

# Function to deploy web services only
deploy() {
    echo "📦 Deploying web services only..."
    
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
        "GOOGLE_CLIENT_ID"
        "GOOGLE_CLIENT_SECRET"
        "CERTIFICATE_ARN"
    )
    
    for var in "${required_vars[@]}"; do
        if [ -z "${!var}" ]; then
            echo "❌ Missing required environment variable: $var"
            exit 1
        fi
    done
    
    echo "✅ All required environment variables found"
    
    # Deploy applications only
    echo "🔧 Building Helm dependencies..."
    helm dependency build charts/web_services/
    
    echo "📦 Deploying web services..."
    helm upgrade --install web-services charts/web_services/ \
        -n web-services \
        --create-namespace \
        --set open-webui.secrets.licenseKey="$LICENSE_KEY" \
        --set open-webui.secrets.webuiSecretKey="$WEBUI_SECRET_KEY" \
        --set open-webui.secrets.databaseUrl="$DATABASE_URL" \
        --set open-webui.secrets.redisUrl="$REDIS_URL" \
        --set open-webui.secrets.googleClientId="$GOOGLE_CLIENT_ID" \
        --set open-webui.secrets.googleClientSecret="$GOOGLE_CLIENT_SECRET" \
        --set open-webui.certificateArn="$CERTIFICATE_ARN"
    
    echo "✅ Web services deployment complete!"
    
    echo ""
    echo "🌐 Access your application:"
    kubectl get ingress -n web-services
    
    exit 0
}

# Function to deploy everything (infrastructure + web services)
deploy_all() {
    echo "🚀 Deploying everything (infrastructure + web services)..."
    
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
        "GOOGLE_CLIENT_ID"
        "GOOGLE_CLIENT_SECRET"
        "CERTIFICATE_ARN"
    )
    
    for var in "${required_vars[@]}"; do
        if [ -z "${!var}" ]; then
            echo "❌ Missing required environment variable: $var"
            exit 1
        fi
    done
    
    echo "✅ All required environment variables found"
    
    # Deploy infrastructure first
    deploy_infrastructure
    
    # Deploy applications
    echo "🔧 Building Helm dependencies..."
    helm dependency build charts/web_services/
    
    echo "📦 Deploying web services..."
    helm upgrade --install web-services charts/web_services/ \
        -n web-services \
        --create-namespace \
        --set open-webui.secrets.licenseKey="$LICENSE_KEY" \
        --set open-webui.secrets.webuiSecretKey="$WEBUI_SECRET_KEY" \
        --set open-webui.secrets.databaseUrl="$DATABASE_URL" \
        --set open-webui.secrets.redisUrl="$REDIS_URL" \
        --set open-webui.secrets.googleClientId="$GOOGLE_CLIENT_ID" \
        --set open-webui.secrets.googleClientSecret="$GOOGLE_CLIENT_SECRET" \
        --set open-webui.certificateArn="$CERTIFICATE_ARN"
    
    echo "✅ Complete deployment finished!"
    
    echo ""
    echo "🌐 Access your application by running kubectl get ingress -n web-services"
    kubectl get ingress -n web-services
    
    exit 0
}

# Check arguments
if [ "$1" = "--deploy-all" ]; then
    deploy_all
elif [ "$1" = "--cleanup-all" ]; then
    cleanup_all
elif [ "$1" = "--deploy" ]; then
    deploy
elif [ "$1" = "--cleanup" ]; then
    cleanup
else
    show_usage
fi