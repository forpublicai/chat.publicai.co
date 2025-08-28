#!/bin/bash
set -e

# Function to show usage
show_usage() {
    echo "Web Services Management Script"
    echo ""
    echo "Usage: $0 [COMMAND]"
    echo ""
    echo "Commands:"
    echo "  --deploy-all   Deploy web infrastructure and web services"
    echo "  --cleanup-all  Remove web services and web infrastructure"
    echo "  --deploy       Deploy web services only"
    echo "  --cleanup      Remove web services only"
    echo ""
    echo "Examples:"
    echo "  $0 --deploy-all  # Deploy web infrastructure + web services"
    echo "  $0 --deploy      # Deploy web services only"
    echo "  $0 --cleanup     # Remove web services only"
    echo "  $0 --cleanup-all # Remove web services and web infrastructure"
    exit 1
}

# Function to cleanup web services only
cleanup() {
    echo "🧹 Cleaning up web services deployment..."
    
    helm uninstall web-services -n web-services --ignore-not-found || true
    
    echo "✅ Web services cleanup complete!"
    exit 0
}

# Function to cleanup web services and web infrastructure  
cleanup_all() {
    echo "🧹 Cleaning up web services and web infrastructure..."
    
    # Remove both releases first, then delete namespace
    helm uninstall web-services -n web-services --ignore-not-found || true
    helm uninstall web-infrastructure -n web-services --ignore-not-found || true
    kubectl delete namespace web-services --ignore-not-found
    
    echo "✅ Web services and web infrastructure cleanup complete!"
    exit 0
}


# Function to deploy web infrastructure only
deploy_infrastructure() {
    echo "🏗️  Deploying web infrastructure..."
    echo "📦 Installing web infrastructure chart..."
    helm repo add eks https://aws.github.io/eks-charts
    helm repo update
    helm dependency build charts/web_infrastructure/
    helm upgrade --install web-infrastructure charts/web_infrastructure/ \
        --namespace web-services \
        --create-namespace \
        --set certificateArn="$CERTIFICATE_ARN"
    
    # Wait for AWS Load Balancer Controller to be ready
    echo "⏳ Waiting for AWS Load Balancer Controller to be ready..."
    kubectl wait --for=condition=available --timeout=60s deployment/web-infrastructure-aws-load-balancer-controller -n web-services
    echo "✅ AWS Load Balancer Controller is ready!"
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
    
    # Validate required environment variables
    local required_vars=(
        "LICENSE_KEY"
        "WEBUI_SECRET_KEY"
        "DATABASE_URL"
        "REDIS_URL"
        "CERTIFICATE_ARN"
        # "GOOGLE_CLIENT_ID"
        # "GOOGLE_CLIENT_SECRET"
        "OPENID_PROVIDER_URL"
        "OAUTH_CLIENT_ID"
        "OAUTH_CLIENT_SECRET"
        "OPENID_REDIRECT_URI"
    )
    
    for var in "${required_vars[@]}"; do
        if [ -z "${!var}" ]; then
            echo "❌ Missing required environment variable: $var"
            exit 1
        fi
    done
    
    echo "✅ All required environment variables found"
}

# Function to deploy web services
deploy_web_services() {
    echo "🔧 Building Helm dependencies..."
    helm dependency build charts/web_services/
    
    echo "📦 Deploying web services..."
    helm upgrade --install web-services charts/web_services/ \
        -n web-services \
        --set open-webui.secrets.licenseKey="$LICENSE_KEY" \
        --set open-webui.secrets.webuiSecretKey="$WEBUI_SECRET_KEY" \
        --set open-webui.secrets.databaseUrl="$DATABASE_URL" \
        --set open-webui.secrets.redisUrl="$REDIS_URL" \
        --set open-webui.secrets.openidProviderUrl="$OPENID_PROVIDER_URL" \
        --set open-webui.secrets.oauthClientId="$OAUTH_CLIENT_ID" \
        --set open-webui.secrets.oauthClientSecret="$OAUTH_CLIENT_SECRET" \
        --set open-webui.secrets.openidRedirectUri="$OPENID_REDIRECT_URI"
        # --set open-webui.secrets.googleClientId="$GOOGLE_CLIENT_ID" \
        # --set open-webui.secrets.googleClientSecret="$GOOGLE_CLIENT_SECRET" \
    
    echo "✅ Web services deployment complete!"
}

# Function to show ingress information
show_ingress_info() {
    echo ""
    echo "🌐 Access your application:"
    kubectl get ingress -n web-services
}

# Function to deploy web services only
deploy() {
    echo "📦 Deploying web services only..."
    
    validate_env
    deploy_web_services
    show_ingress_info
    
    exit 0
}

# Function to deploy web services (web infrastructure + web services)
deploy_all() {
    echo "🚀 Deploying web services (web infrastructure + web services)..."
    
    validate_env
    deploy_infrastructure
    deploy_web_services
    
    echo "✅ Web services deployment finished!"
    echo "🌐 Access your application by running kubectl get ingress -n web-services"
    show_ingress_info
    
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