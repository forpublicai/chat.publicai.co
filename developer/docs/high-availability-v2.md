
Audit the target application against the criteria below, apply the fixes, and verify them via `helm template` without git committing or running `kubectl apply`:

### Important Audit Rule

Do not blindly apply the example configuration values in this checklist.

Inspect the existing application, Helm chart, and Kubernetes configuration first. Where necessary, use authoritative web resources, official application/framework documentation, and relevant GitHub source code to understand the application's actual behavior.

If the correct configuration cannot be established with reasonable confidence, report the item as **Needs Verification** rather than guessing.
---

### 1. Zero-Downtime Rolling Update Strategy
- [ ] **Zero Unavailable during Updates**: Configure `spec.strategy.rollingUpdate.maxUnavailable: 0` and `maxSurge: 1` (or `25%`) so no running pod is killed until a new one is fully ready.
- [ ] **Warm-up Soak Window (`minReadySeconds`)**: Set `spec.minReadySeconds: 30` (minimum 30 seconds) so new pods must remain healthy and pass readiness checks for 30 continuous seconds before older pods are drained.
- [ ] **Rollout Timeout**: Ensure `spec.progressDeadlineSeconds: 300` (or 600) is set to catch stalled rollouts automatically.

### 2. High Availability Replicas & Anti-Affinity
- [ ] **Minimum Replicas**: Ensure `spec.replicas` is at least `2` (never `1` for production).
- [ ] **HPA Alignment**: If Horizontal Pod Autoscaling (HPA) is enabled, ensure `minReplicas >= 2` so scale-down never leaves a single point of failure.
- [ ] **Pod Distribution (Multi-Node & Multi-AZ)**:
  - Ensure replicas are distributed appropriately across Kubernetes nodes and Availability Zones.
  - Prefer `topologySpreadConstraints` as the primary mechanism for controlling pod distribution where appropriate.
  - `podAntiAffinity` may also be used where there is a specific requirement, but do not automatically configure both anti-affinity and topology spread constraints if doing so would create unnecessarily restrictive or conflicting scheduling rules.
  - Use:
    - `topologyKey: kubernetes.io/hostname` for node-level distribution where appropriate.
    - `topologyKey: topology.kubernetes.io/zone` for Availability Zone distribution where appropriate.
  - Review `whenUnsatisfiable` settings carefully so that HA requirements do not unintentionally make pods unschedulable.
  - The final configuration should balance availability requirements with the actual number of replicas, nodes, Availability Zones, node selectors, taints, and available capacity.
- [ ] **Topology Spread Constraints**: Add `topologySpreadConstraints` to distribute replicas evenly across AWS AZs.

### 3. Cluster Eviction Protection (PodDisruptionBudget - PDB)
- [ ] **PDB Resource**: Ensure a `PodDisruptionBudget` is configured with `minAvailable: 1` (or `maxUnavailable: 1`) so node drains, Karpenter consolidations, and EKS AMI upgrades never terminate all replicas at once.

### 4. Kubernetes Health Probes & Ingress Alignment
- [ ] **Startup Probe**:
  - Add a `startupProbe` where appropriate to protect applications with slow or variable startup times.
  - The startup probe should prevent liveness/readiness checks from prematurely killing or removing a slow-starting application.
  - Use an appropriate endpoint and timing based on the application's actual startup behavior.
  - Do not blindly use fixed timing values if the application's startup characteristics indicate different values are appropriate.

- [ ] **Liveness Probe**:
  - `httpGet` on the application's actual liveness endpoint (e.g. `/health/liveness` or `/healthz`).
  - `initialDelaySeconds: 30`, `periodSeconds: 15`, `timeoutSeconds: 5`, `failureThreshold: 3`, unless the application's actual behavior indicates different values are appropriate.

- [ ] **Readiness Probe**:
  - `httpGet` on the application's actual readiness endpoint (e.g. `/health/readiness` or `/healthz`).
  - `initialDelaySeconds: 15`, `periodSeconds: 10`, `timeoutSeconds: 5`, `failureThreshold: 3`, unless the application's actual behavior indicates different values are appropriate.

- [ ] **Health Endpoint Semantics**:
  - Verify that the endpoints used for startup, liveness, and readiness actually exist and have the correct semantics for the application.
  - Do not invent health endpoints or assume that an endpoint has the correct semantics based solely on its name.
  - Use available web resources, official framework/application documentation, and relevant GitHub source code/documentation to determine the intended behavior where necessary.
  - Specifically verify:
    - **Startup** means the application has successfully initialized.
    - **Readiness** means the pod is currently able to receive production traffic.
    - **Liveness** means the application is sufficiently unhealthy/stuck that restarting the container is appropriate.
  - Pay particular attention to whether dependency failures (e.g. database or external service failures) should affect readiness but should **not necessarily cause a liveness restart**.
  - If the correct semantics cannot be established with reasonable confidence, report the item as **Needs Verification** rather than inventing or changing the endpoint.

