resource "helm_release" "nginx_ingress" {
  name       = "nginx-ingress"
  repository = "https://kubernetes.github.io/ingress-nginx"
  chart      = "ingress-nginx"
  version    = "4.8.3"
  namespace  = "ingress-nginx"
  create_namespace = true

  values = [
    yamlencode({
      controller = {
        service = {
          type = "LoadBalancer"
          annotations = {
            "service.beta.kubernetes.io/exoscale-loadbalancer-name" = "${var.cluster_name}-nlb"
            "service.beta.kubernetes.io/exoscale-loadbalancer-zone" = var.zone
          }
        }
        nodeSelector = {
          "node-type" = "cpu"
        }
        resources = {
          requests = {
            cpu    = "100m"
            memory = "128Mi"
          }
          limits = {
            cpu    = "500m"
            memory = "512Mi"
          }
        }
        metrics = {
          enabled = var.enable_metrics
          serviceMonitor = {
            enabled = var.enable_metrics
          }
        }
      }
    })
  ]

  depends_on = [exoscale_sks_nodepool.cpu_nodes]
}

resource "kubernetes_ingress_v1" "vllm_ingress" {
  metadata {
    name      = "vllm-ingress"
    namespace = kubernetes_namespace.vllm.metadata[0].name
    annotations = {
      "kubernetes.io/ingress.class"                    = "nginx"
      "nginx.ingress.kubernetes.io/rewrite-target"     = "/"
      "nginx.ingress.kubernetes.io/ssl-redirect"       = "true"
      "nginx.ingress.kubernetes.io/force-ssl-redirect" = "true"
      "nginx.ingress.kubernetes.io/proxy-body-size"    = "50m"
      "nginx.ingress.kubernetes.io/proxy-read-timeout" = "300"
      "nginx.ingress.kubernetes.io/proxy-send-timeout" = "300"
      "nginx.ingress.kubernetes.io/rate-limit"         = "100"
      "nginx.ingress.kubernetes.io/rate-limit-window"  = "1m"
    }
  }

  spec {
    tls {
      hosts       = ["vllm.${var.cluster_name}.exoscale.com"]
      secret_name = "vllm-tls"
    }

    rule {
      host = "vllm.${var.cluster_name}.exoscale.com"
      
      http {
        path {
          path      = "/"
          path_type = "Prefix"
          
          backend {
            service {
              name = kubernetes_service.vllm.metadata[0].name
              port {
                number = 8000
              }
            }
          }
        }
      }
    }
  }

  depends_on = [
    helm_release.nginx_ingress,
    kubernetes_service.vllm
  ]
}

resource "helm_release" "cert_manager" {
  name       = "cert-manager"
  repository = "https://charts.jetstack.io"
  chart      = "cert-manager"
  version    = "1.13.2"
  namespace  = "cert-manager"
  create_namespace = true

  set {
    name  = "installCRDs"
    value = "true"
  }

  values = [
    yamlencode({
      nodeSelector = {
        "node-type" = "cpu"
      }
      webhook = {
        nodeSelector = {
          "node-type" = "cpu"
        }
      }
      cainjector = {
        nodeSelector = {
          "node-type" = "cpu"
        }
      }
    })
  ]

  depends_on = [exoscale_sks_nodepool.cpu_nodes]
}

resource "kubernetes_manifest" "letsencrypt_issuer" {
  manifest = {
    apiVersion = "cert-manager.io/v1"
    kind       = "ClusterIssuer"
    metadata = {
      name = "letsencrypt-prod"
    }
    spec = {
      acme = {
        server = "https://acme-v02.api.letsencrypt.org/directory"
        email  = "admin@${var.cluster_name}.exoscale.com"
        privateKeySecretRef = {
          name = "letsencrypt-prod"
        }
        solvers = [
          {
            http01 = {
              ingress = {
                class = "nginx"
              }
            }
          }
        ]
      }
    }
  }

  depends_on = [helm_release.cert_manager]
}

resource "kubernetes_manifest" "vllm_certificate" {
  manifest = {
    apiVersion = "cert-manager.io/v1"
    kind       = "Certificate"
    metadata = {
      name      = "vllm-tls"
      namespace = kubernetes_namespace.vllm.metadata[0].name
    }
    spec = {
      secretName = "vllm-tls"
      issuerRef = {
        name = "letsencrypt-prod"
        kind = "ClusterIssuer"
      }
      dnsNames = [
        "vllm.${var.cluster_name}.exoscale.com"
      ]
    }
  }

  depends_on = [kubernetes_manifest.letsencrypt_issuer]
}