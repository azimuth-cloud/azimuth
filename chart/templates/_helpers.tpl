{{/*
Expand the name of the chart.
*/}}
{{- define "jasmin-cloud.name" -}}
{{- default .Chart.Name .Values.nameOverride | lower | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified name for a chart-level resource.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "jasmin-cloud.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | lower | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | lower | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | lower | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Create a fully qualified name for a component resource.
*/}}
{{- define "jasmin-cloud.componentname" -}}
{{- $context := index . 0 }}
{{- $componentName := index . 1 }}
{{- $fullName := include "jasmin-cloud.fullname" $context }}
{{- printf "%s-%s" $fullName $componentName | lower | trunc 63 | trimSuffix "-" }}
{{- end -}}

{{/*
Selector labels for a chart-level resource.
*/}}
{{- define "jasmin-cloud.selectorLabels" -}}
app.kubernetes.io/name: {{ include "jasmin-cloud.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Selector labels for a component resource.
*/}}
{{- define "jasmin-cloud.componentSelectorLabels" -}}
{{- $context := index . 0 }}
{{- $componentName := index . 1 }}
{{- include "jasmin-cloud.selectorLabels" $context }}
app.kubernetes.io/component: {{ $componentName }}
{{- end -}}

{{/*
Common labels for all resources.
*/}}
{{- define "jasmin-cloud.commonLabels" -}}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | lower | trunc 63 | trimSuffix "-" }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
{{- end }}

{{/*
Labels for a chart-level resource.
*/}}
{{- define "jasmin-cloud.labels" -}}
{{ include "jasmin-cloud.commonLabels" . }}
{{ include "jasmin-cloud.selectorLabels" . }}
{{- end }}

{{/*
Labels for a component resource.
*/}}
{{- define "jasmin-cloud.componentLabels" -}}
{{ include "jasmin-cloud.commonLabels" (index . 0) }}
{{ include "jasmin-cloud.componentSelectorLabels" . }}
{{- end -}}

{{/*
Tries to derive the Consul server address to use from the internal Consul settings.

This template may be used from dependencies and must still return the correct value.
In particular, this affects the top-level .Values and limits the checks that can be
done. It also means the chart name must be hard-coded.
*/}}
{{- define "jasmin-cloud.consulServerAddress" -}}
{{- $name := "jasmin-cloud" }}
{{- $fullName := contains $name .Release.Name | ternary .Release.Name (printf "%s-%s" .Release.Name $name) -}}
{{- $consulReleaseName := printf "%s-consul" $fullName | lower | trunc 63 | trimSuffix "-" -}}
{{- printf "%s-consul-server:8500" $consulReleaseName -}}
{{- end -}}

{{/*
Tries to derive the app proxy base domain from the internal app proxy settings.
*/}}
{{- define "jasmin-cloud.appProxyBaseDomain" -}}
{{- if .Values.appProxy.enabled -}}
{{- .Values.appProxy.proxy.baseDomain -}}
{{- else -}}
{{- fail "apps.proxyBaseDomain is required when appProxy.enabled is false" -}}
{{- end -}}
{{- end -}}

{{/*
Tries to derive the SSHD host from the app proxy settings.

If the service is a LoadBalancer service, use the static IP if given or force
the user to specify the host.

In other cases, i.e. NodePort service or not enabled, fallback to the app proxy base domain.
*/}}
{{- define "jasmin-cloud.appProxySSHDHost" -}}
{{- if not .Values.appProxy.enabled -}}
{{- tpl .Values.apps.proxyBaseDomain . -}}
{{- else if (eq .Values.appProxy.sshd.service.type "NodePort") -}}
{{- tpl .Values.apps.proxyBaseDomain . -}}
{{- else if (eq .Values.appProxy.sshd.service.type "LoadBalancer") -}}
{{- .Values.appProxy.sshd.service.loadBalancerIP | required "You must specify either appProxy.sshd.service.loadBalancerIP or apps.proxySSHDHost" -}}
{{- else -}}
{{- fail "App proxy SSHD service type must be one of NodePort or LoadBalancer" -}}
{{- end -}}
{{- end -}}

{{/*
Tries to derive the SSHD port from the app proxy settings.

If the internal app proxy is not enabled, use port 22.
If the service is a NodePort service, use the specified node port.
If the service is a LoadBalancer service, use the service port.
*/}}
{{- define "jasmin-cloud.appProxySSHDPort" -}}
{{- if not .Values.appProxy.enabled -}}
22
{{- else if (eq .Values.appProxy.sshd.service.type "NodePort") -}}
{{- .Values.appProxy.sshd.service.nodePort -}}
{{- else if (eq .Values.appProxy.sshd.service.type "LoadBalancer") -}}
{{- .Values.appProxy.sshd.service.port -}}
{{- else -}}
{{- fail "App proxy SSHD service type must be one of NodePort or LoadBalancer" -}}
{{- end -}}
{{- end -}}
