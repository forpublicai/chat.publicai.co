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
        "OWUI_DATABASE_URL"
        "OWUI_REDIS_URL"
        "CERTIFICATE_ARN"
        "OPENID_PROVIDER_URL"
        "OAUTH_CLIENT_ID"
        "OAUTH_CLIENT_SECRET"
        "OPENID_REDIRECT_URI"
        "LITELLM_API_KEY"
        "LITELLM_SALT_KEY"
        "LITELLM_DATABASE_URL"
        "LITELLM_REDIS_URL"
        "TOGETHER_API_KEY"
        "SEALION_API_KEY"
        "VLLM_API_KEY"
        "VLLM_API_KEY_EXOSCALE"
        "VLLM_API_KEY_ANU"
        "VLLM_API_KEY_CSCS"
        "VLLM_API_KEY_CUDO"
        "VLLM_API_KEY_HH"
        "VLLM_API_KEY_INTEL"
        "CIRRASCALE_API_KEY"
        "PARASCALE_API_KEY"
        "MULTIVERSE_API_KEY"
        "LAGO_DATABASE_URL"
        "LAGO_REDIS_URL"
        "LAGO_SECRET_KEY_BASE"
        "LAGO_ENCRYPTION_PRIMARY_KEY"
        "LAGO_ENCRYPTION_DETERMINISTIC_KEY"
        "LAGO_ENCRYPTION_KEY_DERIVATION_SALT"
        "LAGO_RSA_PRIVATE_KEY"
        "LAGO_API_KEY"
        "EXPECTED_KUBE_CONTEXT"
        "DICTA_API_KEY"
        "INFOMANIAK_API_KEY"
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

# Function to deploy web services
deploy_services() {
    echo "🔧 Building web services dependencies..."
    helm dependency build charts/web_services/

    echo "📦 Deploying web services with Lago billing..."
    helm upgrade --install web-services charts/web_services/ \
        -n web-services \
        --create-namespace \
        --set open-webui.secrets.licenseKey="$LICENSE_KEY" \
        --set open-webui.secrets.webuiSecretKey="$WEBUI_SECRET_KEY" \
        --set open-webui.secrets.databaseUrl="$OWUI_DATABASE_URL" \
        --set open-webui.secrets.redisUrl="$OWUI_REDIS_URL" \
        --set open-webui.secrets.openidProviderUrl="$OPENID_PROVIDER_URL" \
        --set open-webui.secrets.oauthClientId="$OAUTH_CLIENT_ID" \
        --set open-webui.secrets.oauthClientSecret="$OAUTH_CLIENT_SECRET" \
        --set open-webui.secrets.openidRedirectUri="$OPENID_REDIRECT_URI" \
        --set litellm.enabled=true \
        --set litellm.secrets.litellmMasterKey="$LITELLM_API_KEY" \
        --set litellm.secrets.litellmSaltKey="$LITELLM_SALT_KEY" \
        --set litellm.secrets.databaseUrl="$LITELLM_DATABASE_URL" \
        --set litellm.secrets.redisUrl="$LITELLM_REDIS_URL" \
        --set litellm.secrets.togetherApiKey="$TOGETHER_API_KEY" \
        --set litellm.secrets.sealionApiKey="$SEALION_API_KEY" \
        --set litellm.secrets.vllmApiKey="$VLLM_API_KEY" \
        --set litellm.secrets.vllmApiKeyExoscale="$VLLM_API_KEY_EXOSCALE" \
        --set litellm.secrets.vllmApiKeyAnu="$VLLM_API_KEY_ANU" \
        --set litellm.secrets.vllmApiKeyCscs="$VLLM_API_KEY_CSCS" \
        --set litellm.secrets.vllmApiKeyCudo="$VLLM_API_KEY_CUDO" \
        --set litellm.secrets.vllmApiKeyHh="$VLLM_API_KEY_HH" \
        --set litellm.secrets.vllmApiKeyIntel="$VLLM_API_KEY_INTEL" \
        --set litellm.secrets.cirrascaleApiKey="$CIRRASCALE_API_KEY" \
        --set litellm.secrets.parascaleApiKey="$PARASCALE_API_KEY" \
        --set litellm.secrets.multiverseApiKey="$MULTIVERSE_API_KEY" \
        --set litellm.secrets.lagoApiKey="$LAGO_API_KEY" \
        --set litellm.secrets.dictaApiKey="$DICTA_API_KEY" \
        --set litellm.secrets.infomaniakApiKey="$INFOMANIAK_API_KEY" \
        --set litellm.lago.enabled=true \
        --set lago.enabled=true \
        --set lago.global.databaseUrl="$LAGO_DATABASE_URL" \
        --set lago.global.redisUrl="$LAGO_REDIS_URL" 
        

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
    set_kube_context
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
    set_kube_context
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