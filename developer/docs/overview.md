# Public AI System Architecture & Charts Guide

Welcome to the team! This directory (`/charts`) contains the infrastructure-as-code (IaC) definitions that deploy and manage the entire Public AI platform on Kubernetes (Amazon EKS).

As a new developer, it's crucial to understand how our various microservices, language models, and infrastructure components fit together. We use **Helm** to template and manage these Kubernetes resources.

## 🏗 High-Level Architecture Concepts

Before diving into the specific charts, here are the foundational concepts and tooling you need to understand:

1. **Kubernetes (EKS)**: Our core orchestration platform.
2. **Helm**: We use Helm umbrella charts to group related services, making it easy to deploy entire environments with a single command and manage configurations dynamically.
3. **IRSA (IAM Roles for Service Accounts)**: We use AWS IRSA to grant specific pods (like OpenWebUI or Lago) access to AWS resources securely, without hardcoding or mounting AWS credentials.
4. **Karpenter**: We use Karpenter for dynamic node auto-provisioning. It's especially critical for scaling our expensive GPU nodes (`p4d.24xlarge`) on demand, or taking advantage of AWS Capacity Blocks.
5. **S3-Backed Volumes (CSI)**: Large model weights (70B+ parameters) are stored in S3 and mounted directly into our inference pods using the S3 CSI driver. This allows instantaneous access to massive models without downloading hundreds of gigabytes over the network on pod startup.

---

## 📂 The Charts Directory

We've split our infrastructure into four logical domains to cleanly isolate concerns.

### 1. `load-balancer`
This chart handles the foundational, cluster-wide networking components.
* **AWS Load Balancer Controller**: Listens to our Kubernetes `Ingress` objects and automatically provisions AWS Application Load Balancers (ALBs). It is configured to run on `hostNetwork` to bypass certain networking constraints and uses IRSA (`AmazonEKSLoadBalancerControllerRole`) to communicate securely with the AWS API.

### 2. `ingress`
Instead of scattering Ingress definitions across every microservice, we centralize our public routing layer here.
* Uses the `alb-web` ingress class.
* Connects hostnames to their respective backend services using **IP-mode routing** (traffic routes straight from the ALB to the Pod IP, bypassing `kube-proxy` for lower latency).
* **Routes Managed**:
  * `chat.publicai.co` -> OpenWebUI
  * `api-internal.publicai.co` -> LiteLLM (Internal AI Gateway)
  * `lago.publicai.co` & `lago-api.publicai.co` -> Lago Billing

