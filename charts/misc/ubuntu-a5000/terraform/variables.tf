variable "exoscale_api_key" {
  description = "Exoscale API key"
  type        = string
  sensitive   = true
}

variable "exoscale_api_secret" {
  description = "Exoscale API secret"
  type        = string
  sensitive   = true
}

variable "zone" {
  description = "Exoscale zone"
  type        = string
  default     = "ch-gva-2"
}

variable "cluster_name" {
  description = "Name of the SKS cluster"
  type        = string
  default     = "vllm-inference-cluster"
}

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "production"
}

variable "gpu_instance_type" {
  description = "Instance type for GPU nodes (A5000)"
  type        = string
  default     = "gpu3.large"
  validation {
    condition = contains([
      "gpu3.large",
      "gpu3.xlarge", 
      "gpu3.2xlarge"
    ], var.gpu_instance_type)
    error_message = "GPU instance type must be one of: gpu3.large, gpu3.xlarge, gpu3.2xlarge."
  }
}

variable "cpu_instance_type" {
  description = "Instance type for CPU nodes"
  type        = string
  default     = "standard.large"
}

variable "initial_node_count" {
  description = "Initial number of GPU nodes"
  type        = number
  default     = 2
  validation {
    condition     = var.initial_node_count >= 1 && var.initial_node_count <= 10
    error_message = "Initial node count must be between 1 and 10."
  }
}

variable "cpu_node_count" {
  description = "Number of CPU nodes for system workloads"
  type        = number
  default     = 2
}

variable "node_disk_size" {
  description = "Disk size for GPU nodes in GB"
  type        = number
  default     = 200
  validation {
    condition     = var.node_disk_size >= 50
    error_message = "Node disk size must be at least 50 GB."
  }
}

variable "vllm_api_key" {
  description = "API key for vLLM authentication"
  type        = string
  sensitive   = true
  default     = ""
}

variable "huggingface_token" {
  description = "Hugging Face token for model downloads"
  type        = string
  sensitive   = true
  default     = ""
}

variable "model_repository" {
  description = "Model repository/path (e.g., S3 bucket or HuggingFace model)"
  type        = string
  default     = ""
}

variable "max_model_len" {
  description = "Maximum model length for vLLM"
  type        = number
  default     = 4096
}

variable "tensor_parallel_size" {
  description = "Tensor parallel size for multi-GPU inference"
  type        = number
  default     = 1
}

variable "enable_metrics" {
  description = "Enable Prometheus metrics collection"
  type        = bool
  default     = true
}

variable "enable_autoscaling" {
  description = "Enable horizontal pod autoscaling"
  type        = bool
  default     = true
}

variable "min_replicas" {
  description = "Minimum number of vLLM replicas"
  type        = number
  default     = 1
}

variable "max_replicas" {
  description = "Maximum number of vLLM replicas"
  type        = number
  default     = 5
}