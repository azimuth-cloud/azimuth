{{/*
Expand the name of the chart.
*/}}
{{- define "azimuth.name" -}}
{{- .Chart.Name | lower | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified name for a chart-level resource.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "azimuth.fullname" -}}
{{- if contains .Chart.Name .Release.Name }}
{{- .Release.Name | lower | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name .Chart.Name | lower | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}

{{/*
Create a fully qualified name for a component resource.
*/}}
{{- define "azimuth.componentname" -}}
{{- $context := index . 0 }}
{{- $componentName := index . 1 }}
{{- $fullName := include "azimuth.fullname" $context }}
{{- printf "%s-%s" $fullName $componentName | lower | trunc 63 | trimSuffix "-" }}
{{- end -}}

{{/*
Selector labels for a chart-level resource.
*/}}
{{- define "azimuth.selectorLabels" -}}
app.kubernetes.io/name: {{ include "azimuth.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Selector labels for a component resource.
*/}}
{{- define "azimuth.componentSelectorLabels" -}}
{{- $context := index . 0 }}
{{- $componentName := index . 1 }}
{{- include "azimuth.selectorLabels" $context }}
app.kubernetes.io/component: {{ $componentName }}
{{- end -}}

{{/*
Common labels for all resources.
*/}}
{{- define "azimuth.commonLabels" -}}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | lower | trunc 63 | trimSuffix "-" }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
{{- end }}

{{/*
Labels for a chart-level resource.
*/}}
{{- define "azimuth.labels" -}}
{{ include "azimuth.commonLabels" . }}
{{ include "azimuth.selectorLabels" . }}
{{- end }}

{{/*
Labels for a component resource.
*/}}
{{- define "azimuth.componentLabels" -}}
{{ include "azimuth.commonLabels" (index . 0) }}
{{ include "azimuth.componentSelectorLabels" . }}
{{- end -}}

{{/*
Tries to derive the Consul server address to use from the internal Consul settings.

This template may be used from dependencies and must still return the correct value.
In particular, this affects the top-level .Values and limits the checks that can be
done. It also means the chart name must be hard-coded.
*/}}
{{- define "azimuth.consul.address" -}}
{{- $fullName := "" }}
{{- if contains "azimuth" .Release.Name }}
{{- $fullName = .Release.Name | lower | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $fullName = printf "%s-azimuth" .Release.Name | lower | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- printf "%s-consul-server" $fullName -}}
{{- end -}}

{{/*
Tries to derive the app proxy base domain from the internal Zenith settings.
*/}}
{{- define "azimuth.apps.baseDomain" -}}
{{- if .Values.global.ingress.baseDomain }}
{{- .Values.global.ingress.baseDomain }}
{{- else if dig "enabled" true .Values.zenith -}}
{{- .Values.zenith.sync.config.kubernetes.ingress.baseDomain -}}
{{- else -}}
{{- fail "apps.baseDomain is required when zenith.enabled is false" -}}
{{- end -}}
{{- end -}}

{{/*
Tries to derive the SSHD host from the internal Zenith settings.

If the service is a LoadBalancer service, use the static IP if given or force
the user to specify the host.

In other cases, i.e. NodePort service or not enabled, fallback to the app proxy base domain.
*/}}
{{- define "azimuth.apps.sshdHost" -}}
{{- if not (dig "enabled" true .Values.zenith) -}}
{{- tpl .Values.apps.baseDomain . -}}
{{- else if (eq .Values.zenith.sshd.service.type "NodePort") -}}
{{- tpl .Values.apps.baseDomain . -}}
{{- else if (eq .Values.zenith.sshd.service.type "LoadBalancer") -}}
{{- .Values.zenith.sshd.service.loadBalancerIP | required "You must specify either zenith.sshd.service.loadBalancerIP or apps.sshdHost" -}}
{{- else -}}
{{- fail "zenith.sshd.service.type must be one of NodePort or LoadBalancer" -}}
{{- end -}}
{{- end -}}

{{/*
Tries to derive the SSHD port from the internal Zenith settings.

If the internal Zenith is not enabled, use port 22.
If the service is a NodePort service, use the specified node port.
If the service is a LoadBalancer service, use the service port.
*/}}
{{- define "azimuth.apps.sshdPort" -}}
{{- if not (dig "enabled" true .Values.zenith) -}}
22
{{- else if (eq .Values.zenith.sshd.service.type "NodePort") -}}
{{- .Values.zenith.sshd.service.nodePort -}}
{{- else if (eq .Values.zenith.sshd.service.type "LoadBalancer") -}}
{{- .Values.zenith.sshd.service.port -}}
{{- else -}}
{{- fail "zenith.sshd.service.type must be one of NodePort or LoadBalancer" -}}
{{- end -}}
{{- end -}}