### 3. `llm_services`
This is the core of our AI offering—the production inference stack.
* **vLLM Stack**: We use [vLLM](https://github.com/vllm-project/vllm) for high-throughput, memory-efficient LLM serving.
* **Model Configuration**: We currently serve our custom `apertus-70b-instruct` model.
* **GPU & Tensor Parallelism**: Serving a 70B model requires massive VRAM. We request 8 GPUs per instance and use a `tensorParallelSize` of 8 to split the model execution across them seamlessly.
* **Custom Chat Templates & Tools**: You'll notice `apertus_tool_parser.py` and `apertus_chat_template.jinja` in this folder. These are injected into the vLLM pods via a ConfigMap. This teaches vLLM how to parse our custom tool-calling format and format prompts natively for the Apertus architecture.
* **Karpenter Integration**: A dedicated `gpu` node pool is defined here to spin up `p4d` instances specifically when inference pods are scheduled. Taints prevent normal web services from accidentally scheduling onto these expensive instances.

### 4. `web_services`
This is an **umbrella chart** that pulls together all the end-user and backend microservices.
* **OpenWebUI**: The main chat frontend users interact with. Configured to autoscale (HPA) between 1-3 replicas based on load (75% CPU / 85% Memory) and uses S3 for user file uploads.
* **Tika**: An Apache Tika service used for extracting text from PDFs and documents that users upload. It's configured with heavy memory limits (2Gi) because OCR and processing large PDFs can easily OOM kill smaller pods.
* **LiteLLM**: The AI Gateway. It normalizes APIs and routes traffic securely to our underlying vLLM instances.
* **Lago**: Our robust billing and metering engine. It's a large architecture with multiple dedicated background workers (billing, clock, events, payment, pdf, webhook) all scaled individually. It relies on our external Postgres and Redis databases.
* **SearXNG**: A metasearch engine (currently disabled) intended to back our web-search tool capabilities.

## 🔐 Authentication & API Flow

Understanding how users and developers authenticate, and how that identity propagates through the system, is critical. We use different Identity Providers (IdPs) depending on the audience:

### 1. End Users (Web Portal)
* **Identity Provider**: **AWS Cognito**
* **Flow**: When a user visits `chat.publicai.co`, OpenWebUI handles the OAuth/OpenID Connect flow. The configuration for this (Client ID, Secret, Provider URL) is injected into OpenWebUI's secrets via the `web.sh` deployment script.
* **Internal Tracking**: When OpenWebUI forwards an inference request to LiteLLM (the internal AI gateway), it passes the user's identity along using `X-OpenWebUI-User-*` HTTP headers.

### 2. Developers (API & Platform)
* **Identity Provider**: **Auth0**
* **Developer Portal**: Developers log into `platform.publicai.co` (built with Zudoku) using Auth0.
* **API Gateway (Zuplo)**: Developers generate API keys from the portal to access `api.publicai.co`. Our SaaS API Gateway, Zuplo, validates these API keys, enforces rate limits, and checks budgets. 
* **Internal Routing**: Once Zuplo validates a developer's request, it proxies the traffic to our internal LiteLLM ingress (`api-internal.publicai.co`).

### ⚠️ Are Cognito and Auth0 Unified?
**No, they are completely separate, disjoint systems.** We use them to serve two different audiences with very different requirements.

* **Where is the identity data stored?**
  * **End-User Data**: Stored in **AWS Cognito** (passwords, emails). OpenWebUI creates a "shadow profile" in its own PostgreSQL database—mapped by the unique Cognito ID—to save chat histories and user preferences.
  * **Developer Data**: Stored in **Auth0**. This is optimized for B2B developer workflows, API key generation, and machine-to-machine OAuth flows which Zuplo relies on.
* **Where do they unify?**
  * The identities only unify at the **billing layer (Lago)**. Lago is IdP-agnostic. It simply receives an ID from LiteLLM (which originated from either Cognito or Auth0) and maps it to a single `external_customer_id` to track token usage and generate invoices.

### 3. Billing & Metering (Lago)
Whether a request originates from an end-user on OpenWebUI or a developer hitting the API via Zuplo, it ultimately flows through **LiteLLM**. 
* LiteLLM acts as the central chokepoint. It is configured to integrate directly with **Lago** (our billing engine). 
* LiteLLM reports token usage (prompt and completion tokens) asynchronously to Lago, attaching the usage to the specific user or developer identity passed down from the upstream services.

---

## 🤖 AI Gateway & Model Routing (LiteLLM)

OpenWebUI serves as the user interface but **does not know where models are hosted**. Instead, it acts as a client connected to **LiteLLM**, our internal AI Gateway. 

### How Model Discovery Works
1. When OpenWebUI loads, it makes an HTTP request to LiteLLM's standard `/v1/models` endpoint.
2. LiteLLM responds with the full list of available models, which dynamically populates OpenWebUI's model dropdown. *(Note: The connection between OpenWebUI and LiteLLM is saved in OpenWebUI's internal Postgres database, not hardcoded in its Kubernetes YAML.)*

### Source of Truth for Routing
The actual mapping of user-facing model names to backend endpoints is strictly managed inside `charts/web_services/charts/litellm/values.yaml` under `config.models`.

LiteLLM handles all complex routing logic, including:
* **External SaaS Providers**: Routing `meta-llama/Llama-3.2-3B-Instruct` to AWS Bedrock.
* **Bare-Metal & Managed Partners**: Routing `swiss-ai/apertus-70b-instruct` to external endpoints like Infomaniak, CSCS, or PHOENIQS.
* **Load Balancing**: The same model name can be defined multiple times pointing to different infrastructure endpoints. LiteLLM uses a `simple-shuffle` routing strategy to randomly distribute traffic across healthy endpoints, providing automatic load balancing and failover entirely hidden from OpenWebUI.


### 1. How OpenWebUI Discovers Models
OpenWebUI is designed to talk to any standard OpenAI-compatible API. In our architecture, it points to the internal `litellm-service`. 
When OpenWebUI boots up (or when a user refreshes the page), it makes a standard HTTP GET request to LiteLLM's `/v1/models` endpoint. LiteLLM responds with a list of all configured models, and OpenWebUI dynamically populates its dropdown menu. 

