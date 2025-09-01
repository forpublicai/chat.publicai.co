resource "helm_release" "metrics_server" {
  name       = "metrics-server"
  repository = "https://kubernetes-sigs.github.io/metrics-server/"
  chart      = "metrics-server"
  version    = "3.11.0"
  namespace  = "kube-system"

  values = [
    yamlencode({
      nodeSelector = {
        "node-type" = "cpu"
      }
      args = [
        "--cert-dir=/tmp",
        "--secure-port=4443",
        "--kubelet-preferred-address-types=InternalIP,ExternalIP,Hostname",
        "--kubelet-use-node-status-port",
        "--metric-resolution=15s"
      ]
      resources = {
        requests = {
          cpu    = "100m"
          memory = "200Mi"
        }
      }
    })
  ]

  depends_on = [exoscale_sks_nodepool.cpu_nodes]
}

resource "kubernetes_horizontal_pod_autoscaler_v2" "vllm_hpa" {
  count = var.enable_autoscaling ? 1 : 0

  metadata {
    name      = "vllm-hpa"
    namespace = kubernetes_namespace.vllm.metadata[0].name
  }

  spec {
    scale_target_ref {
      api_version = "apps/v1"
      kind        = "Deployment"
      name        = kubernetes_deployment.vllm.metadata[0].name
    }

    min_replicas = var.min_replicas
    max_replicas = var.max_replicas

    metric {
      type = "Resource"
      resource {
        name = "cpu"
        target {
          type                = "Utilization"
          average_utilization = 70
        }
      }
    }

    metric {
      type = "Resource"
      resource {
        name = "memory"
        target {
          type                = "Utilization"
          average_utilization = 80
        }
      }
    }

    behavior {
      scale_up {
        stabilization_window_seconds = 300
        select_policy               = "Max"
        policy {
          type          = "Percent"
          value         = 100
          period_seconds = 60
        }
        policy {
          type          = "Pods"
          value         = 2
          period_seconds = 60
        }
      }

      scale_down {
        stabilization_window_seconds = 600
        select_policy               = "Min"
        policy {
          type          = "Percent"
          value         = 50
          period_seconds = 60
        }
        policy {
          type          = "Pods"
          value         = 1
          period_seconds = 60
        }
      }
    }
  }

  depends_on = [
    helm_release.metrics_server,
    kubernetes_deployment.vllm
  ]
}

resource "helm_release" "prometheus" {
  count = var.enable_metrics ? 1 : 0

  name       = "prometheus"
  repository = "https://prometheus-community.github.io/helm-charts"
  chart      = "kube-prometheus-stack"
  version    = "51.2.0"
  namespace  = "monitoring"
  create_namespace = true

  values = [
    yamlencode({
      prometheus = {
        prometheusSpec = {
          nodeSelector = {
            "node-type" = "cpu"
          }
          storageSpec = {
            volumeClaimTemplate = {
              spec = {
                storageClassName = "exoscale-ssd"
                accessModes      = ["ReadWriteOnce"]
                resources = {
                  requests = {
                    storage = "50Gi"
                  }
                }
              }
            }
          }
        }
      }
      grafana = {
        nodeSelector = {
          "node-type" = "cpu"
        }
        persistence = {
          enabled          = true
          storageClassName = "exoscale-ssd"
          size             = "10Gi"
        }
        adminPassword = "admin123"
      }
      alertmanager = {
        alertmanagerSpec = {
          nodeSelector = {
            "node-type" = "cpu"
          }
        }
      }
    })
  ]

  depends_on = [exoscale_sks_nodepool.cpu_nodes]
}

resource "kubernetes_service_monitor" "vllm_metrics" {
  count = var.enable_metrics ? 1 : 0

  metadata {
    name      = "vllm-metrics"
    namespace = kubernetes_namespace.vllm.metadata[0].name
    labels = {
      app = "vllm"
    }
  }

  spec {
    selector {
      match_labels = {
        app = "vllm"
      }
    }

    endpoints {
      port     = "http"
      path     = "/metrics"
      interval = "30s"
    }
  }

  depends_on = [helm_release.prometheus]
}

resource "kubernetes_cluster_role" "node_autoscaler" {
  metadata {
    name = "cluster-autoscaler"
  }

  rule {
    api_groups = [""]
    resources  = ["events", "endpoints"]
    verbs      = ["create", "patch"]
  }

  rule {
    api_groups = [""]
    resources  = ["pods/eviction"]
    verbs      = ["create"]
  }

  rule {
    api_groups = [""]
    resources  = ["pods/status"]
    verbs      = ["update"]
  }

  rule {
    api_groups     = [""]
    resources      = ["endpoints"]
    resource_names = ["cluster-autoscaler"]
    verbs          = ["get", "update"]
  }

  rule {
    api_groups = [""]
    resources  = ["nodes"]
    verbs      = ["watch", "list", "get", "update"]
  }

  rule {
    api_groups = [""]
    resources  = ["pods", "services", "replicationcontrollers", "persistentvolumeclaims", "persistentvolumes"]
    verbs      = ["watch", "list", "get"]
  }

  rule {
    api_groups = ["extensions"]
    resources  = ["replicasets", "daemonsets"]
    verbs      = ["watch", "list", "get"]
  }

  rule {
    api_groups = ["policy"]
    resources  = ["poddisruptionbudgets"]
    verbs      = ["watch", "list"]
  }

  rule {
    api_groups = ["apps"]
    resources  = ["statefulsets", "replicasets", "daemonsets"]
    verbs      = ["watch", "list", "get"]
  }

  rule {
    api_groups = ["storage.k8s.io"]
    resources  = ["storageclasses", "csinodes", "csidrivers", "csistoragecapacities"]
    verbs      = ["watch", "list", "get"]
  }

  rule {
    api_groups = ["batch"]
    resources  = ["jobs", "cronjobs"]
    verbs      = ["watch", "list", "get"]
  }

  rule {
    api_groups = ["coordination.k8s.io"]
    resources  = ["leases"]
    verbs      = ["create"]
  }

  rule {
    api_groups     = ["coordination.k8s.io"]
    resource_names = ["cluster-autoscaler"]
    resources      = ["leases"]
    verbs          = ["get", "update"]
  }
}