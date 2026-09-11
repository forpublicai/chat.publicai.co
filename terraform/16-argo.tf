resource "kubernetes_namespace_v1" "argocd" {
  metadata {
    name = "argocd"
  }
}

# Install Argo CD
resource "helm_release" "argocd" {
  name            = "argocd"
  repository      = "https://argoproj.github.io/argo-helm"
  chart           = "argo-cd"
  version         = "9.5.22"
  namespace       = kubernetes_namespace_v1.argocd.metadata[0].name
  timeout         = 200
  replace         = true
  cleanup_on_fail = true

  set = [
    {
      name  = "server.service.type"
      value = "ClusterIP"
    },
    {
      name  = "configs.params.server\\.insecure"
      value = "true"
    },
    {
      name  = "global.tolerations[0].key"
      value = "eks.amazonaws.com/compute-type"
    },
    {
      name  = "global.tolerations[0].operator"
      value = "Equal"
    },
    {
      name  = "global.tolerations[0].value"
      value = "auto"
    },
    {
      name  = "global.tolerations[0].effect"
      value = "NoSchedule"
    }
  ]

  values = [
    yamlencode({
      notifications = {
        enabled = true
        secret = {
          create = false
        }
        notifiers = {
          "service.slack" = "token: $slack-token"
          "service.email" = <<-EOT
            host: umnszkveg337.fips.wmjb.mail-manager-smtp.amazonaws.com
            port: 587
            from: ${local.alert_email}
            username: $email-username
            password: $email-password
          EOT
        }
        triggers = {
          "trigger.on-deployed"        = <<-EOT
            - description: Application is synced and healthy.
              oncePer: app.status.sync.revision
              send: [app-deployed]
              when: app.status.operationState.phase in ["Succeeded"] and app.status.health.status == "Healthy"
          EOT
          "trigger.on-health-degraded" = <<-EOT
            - description: Application has degraded
              send: [app-health-degraded]
              when: app.status.health.status == "Degraded"
          EOT
          "trigger.on-sync-failed"     = <<-EOT
            - description: Application syncing has failed
              send: [app-sync-failed]
              when: app.status.operationState.phase in ["Error", "Failed"]
          EOT
        }
        templates = {
          "template.app-deployed"        = <<-EOT
            email:
              subject: Application {{.app.metadata.name}} is deployed and healthy
            message: |
              Application {{.app.metadata.name}} is now running revision {{.app.status.sync.revision}}.
            slack:
              attachments: |
                [{
                  "title": "{{ .app.metadata.name}}",
                  "title_link": "{{.context.argocdUrl}}/applications/{{.app.metadata.name}}",
                  "color": "#18be52",
                  "fields": [
                    {"title": "Sync Status", "value": "{{.app.status.sync.status}}", "short": true},
                    {"title": "Health Status", "value": "{{.app.status.health.status}}", "short": true}
                  ]
                }]
          EOT
          "template.app-health-degraded" = <<-EOT
            email:
              subject: Application {{.app.metadata.name}} has degraded
            message: |
              Application {{.app.metadata.name}} health status has degraded to {{.app.status.health.status}}.
            slack:
              attachments: |
                [{
                  "title": "ALERT: {{ .app.metadata.name}} degraded",
                  "title_link": "{{.context.argocdUrl}}/applications/{{.app.metadata.name}}",
                  "color": "#E96D76",
                  "fields": [
                    {"title": "Health Status", "value": "{{.app.status.health.status}}", "short": true}
                  ]
                }]
          EOT
          "template.app-sync-failed"     = <<-EOT
            email:
              subject: Failed to sync application {{.app.metadata.name}}
            message: |
              The sync operation of application {{.app.metadata.name}} failed with error: {{.app.status.operationState.message}}
            slack:
              attachments: |
                [{
                  "title": "ALERT: {{ .app.metadata.name}} sync failed",
                  "title_link": "{{.context.argocdUrl}}/applications/{{.app.metadata.name}}",
                  "color": "#E96D76",
                  "fields": [
                    {"title": "Sync Status", "value": "{{.app.status.operationState.phase}}", "short": true}
                  ]
                }]
          EOT
        }
      }
    })
  ]
}

# Install External Secrets Operator (ESO)
resource "kubernetes_namespace_v1" "external_secrets" {
  metadata {
    name = "external-secrets"
  }
}

resource "helm_release" "external_secrets" {
  name            = "external-secrets"
  repository      = "https://charts.external-secrets.io"
  chart           = "external-secrets"
  version         = "2.6.0"
  namespace       = kubernetes_namespace_v1.external_secrets.metadata[0].name
  timeout         = 200
  replace         = true
  cleanup_on_fail = true

  set = [
    {
      name  = "installCRDs"
      value = "true"
    },
    {
      name  = "serviceAccount.annotations.eks\\.amazonaws\\.com/role-arn"
      value = aws_iam_role.external_secrets_irsa.arn
    }
  ]
}