*(Note: The connection from OpenWebUI to LiteLLM is saved in OpenWebUI's Persistent Config within its Postgres database, rather than being hardcoded in its Kubernetes YAML.)*

### 2. The Source of Truth: LiteLLM's Configuration
The actual mapping of *what* models exist and *where* their endpoints are located is strictly managed by **LiteLLM**. 

If you look at `charts/web_services/charts/litellm/values.yaml`, there is a massive `config.models` list. This is where the magic happens. LiteLLM maps a clean, user-facing `model_name` to complex backend routing logic:

**Example 1: Routing to External Partners**
```yaml
- model_name: swiss-ai/apertus-70b-instruct
  litellm_params:
    model: openai/swiss-ai/Apertus-70B-Instruct-2509
    api_base: https://api.infomaniak.com/2/ai/106744/openai/v1
    api_key: "os.environ/INFOMANIAK_API_KEY"
```

**Example 2: Routing to AWS Bedrock**
```yaml
- model_name: meta-llama/Llama-3.2-3B-Instruct
  litellm_params:
    model: bedrock/eu.meta.llama3-2-3b-instruct-v1:0
    aws_region_name: eu-central-1
```

### 3. Load Balancing & Failover
Because LiteLLM sits in the middle, you'll notice in `litellm/values.yaml` that the **same `model_name`** (e.g., `swiss-ai/apertus-8b-instruct`) is defined multiple times pointing to different endpoints (like Intel, CSCS, and PHOENIQS). 

LiteLLM is configured with a `routingStrategy: "simple-shuffle"`. When OpenWebUI requests a completion for `apertus-8b-instruct`, LiteLLM randomly shuffles between the available, healthy endpoints to balance the load and handle failovers automatically. OpenWebUI is completely oblivious to this complexity!

---

## 🗄️ Database Architecture & State Management

In this project, we rely entirely on **AWS Managed Data Layers** (RDS, ElastiCache, S3). No stateful databases run natively as pods inside our Kubernetes cluster. This ensures high availability and easier disaster recovery.

Here is the rundown of the databases used, where they run, and what they are responsible for:

### 1. PostgreSQL (AWS RDS)
We use separate logical databases (often on the same or separate RDS instances depending on the environment) for different services:
* **OpenWebUI DB**: Uses the `pgvector` extension. It stores end-user accounts (shadow profiles linked to Cognito), chat histories, saved prompts, persistent configuration, and vector embeddings for RAG functionality.
* **LiteLLM DB**: Uses Prisma. It stores API keys for developers, usage budgets, team mappings, and routing configurations.
* **Lago DB**: The core database for the Lago billing engine. It stores invoicing data, customer billing metrics, and payment gateway states.

### 2. Redis (AWS ElastiCache)
Redis is heavily utilized across the stack for ephemeral state and queueing:
* **OpenWebUI Redis**: Manages WebSocket connections for real-time chat streaming across multiple OpenWebUI replicas.
* **LiteLLM Redis**: Acts as a high-speed caching layer for identical LLM requests and handles strict rate-limiting for developers.
* **Lago Redis**: The backbone of Lago's worker architecture. It queues events for billing, PDF generation, webhooks, and payment processing workers.

### 3. S3 (AWS Simple Storage Service)
S3 is used globally for heavy object storage:
* **User Uploads**: OpenWebUI stores user-uploaded files, images, and documents in S3 under the `uploads/` prefix.
* **LLM Weights**: vLLM instances mount S3 buckets using the S3 CSI driver to load massive 70B parameter models at runtime.
* **Billing Documents**: Lago utilizes S3 to store generated PDF invoices.

---

## 🛠 Everyday Developer Tasks

* **Adding a new environment variable to a web service**: Modify the corresponding block in `charts/web_services/values.yaml` (e.g. under the `open-webui` or `lago` section).
* **Updating the Apertus model version**: Go to `charts/llm_services/values.yaml`, update the `modelURL` path pointing to the new S3 directory, and ensure the `vllmConfig` matches any new architectural requirements.
* **Scaling behavior**: Modify the resources `requests/limits` or the autoscaling rules in the specific service's `values.yaml` configuration block.

Remember, everything here ultimately deploys to AWS EKS, so look out for how we link IAM roles (via `serviceAccount.annotations`) and handle persistent storage!
