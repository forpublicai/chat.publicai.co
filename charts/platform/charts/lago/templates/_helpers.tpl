{{- define "secret-path" }}
{{- if .Values.global.existingSecret -}}
{{ .Values.global.existingSecret }}
{{- else -}}
{{ .Release.Name }}-secrets
{{- end }}
{{- end}}

{{- define "encryption-secret-path" }}
{{- if .Values.encryption.existingSecret -}}
{{ .Values.encryption.existingSecret }}
{{- else -}}
{{ .Release.Name }}-secrets
{{- end }}
{{- end}}

{{- define "kubectlVersion" }}
{{- if .Values.global.kubectl.imageTag -}}
{{ .Values.global.kubectl.imageTag }}
{{- else -}}
{{ .Capabilities.KubeVersion }}
{{- end }}
{{- end}}

{{- define "kafkaEnvs" }}
{{- $kafka := .Values.global.clickhouse.kafka -}}
- name: LAGO_KAFKA_BOOTSTRAP_SERVERS
  value: {{ required "If clickhouse is enabled, you must provide a list of Kafka servers"
    $kafka.bootstrapServers | join "," }}
- name: LAGO_KAFKA_CONSUMER_GROUP
  value: {{ $kafka.consumerGroup | quote }}
- name: LAGO_KAFKA_ENRICHED_EVENTS_EXPANDED_TOPIC
  value: {{ $kafka.topics.eventsEnrichedExpanded | quote }}
- name: LAGO_KAFKA_ENRICHED_EVENTS_TOPIC
  value: {{ $kafka.topics.eventsEnriched | quote }}
- name: LAGO_KAFKA_EVENTS_CHARGED_IN_ADVANCE_TOPIC
  value: {{ $kafka.topics.eventsChargedInAdvance | quote }}
- name: LAGO_KAFKA_EVENTS_DEAD_LETTER_TOPIC
  value: {{ $kafka.topics.eventsDeadLetter | quote }}
- name: LAGO_KAFKA_PASSWORD
  valueFrom:
    secretKeyRef:
      name: {{ include "secret-path" . }}
      key: kafkaPassword
      optional: true
- name: LAGO_KAFKA_RAW_EVENTS_TOPIC
  value: {{ $kafka.topics.eventsRaw | quote }}
- name: LAGO_KAFKA_SCRAM_ALGORITHM
  value: {{ $kafka.saslMechanisms | quote }}
- name: LAGO_KAFKA_USERNAME
  valueFrom:
    secretKeyRef:
      name: {{ include "secret-path" . }}
      key: kafkaUsername
      optional: true
- name: LAGO_KAFKA_TLS
  value: {{ $kafka.tls | quote }}
{{- end }}

{{- define "clickhouseEnvs" }}
- name: LAGO_KAFKA_ACTIVITY_LOGS_TOPIC
  value: {{ .Values.global.clickhouse.kafka.topics.activityLogs | quote }}
- name: LAGO_KAFKA_API_LOGS_TOPIC
  value: {{ .Values.global.clickhouse.kafka.topics.apiLogs | quote }}
- name: LAGO_CLICKHOUSE_PORT
  value: "{{ .Values.global.clickhouse.port }}"
- name: LAGO_CLICKHOUSE_HOST
  value: {{ .Values.global.clickhouse.host }}
- name: LAGO_CLICKHOUSE_SSL
  value: "{{ .Values.global.clickhouse.ssl }}"
- name: LAGO_CLICKHOUSE_ENABLED
  value: "true"
- name: LAGO_CLICKHOUSE_DATABASE
  value: "default"
- name: LAGO_CLICKHOUSE_USERNAME
  valueFrom:
    secretKeyRef:
      name: {{ include "secret-path" . }}
      key: clickhouseUsername
      optional: true
- name: LAGO_CLICKHOUSE_PASSWORD
  valueFrom:
    secretKeyRef:
      name: {{ include "secret-path" . }}
      key: clickhousePassword
      optional: true
{{- end }}

{{- define "api-image" }}
{{- $repository := "getlago/api" }}
{{- if and .Values.api (and .Values.api.image .Values.api.image.repository) }}
  {{- $repository = .Values.api.image.repository }}
{{- else if and .Values.image .Values.image.repository }}
  {{- $repository = .Values.image.repository }}
{{- end }}
{{- $tag := printf "v%s" .Values.version }}
{{- if and .Values.api (and .Values.api.image .Values.api.image.tag) }}
  {{- $tag = .Values.api.image.tag }}
{{- else if and .Values.image .Values.image.tag }}
  {{- $tag = .Values.image.tag }}
{{- end }}
{{- printf "%s:%s" $repository $tag }}
{{- end }}
