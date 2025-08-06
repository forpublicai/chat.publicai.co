# Open WebUI Production Setup

This repository contains the production deployment configuration for Open WebUI with AI services integration on DigitalOcean infrastructure.

## Architecture Overview

The setup consists of three main components deployed across multiple DigitalOcean droplets:

### 🌐 Web Services (`web_services/`)
- **Nginx Reverse Proxy**: SSL termination and traffic routing
- **Open WebUI**: Main application (app.publicai.company)
- **Grafana**: Observability and telemetry dashboard (grafana.publicai.company)

### 🤖 AI Services (`ai_services/`)
- **Envoy Proxy**: AI API gateway for model requests
- Routes to local models (BGE-M3, BGE-reranker) and external APIs

### 🗄️ Data Layer
- **Managed PostgreSQL**: Primary database
- **Managed Redis**: WebSocket broker and caching
- **DigitalOcean Spaces**: S3-compatible file storage

### 🔗 External Integrations
- **Cloudflare CDN**: Edge caching and DDoS protection
- **External AI Providers**: SwissCom API, Sea Lion API
- **Vercel**: Marketing site (publicai.company)

## Project Structure

```
├── README.md
├── ai_services/
│   ├── docker-compose.yml    # Envoy AI gateway
│   └── envoy.yaml           # Envoy proxy configuration
├── web_services/
│   ├── docker-compose.yml    # Nginx, Open WebUI, Grafana
│   └── nginx.conf           # Nginx reverse proxy config
├── architecture_diagrams/
│   ├── architecture.d2      # D2 diagram source
│   └── architecture.svg     # Generated architecture diagram
└── llm_services/            # Future LLM model services
```

## Environment Variables

Create a `.env` file in the root directory with the following variables:

```bash
# Open WebUI Configuration
LICENSE_KEY=your_license_key
WEBUI_SECRET_KEY=your_secret_key

# Database & Redis
DATABASE_URL=postgresql://user:pass@host:port/db
REDIS_URL=redis://user:pass@host:port

# S3 Storage (DigitalOcean Spaces)
S3_ACCESS_KEY_ID=your_access_key
S3_SECRET_ACCESS_KEY=your_secret_key

# AI API Keys
SEALION_API_KEY=your_sealion_key
```
