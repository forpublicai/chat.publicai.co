#!/bin/bash
set -e

# Function to show usage
show_usage() {
    echo "Web Services Management Script"
    echo ""
    echo "Usage: $0 [COMMAND]"
    echo ""
    echo "Commands:"
    echo "  --deploy            Deploy web services only"
    echo "  --deploy-all        Deploy web services and ingress"
    echo "  --cleanup           Remove web services only"
    echo "  --cleanup-all       Remove web services and ingress"
    echo "  --validate          Validate configurations and compile templates locally (offline)"
    echo "  --dry-run [TARGET]  Validate environment and simulate deployment on cluster"
    echo "                      (TARGET can be --deploy or --deploy-all. Defaults to --deploy-all)"
    echo ""
    echo "Examples:"
    echo "  $0 --deploy         # Deploy services only"
    echo "  $0 --deploy-all     # Deploy services + ingress"
    echo "  $0 --cleanup        # Remove services only"
    echo "  $0 --cleanup-all    # Remove services + ingress"
    echo "  $0 --validate       # Run dry-run checks and offline lint/template compilation"
    echo "  $0 --dry-run        # Simulate full deployment (ingress + services)"
    echo "  $0 --dry-run --deploy # Simulate deploying services only"
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
        "SEALION_API_KEY"
        "VLLM_API_KEY_INTEL"
        "LAGO_DATABASE_URL"
        "LAGO_REDIS_URL"
        "LAGO_SECRET_KEY_BASE"
        "LAGO_ENCRYPTION_PRIMARY_KEY"
        "LAGO_ENCRYPTION_DETERMINISTIC_KEY"
        "LAGO_ENCRYPTION_KEY_DERIVATION_SALT"
        "LAGO_RSA_PRIVATE_KEY"
        "LAGO_API_KEY"
        "EXPECTED_KUBE_CONTEXT"
        "INFOMANIAK_API_KEY"
        "BIELIK_API_KEY"
        "CSCS_API_KEY"
        "GRAFANA_ADMIN_USER"
        "GRAFANA_ADMIN_PASSWORD"
        "PROMETHEUS_ADMIN_USER"
        "PROMETHEUS_ADMIN_PASSWORD"
    )
    
    for var in "${required_vars[@]}"; do
        if [ -z "${!var}" ]; then
            echo "❌ Missing required environment variable: $var"
            exit 1
        fi
    done

    # Generate base64 auth token for Prometheus probes
    export PROMETHEUS_AUTH_TOKEN=$(echo -n "${PROMETHEUS_ADMIN_USER}:${PROMETHEUS_ADMIN_PASSWORD}" | base64)
    
    echo "✅ Environment variables validated"
}

# Function to set Kubernetes context
set_kube_context() {
    local current_context=$(kubectl config current-context 2>/dev/null)
    
    if [ "$current_context" != "$EXPECTED_KUBE_CONTEXT" ]; then
        echo "🔄 Switching Kubernetes context..."
        echo "   From: $current_context"
        echo "   To: $EXPECTED_KUBE_CONTEXT"
        if ! kubectl config use-context "$EXPECTED_KUBE_CONTEXT" 2>/dev/null; then
            echo ""
            echo "Please make sure the aws cli is installed, then in the aws console find the IAM user called currentai-cluster-deploy and generate security keys for them and add to using aws configure. Then run the commands below to check and add the kubecontext from aws cli."
            echo ""
            echo "aws sts get-caller-identity"
            echo "aws eks list-clusters --region eu-central-2"
            echo "aws eks update-kubeconfig --region eu-central-2 --name publicai-eks"
            exit 1
        fi
    fi
    
    echo "✅ Using Kubernetes context: $EXPECTED_KUBE_CONTEXT"
}