- [ ] **ALB Healthcheck Ingress Annotation**:
  - Verify that `alb.ingress.kubernetes.io/healthcheck-path` matches an actual health endpoint served by the application and is appropriate for determining whether the ALB should send traffic to the pod.
  
### 5. Graceful Connection Draining & PreStop Hook
- [ ] **ALB Deregistration Buffer (`preStop` hook)**: Add a preStop sleep hook:
  ```yaml
  lifecycle:
    preStop:
      exec:
        command: ["/bin/sleep", "5"]
  ```
  *(Prevents 502/504 errors by giving the AWS ALB 5 seconds to stop sending new traffic before the container receives SIGTERM).*
- [ ] **Termination Grace Period**: Set `spec.template.spec.terminationGracePeriodSeconds: 30` (or 60).

### 6. Resource Budgeting & Scheduling Controls
- [ ] **Explicit CPU & Memory Requests/Limits**: Set distinct `requests` and `limits` to prevent node overcommitment and OOM cascading failures.
- [ ] **Scheduling Blocks**: Ensure `{{- with .Values.app.nodeSelector }}`, `{{- with .Values.app.tolerations }}`, and `{{- with .Values.app.affinity }}` are templated.

### 7. Argo CD Alerting, Tracking & Self-Healing
- [ ] **Alerting Notifications**: Add standard Argo CD notification annotations to the `Application` manifest metadata:
  ```yaml
  metadata:
    annotations:
      notifications.argoproj.io/subscribe.on-health-degraded.slack: "#argo-alerts"
      notifications.argoproj.io/subscribe.on-sync-failed.slack: "#argo-alerts"
      notifications.argoproj.io/subscribe.on-health-degraded.email: "sean@publicai.co"
      notifications.argoproj.io/subscribe.on-sync-failed.email: "sean@publicai.co"
      notifications.argoproj.io/subscribe.on-deployed.slack: "#argo-alerts"
      notifications.argoproj.io/subscribe.on-deployed.email: "sean@publicai.co"
      notifications.argoproj.io/subscribe.on-created.slack: "#argo-alerts"
      notifications.argoproj.io/subscribe.on-created.email: "sean@publicai.co"
      notifications.argoproj.io/subscribe.on-deleted.slack: "#argo-alerts"
      notifications.argoproj.io/subscribe.on-deleted.email: "sean@publicai.co"
  ```
- [ ] **Automated Sync Policy**: Ensure `syncPolicy.automated.prune: true`, `selfHeal: true`, and `retry` exponential backoff blocks are present.

---

### Output Requirements:
1. Provide a table summarizing the audit findings (Pass / Fail / Fixed).
1. Confirm that `helm lint` and `helm template` rendered without errors.
1. DO NOT run `git commit` or `kubectl apply` without explicit confirmation.
```

---

### Standard Blueprint Template (`deployment.yaml` + `pdb.yaml`)

```yaml
# templates/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ .Values.app.name }}
  namespace: {{ .Values.global.namespace }}
spec:
  replicas: {{ .Values.app.replicas | default 2 }}
  minReadySeconds: {{ .Values.app.minReadySeconds | default 30 }}
  progressDeadlineSeconds: 300
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxUnavailable: 0
      maxSurge: 1
  selector:
    matchLabels:
      app: {{ .Values.app.name }}
  template:
    metadata:
      labels:
        app: {{ .Values.app.name }}
    spec:
      terminationGracePeriodSeconds: 30
      {{- with .Values.app.affinity }}
      affinity:
        {{- toYaml . | nindent 8 }}
      {{- end }}
      {{- with .Values.app.topologySpreadConstraints }}
      topologySpreadConstraints:
        {{- toYaml . | nindent 8 }}
      {{- end }}
      containers:
        - name: {{ .Values.app.name }}
          lifecycle:
            preStop:
              exec:
                command: ["/bin/sleep", "5"]
          livenessProbe:
            httpGet:
              path: {{ .Values.app.livenessProbe.path }}
              port: {{ .Values.app.port }}
            initialDelaySeconds: 30
            periodSeconds: 15
            timeoutSeconds: 5
            failureThreshold: 3
          readinessProbe:
            httpGet:
              path: {{ .Values.app.readinessProbe.path }}
              port: {{ .Values.app.port }}
            initialDelaySeconds: 15
            periodSeconds: 10
            timeoutSeconds: 5
            failureThreshold: 3
          resources:
            {{- toYaml .Values.app.resources | nindent 12 }}
---
# templates/pdb.yaml
{{- if .Values.podDisruptionBudget.enabled }}
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: {{ .Values.app.name }}-pdb
  namespace: {{ .Values.global.namespace }}
spec:
  minAvailable: {{ .Values.podDisruptionBudget.minAvailable | default 1 }}
  selector:
    matchLabels:
      app: {{ .Values.app.name }}
{{- end }}
```