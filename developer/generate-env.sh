#!/bin/bash
set -eo pipefail

ENV_FILE=".env"

if [ -f "$ENV_FILE" ]; then
    echo "⚠️  $ENV_FILE already exists! Skipping generation to avoid overwriting existing secrets."
    exit 0
fi

echo "Generating $ENV_FILE with default/random secrets..."

# Generate keys
WEBUI_SECRET_KEY=$(openssl rand -hex 32 2>/dev/null || echo "webui_default_secret_key_change_me_12345")
LITELLM_SALT_KEY=$(openssl rand -hex 16 2>/dev/null || echo "litellm_default_salt_key_change_me_12345")
LAGO_SECRET_KEY_BASE=$(openssl rand -hex 64 2>/dev/null || echo "lago_default_secret_key_base_change_me_1234567890")
LAGO_ENCRYPTION_PRIMARY_KEY=$(openssl rand -hex 16 2>/dev/null || echo "lago_primary_key_16_bytes")
LAGO_ENCRYPTION_DETERMINISTIC_KEY=$(openssl rand -hex 16 2>/dev/null || echo "lago_determ_key_16_bytes")
LAGO_ENCRYPTION_KEY_DERIVATION_SALT=$(openssl rand -hex 16 2>/dev/null || echo "lago_salt_key_16_bytes")
LAGO_RSA_PRIVATE_KEY=$(openssl genrsa 2048 2>/dev/null | openssl base64 -A || echo "rsa_private_key_placeholder")

cat <<EOF > "$ENV_FILE"
# ==========================================
# Docker Compose Configurations
# ==========================================
POSTGRES_DB=lago
POSTGRES_USER=lago
POSTGRES_PASSWORD=password
POSTGRES_PORT=5432
REDIS_PORT=6379
PGADMIN_DEFAULT_EMAIL=admin@publicai.co
PGADMIN_DEFAULT_PASSWORD=password

# ==========================================
# Kubernetes Setup Variables (.env)
# ==========================================
EXPECTED_KUBE_CONTEXT=publicai-local
LICENSE_KEY=your-license-key
WEBUI_SECRET_KEY=$WEBUI_SECRET_KEY
CERTIFICATE_ARN=arn:aws:acm:eu-central-2:123456789012:certificate/placeholder

# DB/Redis URLs pointing to external Kubernetes services (defined in external-db-services.yaml)
OWUI_DATABASE_URL=postgresql://openwebui:password@external-postgres:5432/openwebui?sslmode=disable
OWUI_REDIS_URL=redis://external-redis:6379/2

LITELLM_DATABASE_URL=postgresql://llmproxy:password@external-postgres:5432/litellm?sslmode=disable
LITELLM_REDIS_URL=redis://external-redis:6379/1

LAGO_DATABASE_URL=postgresql://lago:password@external-postgres:5432/lago?sslmode=disable
LAGO_REDIS_URL=redis://external-redis:6379/0

# OAuth / OpenID (Use placeholders)
OPENID_PROVIDER_URL=https://keycloak.example.com/auth/realms/publicai
OAUTH_CLIENT_ID=publicai-client
OAUTH_CLIENT_SECRET=client-secret-placeholder
OPENID_REDIRECT_URI=https://chat.publicai.co/oauth/callback

# LiteLLM Master / Salt Key
LITELLM_API_KEY=sk-litellm-master-key-1234567890
LITELLM_SALT_KEY=$LITELLM_SALT_KEY

# API Key Placeholders (Replace with actual ones)
TOGETHER_API_KEY=together-api-key-placeholder
SEALION_API_KEY=sealion-api-key-placeholder
VLLM_API_KEY=vllm-api-key-placeholder
VLLM_API_KEY_EXOSCALE=vllm-exoscale-key-placeholder
VLLM_API_KEY_ANU=vllm-anu-key-placeholder
VLLM_API_KEY_CSCS=vllm-cscs-key-placeholder
VLLM_API_KEY_CUDO=vllm-cudo-key-placeholder
VLLM_API_KEY_HH=vllm-hh-key-placeholder
VLLM_API_KEY_INTEL=vllm-intel-key-placeholder
CIRRASCALE_API_KEY=cirrascale-key-placeholder
PARASCALE_API_KEY=parascale-key-placeholder
MULTIVERSE_API_KEY=multiverse-key-placeholder
DICTA_API_KEY=dicta-key-placeholder
INFOMANIAK_API_KEY=infomaniak-key-placeholder
DEEPINFRA_API_KEY=deepinfra-key-placeholder
PHOENIQS_API_KEY=phoeniqs-key-placeholder

# Lago Secrets
LAGO_API_KEY=lago-api-key-placeholder
LAGO_SECRET_KEY_BASE=$LAGO_SECRET_KEY_BASE
LAGO_ENCRYPTION_PRIMARY_KEY=$LAGO_ENCRYPTION_PRIMARY_KEY
LAGO_ENCRYPTION_DETERMINISTIC_KEY=$LAGO_ENCRYPTION_DETERMINISTIC_KEY
LAGO_ENCRYPTION_KEY_DERIVATION_SALT=$LAGO_ENCRYPTION_KEY_DERIVATION_SALT
LAGO_RSA_PRIVATE_KEY=$LAGO_RSA_PRIVATE_KEY
EOF

echo "✅ $ENV_FILE generated successfully!"
