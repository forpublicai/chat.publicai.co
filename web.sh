#!/bin/bash
set -e

# Function to show usage
show_usage() {
    echo "Web Services Management Script"
    echo ""
    echo "Usage: $0 [COMMAND]"
    echo ""
    echo "Commands:"
    echo "  --deploy        Deploy web services only"
    echo "  --deploy-all    Deploy web services and ingress"
    echo "  --cleanup       Remove web services only"
    echo "  --cleanup-all   Remove web services and ingress"
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
        "LICENSE_KEY"
        "WEBUI_SECRET_KEY"
        "DATABASE_URL"
        "REDIS_URL"
        "CERTIFICATE_ARN"
        "OPENID_PROVIDER_URL"
        "OAUTH_CLIENT_ID"
        "OAUTH_CLIENT_SECRET"
        "OPENID_REDIRECT_URI"
        "LITELLM_API_KEY"
    )
    
    for var in "${required_vars[@]}"; do
        if [ -z "${!var}" ]; then
            echo "❌ Missing required environment variable: $var"
            exit 1
        fi
    done
    
    echo "✅ Environment variables validated"
}

# Function to deploy web services
deploy_services() {
    echo "🔧 Building web services dependencies..."
    helm dependency build charts/web_services/
    
    echo "📦 Deploying web services..."
    helm upgrade --install web-services charts/web_services/ \
        -n web-services \
        --create-namespace \
        --set open-webui.secrets.licenseKey="$LICENSE_KEY" \
        --set open-webui.secrets.webuiSecretKey="$WEBUI_SECRET_KEY" \
        --set open-webui.secrets.databaseUrl="$DATABASE_URL" \
        --set open-webui.secrets.redisUrl="$REDIS_URL" \
        --set open-webui.secrets.openidProviderUrl="$OPENID_PROVIDER_URL" \
        --set open-webui.secrets.oauthClientId="$OAUTH_CLIENT_ID" \
        --set open-webui.secrets.oauthClientSecret="$OAUTH_CLIENT_SECRET" \
        --set open-webui.secrets.openidRedirectUri="$OPENID_REDIRECT_URI" \
        --set litellm.secrets.litellmMasterKey="$LITELLM_API_KEY"
    
    echo "✅ Web services deployment complete!"
}

# Function to deploy web ingress
deploy_ingress() {
    echo "📦 Deploying web ingress..."
    helm upgrade --install web-ingress charts/web_ingress/ \
        -n web-services \
        --create-namespace \
        --set certificateArn="$CERTIFICATE_ARN"
    
    echo "✅ Web ingress deployment complete!"
}

# Function to deploy everything (ingress first, then services)
deploy_all() {
    echo "🚀 Deploying web services and ingress..."
    validate_env
    deploy_ingress
    deploy_services
    show_ingress_info
}

# Function to show ingress information
show_ingress_info() {
    echo ""
    echo "🌐 Web services access:"
    kubectl get ingress -n web-services 2>/dev/null || echo "  No web ingress found"
}

# Cleanup functions
cleanup_services() {
    echo "🧹 Cleaning up web services..."
    helm uninstall web-services -n web-services --ignore-not-found || true
    echo "✅ Web services cleanup complete!"
}

cleanup_ingress() {
    echo "🧹 Cleaning up web ingress..."
    helm uninstall web-ingress -n web-services --ignore-not-found || true
    echo "✅ Web ingress cleanup complete!"
}

cleanup_all() {
    echo "🧹 Cleaning up web services and ingress..."
    cleanup_services
    cleanup_ingress
    kubectl delete namespace web-services --ignore-not-found
    echo "✅ Web cleanup complete!"
}

# Check arguments
if [ "$1" = "--deploy" ]; then
    echo "🚀 Deploying web services only..."
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