# Function to deploy web services
deploy_services() {
    echo "🔧 Building web services dependencies..."
    helm dependency build charts/web_services/

    echo "📦 Deploying web services with Lago billing..."
    helm upgrade --install web-services charts/web_services/ \
        -n web-services --timeout 15m --debug \
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
        --set litellm.secrets.sealionApiKey="$SEALION_API_KEY" \
        --set litellm.secrets.vllmApiKeyIntel="$VLLM_API_KEY_INTEL" \
        --set litellm.secrets.lagoApiKey="$LAGO_API_KEY" \
        --set litellm.secrets.infomaniakApiKey="$INFOMANIAK_API_KEY" \
        --set litellm.secrets.bielikApiKey="$BIELIK_API_KEY" \
        --set litellm.secrets.cscsApiKey="$CSCS_API_KEY" \
        --set litellm.lago.enabled=true \
        --set lago.enabled=true \
        --set lago.global.databaseUrl="$LAGO_DATABASE_URL" \
        --set lago.global.redisUrl="$LAGO_REDIS_URL" \
        --set prometheus.enabled=true \
        --set prometheus.adminUser="$PROMETHEUS_ADMIN_USER" \
        --set prometheus.adminPassword="$PROMETHEUS_ADMIN_PASSWORD" \
        --set-string "prometheus.server.probeHeaders[0].name=Authorization" \
        --set-string "prometheus.server.probeHeaders[0].value=Basic ${PROMETHEUS_AUTH_TOKEN}" \
        --set grafana.enabled=true \
        --set grafana.adminUser="$GRAFANA_ADMIN_USER" \
        --set grafana.adminPassword="$GRAFANA_ADMIN_PASSWORD" \
        --set grafana.env.PROMETHEUS_ADMIN_USER="$PROMETHEUS_ADMIN_USER" \
        --set grafana.env.PROMETHEUS_ADMIN_PASSWORD="$PROMETHEUS_ADMIN_PASSWORD" \
        --set loki.enabled=true \
        --set promtail.enabled=true \
        --set litellm.prometheus.enabled=true 
        

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

# Function to validate configurations and templates locally (offline)
validate() {
    echo "🔍 Validating environment variables..."
    validate_env

    echo "🔍 Running configuration alignment checks..."
    python3 health-check/code_check_endpoint.py

    echo "🔧 Building web services dependencies..."
    helm dependency build charts/web_services/

    echo "🔍 Linting Helm charts..."
    helm lint charts/web_services/
    helm lint charts/web_ingress/

    echo "🔍 Rendering templates locally (offline dry-run)..."
    echo "   --- Testing charts/web_ingress/ ---"
    helm template web-ingress charts/web_ingress/ \
        --set certificateArn="$CERTIFICATE_ARN" > /dev/null

    echo "   --- Testing charts/web_services/ ---"
    helm template web-services charts/web_services/ \
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
        --set litellm.secrets.sealionApiKey="$SEALION_API_KEY" \
        --set litellm.secrets.vllmApiKeyIntel="$VLLM_API_KEY_INTEL" \
        --set litellm.secrets.lagoApiKey="$LAGO_API_KEY" \
        --set litellm.secrets.infomaniakApiKey="$INFOMANIAK_API_KEY" \
        --set litellm.secrets.bielikApiKey="$BIELIK_API_KEY" \
        --set litellm.secrets.cscsApiKey="$CSCS_API_KEY" \
        --set litellm.lago.enabled=true \
        --set lago.enabled=true \
        --set lago.global.databaseUrl="$LAGO_DATABASE_URL" \
        --set lago.global.redisUrl="$LAGO_REDIS_URL" \
        --set prometheus.enabled=true \
        --set prometheus.adminUser="$PROMETHEUS_ADMIN_USER" \
        --set prometheus.adminPassword="$PROMETHEUS_ADMIN_PASSWORD" \
        --set-string "prometheus.server.probeHeaders[0].name=Authorization" \
        --set-string "prometheus.server.probeHeaders[0].value=Basic ${PROMETHEUS_AUTH_TOKEN}" \
        --set grafana.enabled=true \
        --set grafana.adminUser="$GRAFANA_ADMIN_USER" \
        --set grafana.adminPassword="$GRAFANA_ADMIN_PASSWORD" \
        --set grafana.env.PROMETHEUS_ADMIN_USER="$PROMETHEUS_ADMIN_USER" \
        --set grafana.env.PROMETHEUS_ADMIN_PASSWORD="$PROMETHEUS_ADMIN_PASSWORD" \
        --set loki.enabled=true \
        --set promtail.enabled=true \
        --set litellm.prometheus.enabled=true > /dev/null

    echo "✅ Template validation and configuration checks passed successfully!"
}

# Function to simulate deployment on cluster (dry-run)
dry_run() {
    local target="all"
    if [ "$1" = "--deploy" ]; then
        target="services"
    elif [ "$1" = "--deploy-all" ]; then
        target="all"
    elif [ -n "$1" ]; then
        echo "❌ Unknown dry-run target: $1"
        show_usage
    fi

    echo "🚀 Running validate step first..."
    validate

    echo "🔄 Checking Kubernetes context..."
    set_kube_context

    if [ "$target" = "all" ]; then
        echo "📦 Simulating deployment of web ingress (dry-run)..."
        helm upgrade --install web-ingress charts/web_ingress/ \
            -n web-services \
            --create-namespace \
            --set certificateArn="$CERTIFICATE_ARN" \
            --dry-run
    fi

    echo "📦 Simulating deployment of web services (dry-run)..."
    helm upgrade --install web-services charts/web_services/ \
        -n web-services --timeout 15m --debug \
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
        --set litellm.secrets.sealionApiKey="$SEALION_API_KEY" \
        --set litellm.secrets.vllmApiKeyIntel="$VLLM_API_KEY_INTEL" \
        --set litellm.secrets.lagoApiKey="$LAGO_API_KEY" \
        --set litellm.secrets.infomaniakApiKey="$INFOMANIAK_API_KEY" \
        --set litellm.secrets.bielikApiKey="$BIELIK_API_KEY" \
        --set litellm.secrets.cscsApiKey="$CSCS_API_KEY" \
        --set litellm.lago.enabled=true \
        --set lago.enabled=true \
        --set lago.global.databaseUrl="$LAGO_DATABASE_URL" \
        --set lago.global.redisUrl="$LAGO_REDIS_URL" \
        --set prometheus.enabled=true \
        --set prometheus.adminUser="$PROMETHEUS_ADMIN_USER" \
        --set prometheus.adminPassword="$PROMETHEUS_ADMIN_PASSWORD" \
        --set-string "prometheus.server.probeHeaders[0].name=Authorization" \
        --set-string "prometheus.server.probeHeaders[0].value=Basic ${PROMETHEUS_AUTH_TOKEN}" \
        --set grafana.enabled=true \
        --set grafana.adminUser="$GRAFANA_ADMIN_USER" \
        --set grafana.adminPassword="$GRAFANA_ADMIN_PASSWORD" \
        --set grafana.env.PROMETHEUS_ADMIN_USER="$PROMETHEUS_ADMIN_USER" \
        --set grafana.env.PROMETHEUS_ADMIN_PASSWORD="$PROMETHEUS_ADMIN_PASSWORD" \
        --set loki.enabled=true \
        --set promtail.enabled=true \
        --set litellm.prometheus.enabled=true \
        --dry-run

    echo "✅ Cluster dry-run simulation completed successfully!"
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
elif [ "$1" = "--validate" ]; then
    validate
elif [ "$1" = "--dry-run" ]; then
    dry_run "$2"
else
    show_usage
fi

echo "Check the pods and if needed do a: kubectl rollout restart deployment/litellm -n web-services"
echo "Check the pods and if needed do a: kubectl rollout restart deployment/openwebui -n web-services"