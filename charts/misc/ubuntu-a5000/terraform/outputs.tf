output "cluster_id" {
  description = "The ID of the SKS cluster"
  value       = exoscale_sks_cluster.vllm_cluster.id
}

output "cluster_name" {
  description = "The name of the SKS cluster"
  value       = exoscale_sks_cluster.vllm_cluster.name
}

output "cluster_endpoint" {
  description = "The endpoint of the SKS cluster"
  value       = exoscale_sks_cluster.vllm_cluster.endpoint
}

output "kubeconfig" {
  description = "Kubeconfig for the cluster"
  value       = data.exoscale_sks_cluster_kubeconfig.vllm_cluster.kubeconfig
  sensitive   = true
}

output "gpu_nodepool_id" {
  description = "The ID of the GPU node pool"
  value       = exoscale_sks_nodepool.gpu_nodes.id
}

output "cpu_nodepool_id" {
  description = "The ID of the CPU node pool"
  value       = exoscale_sks_nodepool.cpu_nodes.id
}

output "vllm_service_url" {
  description = "Internal cluster URL for vLLM service"
  value       = "http://${kubernetes_service.vllm.metadata[0].name}.${kubernetes_namespace.vllm.metadata[0].name}.svc.cluster.local:8000"
}

output "vllm_external_url" {
  description = "External URL for vLLM API (via ingress)"
  value       = "https://vllm.${var.cluster_name}.exoscale.com"
}

output "nginx_ingress_ip" {
  description = "External IP of the nginx ingress load balancer"
  value       = helm_release.nginx_ingress.status[0].load_balancer[0].ingress[0].ip
}

output "monitoring_urls" {
  description = "URLs for monitoring services"
  value = var.enable_metrics ? {
    prometheus = "http://prometheus.monitoring.svc.cluster.local:9090"
    grafana    = "http://grafana.monitoring.svc.cluster.local:3000"
  } : {}
}

output "api_test_command" {
  description = "Example curl command to test the vLLM API"
  value = <<-EOT
    curl -X POST "https://vllm.${var.cluster_name}.exoscale.com/v1/completions" \
      -H "Authorization: Bearer ${var.vllm_api_key}" \
      -H "Content-Type: application/json" \
      -d '{
        "model": "apertus",
        "prompt": "Hello, how are you?",
        "max_tokens": 100,
        "temperature": 0.7
      }'
  EOT
}

output "deployment_info" {
  description = "Information about the deployment"
  value = {
    cluster_zone          = var.zone
    gpu_instance_type     = var.gpu_instance_type
    initial_gpu_nodes     = var.initial_node_count
    cpu_nodes            = var.cpu_node_count
    autoscaling_enabled  = var.enable_autoscaling
    metrics_enabled      = var.enable_metrics
    min_replicas         = var.min_replicas
    max_replicas         = var.max_replicas
  }
}

output "kubectl_config_command" {
  description = "Command to configure kubectl"
  value       = "exo sks kubeconfig ${exoscale_sks_cluster.vllm_cluster.name} ${var.zone} --group system:masters kube-admin"
}

output "scale_commands" {
  description = "Useful kubectl commands for scaling"
  value = {
    scale_deployment     = "kubectl scale deployment vllm-apertus --replicas=<count> -n vllm"
    get_pods            = "kubectl get pods -n vllm -o wide"
    get_nodes           = "kubectl get nodes --show-labels"
    describe_hpa        = "kubectl describe hpa vllm-hpa -n vllm"
    view_logs          = "kubectl logs -f deployment/vllm-apertus -n vllm"
    port_forward       = "kubectl port-forward service/vllm-service 8080:8000 -n vllm"
  }
}