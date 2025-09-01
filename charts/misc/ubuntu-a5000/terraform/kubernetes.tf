resource "kubernetes_namespace" "vllm" {
  metadata {
    name = "vllm"
    labels = {
      name = "vllm"
    }
  }
  
  depends_on = [exoscale_sks_nodepool.gpu_nodes]
}

resource "kubernetes_secret" "vllm_config" {
  metadata {
    name      = "vllm-config"
    namespace = kubernetes_namespace.vllm.metadata[0].name
  }

  data = {
    VLLM_API_KEY    = var.vllm_api_key
    HF_TOKEN        = var.huggingface_token
    MODEL_PATH      = var.model_repository
  }

  type = "Opaque"
}

resource "kubernetes_config_map" "vllm_config" {
  metadata {
    name      = "vllm-config"
    namespace = kubernetes_namespace.vllm.metadata[0].name
  }

  data = {
    MAX_MODEL_LEN         = tostring(var.max_model_len)
    TENSOR_PARALLEL_SIZE  = tostring(var.tensor_parallel_size)
    GPU_MEMORY_UTILIZATION = "0.9"
    TRUST_REMOTE_CODE     = "true"
    SERVED_MODEL_NAME     = "apertus"
    HOST                  = "0.0.0.0"
    PORT                  = "8000"
  }
}

resource "kubernetes_deployment" "vllm" {
  metadata {
    name      = "vllm-apertus"
    namespace = kubernetes_namespace.vllm.metadata[0].name
    labels = {
      app     = "vllm"
      model   = "apertus"
    }
  }

  spec {
    replicas = var.min_replicas

    selector {
      match_labels = {
        app   = "vllm"
        model = "apertus"
      }
    }

    template {
      metadata {
        labels = {
          app   = "vllm"
          model = "apertus"
        }
      }

      spec {
        node_selector = {
          "node-type" = "gpu"
        }

        toleration {
          key      = "nvidia.com/gpu"
          operator = "Equal"
          value    = "true"
          effect   = "NoSchedule"
        }

        container {
          image = "vllm/vllm-openai:latest"
          name  = "vllm"

          args = [
            "--model", "/models",
            "--served-model-name", "apertus",
            "--host", "0.0.0.0",
            "--port", "8000",
            "--max-model-len", "$(MAX_MODEL_LEN)",
            "--tensor-parallel-size", "$(TENSOR_PARALLEL_SIZE)",
            "--gpu-memory-utilization", "$(GPU_MEMORY_UTILIZATION)",
            "--trust-remote-code",
            "--api-key", "$(VLLM_API_KEY)"
          ]

          port {
            container_port = 8000
            name          = "http"
          }

          env {
            name = "VLLM_API_KEY"
            value_from {
              secret_key_ref {
                name = kubernetes_secret.vllm_config.metadata[0].name
                key  = "VLLM_API_KEY"
              }
            }
          }

          env {
            name = "HF_TOKEN"
            value_from {
              secret_key_ref {
                name = kubernetes_secret.vllm_config.metadata[0].name
                key  = "HF_TOKEN"
              }
            }
          }

          env_from {
            config_map_ref {
              name = kubernetes_config_map.vllm_config.metadata[0].name
            }
          }

          resources {
            limits = {
              "nvidia.com/gpu" = "1"
              memory = "24Gi"
              cpu    = "8"
            }
            requests = {
              "nvidia.com/gpu" = "1"
              memory = "16Gi"
              cpu    = "4"
            }
          }

          volume_mount {
            name       = "model-storage"
            mount_path = "/models"
          }

          volume_mount {
            name       = "shm"
            mount_path = "/dev/shm"
          }

          readiness_probe {
            http_get {
              path = "/health"
              port = "8000"
            }
            initial_delay_seconds = 60
            period_seconds       = 10
            timeout_seconds      = 5
            failure_threshold    = 3
          }

          liveness_probe {
            http_get {
              path = "/health"
              port = "8000"
            }
            initial_delay_seconds = 120
            period_seconds       = 30
            timeout_seconds      = 10
            failure_threshold    = 3
          }
        }

        init_container {
          name  = "model-downloader"
          image = "amazon/aws-cli:latest"
          
          command = ["/bin/sh", "-c"]
          args = [
            <<-EOT
            if [ -n "$MODEL_PATH" ]; then
              echo "Downloading model from $MODEL_PATH"
              # Add your model download logic here
              # Example for S3: aws s3 sync s3://bucket/path /models/
              # Example for HTTP: wget -r -np -nH --cut-dirs=3 $MODEL_PATH -P /models/
            else
              echo "No model path specified, using pre-built image model"
            fi
            EOT
          ]

          env {
            name = "MODEL_PATH"
            value_from {
              secret_key_ref {
                name = kubernetes_secret.vllm_config.metadata[0].name
                key  = "MODEL_PATH"
              }
            }
          }

          volume_mount {
            name       = "model-storage"
            mount_path = "/models"
          }
        }

        volume {
          name = "model-storage"
          empty_dir {
            size_limit = "100Gi"
          }
        }

        volume {
          name = "shm"
          empty_dir {
            medium = "Memory"
            size_limit = "8Gi"
          }
        }
      }
    }
  }

  depends_on = [
    kubernetes_config_map.vllm_config,
    kubernetes_secret.vllm_config
  ]
}

resource "kubernetes_service" "vllm" {
  metadata {
    name      = "vllm-service"
    namespace = kubernetes_namespace.vllm.metadata[0].name
    labels = {
      app = "vllm"
    }
  }

  spec {
    selector = {
      app = "vllm"
    }

    port {
      name        = "http"
      port        = 8000
      target_port = "8000"
      protocol    = "TCP"
    }

    type = "ClusterIP"
  }
}