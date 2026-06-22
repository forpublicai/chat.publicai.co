resource "kubernetes_namespace_v1" "argocd" {
  metadata {
    name = "argocd"
  }
}

# Install Argo CD
resource "helm_release" "argocd" {
  name       = "argocd"
  repository = "https://argoproj.github.io/argo-helm"
  chart      = "argo-cd"
  version    = "9.5.22"
  namespace  = kubernetes_namespace_v1.argocd.metadata[0].name
  timeout    = 900

  set = [
    {
      name  = "server.service.type"
      value = "ClusterIP" # Don't need access to dashboard keep internal only
    },
    {
      name  = "configs.params.server.insecure"
      value = "true"
    }
  ]
}

# Install External Secrets Operator (ESO)
resource "kubernetes_namespace_v1" "external_secrets" {
  metadata {
    name = "external-secrets"
  }
}

resource "helm_release" "external_secrets" {
  name       = "external-secrets"
  repository = "https://charts.external-secrets.io"
  chart      = "external-secrets"
  version    = "2.6.0"
  namespace  = kubernetes_namespace_v1.external_secrets.metadata[0].name
  timeout    = 900

  set = [{
    name  = "installCRDs"
    value = "true"
  }]
}
