# vLLM on Exoscale SKS Terraform Configuration

This Terraform configuration deploys vLLM (your Apertus model) on Exoscale's Kubernetes Service (SKS) with GPU support, auto-scaling, and monitoring.

## Architecture

```
Exoscale SKS Cluster
├── GPU Node Pool (A5000 GPUs)
│   └── vLLM Pods with GPU acceleration
├── CPU Node Pool 
│   ├── Ingress Controller (nginx)
│   ├── Cert Manager (Let's Encrypt)
│   ├── Metrics Server
│   └── Monitoring Stack (Prometheus/Grafana)
├── Load Balancer (Exoscale NLB)
└── Auto-scaling (HPA + Cluster Autoscaler)
```

## Features

- **GPU-accelerated inference** with NVIDIA A5000 GPUs
- **Horizontal Pod Autoscaling** based on CPU/memory metrics
- **Load balancing** across multiple model instances
- **HTTPS termination** with automatic SSL certificates
- **Monitoring** with Prometheus and Grafana
- **Resource isolation** with node selectors and taints

## Prerequisites

1. **Exoscale Account** with API credentials
2. **Terraform** >= 1.0
3. **kubectl** for cluster management
4. **exo CLI** (optional, for easier cluster access)

## Quick Start

### 1. Configure Variables

```bash
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars with your values
```

### 2. Initialize and Deploy

```bash
terraform init
terraform plan
terraform apply
```

### 3. Configure kubectl

```bash
# Get kubeconfig
terraform output -raw kubeconfig > ~/.kube/config-vllm
export KUBECONFIG=~/.kube/config-vllm

# Or use exo CLI
exo sks kubeconfig vllm-inference-cluster ch-gva-2 --group system:masters kube-admin
```

### 4. Test the API

```bash
# Get the external URL
terraform output vllm_external_url

# Test the API
curl -X POST "https://vllm.your-cluster.exoscale.com/v1/completions" \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "apertus",
    "prompt": "Hello, how are you?",
    "max_tokens": 100,
    "temperature": 0.7
  }'
```

## Configuration Options

### Instance Types

| Type | GPUs | Memory | Use Case |
|------|------|--------|----------|
| `gpu3.large` | 1x A5000 | 32GB | Single model inference |
| `gpu3.xlarge` | 2x A5000 | 64GB | Multi-GPU or larger models |
| `gpu3.2xlarge` | 4x A5000 | 128GB | Very large models |

### Model Loading

The configuration supports multiple model loading methods:

1. **S3 Bucket**: Set `model_repository = "s3://bucket/path"`
2. **Hugging Face**: Set `model_repository = "huggingface/model-name"`
3. **Pre-built Image**: Leave `model_repository = ""` and bake model into container image

### Auto-scaling

- **HPA**: Scales pods based on CPU/memory usage (70%/80% targets)
- **Scale-up**: Max 100% increase or 2 pods per minute
- **Scale-down**: Max 50% decrease or 1 pod per minute with 10min stabilization

## Monitoring

Access monitoring dashboards:

```bash
# Port forward to Grafana
kubectl port-forward -n monitoring svc/prometheus-grafana 3000:80

# Port forward to Prometheus
kubectl port-forward -n monitoring svc/prometheus-prometheus 9090:9090
```

Default Grafana credentials: `admin` / `admin123`

## Useful Commands

```bash
# View running pods
kubectl get pods -n vllm -o wide

# Scale manually
kubectl scale deployment vllm-apertus --replicas=3 -n vllm

# View logs
kubectl logs -f deployment/vllm-apertus -n vllm

# Check HPA status
kubectl describe hpa vllm-hpa -n vllm

# View node status
kubectl get nodes --show-labels

# Port forward for direct access
kubectl port-forward service/vllm-service 8080:8000 -n vllm
```

## Cost Optimization

1. **Right-size instances**: Start with `gpu3.large` and scale up if needed
2. **Enable autoscaling**: Automatically scale down during low usage
3. **Monitor usage**: Use Grafana dashboards to optimize resource allocation
4. **Spot instances**: Consider using spot instances for non-critical workloads

## Security

- **Network isolation**: Separate GPU and CPU node pools
- **RBAC**: Proper Kubernetes role-based access control
- **TLS termination**: Automatic SSL certificates via Let's Encrypt
- **API authentication**: Bearer token authentication for vLLM API

## Troubleshooting

### GPU nodes not scheduling pods
```bash
kubectl describe nodes | grep -A 5 "Taints"
kubectl get pods -n vllm -o wide
```

### Model loading issues
```bash
kubectl logs -f deployment/vllm-apertus -n vllm -c model-downloader
```

### Ingress not working
```bash
kubectl get ingress -n vllm
kubectl describe ingress vllm-ingress -n vllm
```

### Scaling issues
```bash
kubectl get hpa -n vllm
kubectl describe hpa vllm-hpa -n vllm
kubectl top pods -n vllm
```

## Cleanup

```bash
terraform destroy
```

This will remove all resources including the cluster, load balancer, and persistent volumes.