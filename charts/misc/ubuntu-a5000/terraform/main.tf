terraform {
  required_providers {
    exoscale = {
      source  = "exoscale/exoscale"
      version = "~> 0.59"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.23"
    }
    helm = {
      source  = "hashicorp/helm"
      version = "~> 2.11"
    }
  }
  required_version = ">= 1.0"
}

provider "exoscale" {
  key    = var.exoscale_api_key
  secret = var.exoscale_api_secret
  zone   = var.zone
}

data "exoscale_zones" "available" {}

resource "exoscale_sks_cluster" "vllm_cluster" {
  zone         = var.zone
  name         = var.cluster_name
  description  = "vLLM GPU cluster for model inference"
  service_level = "pro"
  
  tags = {
    Environment = var.environment
    Project     = "vllm-inference"
    ManagedBy   = "terraform"
  }
}

resource "exoscale_sks_nodepool" "gpu_nodes" {
  cluster_id   = exoscale_sks_cluster.vllm_cluster.id
  zone         = var.zone
  name         = "gpu-a5000-pool"
  description  = "GPU nodes for vLLM inference"
  instance_type = var.gpu_instance_type
  size         = var.initial_node_count
  
  disk_size = var.node_disk_size
  
  tags = {
    NodeType = "gpu"
    GPU      = "a5000"
  }

  taints = {
    "nvidia.com/gpu" = "true:NoSchedule"
  }

  labels = {
    "node-type" = "gpu"
    "gpu-type"  = "a5000"
  }
}

resource "exoscale_sks_nodepool" "cpu_nodes" {
  cluster_id   = exoscale_sks_cluster.vllm_cluster.id
  zone         = var.zone
  name         = "cpu-pool"
  description  = "CPU nodes for system workloads"
  instance_type = var.cpu_instance_type
  size         = var.cpu_node_count
  
  disk_size = 50

  labels = {
    "node-type" = "cpu"
  }
}

data "exoscale_sks_cluster_kubeconfig" "vllm_cluster" {
  cluster_id = exoscale_sks_cluster.vllm_cluster.id
  zone       = var.zone
  user       = "terraform"
  groups     = ["system:masters"]
}

provider "kubernetes" {
  host                   = data.exoscale_sks_cluster_kubeconfig.vllm_cluster.host
  cluster_ca_certificate = base64decode(data.exoscale_sks_cluster_kubeconfig.vllm_cluster.cluster_ca_certificate)
  token                 = data.exoscale_sks_cluster_kubeconfig.vllm_cluster.token
}

provider "helm" {
  kubernetes {
    host                   = data.exoscale_sks_cluster_kubeconfig.vllm_cluster.host
    cluster_ca_certificate = base64decode(data.exoscale_sks_cluster_kubeconfig.vllm_cluster.cluster_ca_certificate)
    token                 = data.exoscale_sks_cluster_kubeconfig.vllm_cluster.token
  }
}