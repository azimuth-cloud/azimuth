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
Derives the default portal hostname from the available options.

If apps is enabled, we use the portal subdomain combined with the apps base domain.
If apps are not enabled, required that the hostname is specified.
*/}}
{{- define "azimuth.ingress.defaultHost" -}}
{{- if .Values.tags.apps }}
{{- .Values.global.ingress.portalSubdomain }}.{{ tpl .Values.apps.baseDomain . }}
{{- else }}
{{- fail "ingress.host must be specified explicitly when apps are not enabled" }}
{{- end }}
{{- end -}}

{{/*
Tries to derive the app proxy base domain from the managed Zenith settings.
*/}}
{{- define "azimuth.apps.baseDomain" -}}
{{- if (dig "enabled" true .Values.zenith) }}
{{- $global := deepCopy .Values.global.ingress }}
{{- $common := dig "common" "ingress" dict .Values.zenith | deepCopy }}
{{- $sync := dig "sync" "config" "kubernetes" "ingress" dict .Values.zenith | deepCopy }}
{{- $ingress := mergeOverwrite $global $common $sync }}
{{- required "unable to determine base domain" $ingress.baseDomain }}
{{- else }}
{{- fail "apps.baseDomain is required when the managed Zenith is not enabled" }}
{{- end }}
{{- end -}}

{{/*
Tries to derive the SSHD host from the managed Zenith settings.

If a NodePort service is used for SSHD, assume that a subdomain of the apps base domain will work.
If a LoadBalancer service with a static IP is used for SSHD, use the static IP.
In all other cases, require the SSHD host to be specified.
*/}}
{{- define "azimuth.apps.sshdHost" -}}
{{- if (dig "enabled" true .Values.zenith) }}
{{- if (eq .Values.zenith.sshd.service.type "NodePort") }}
{{- include "azimuth.apps.baseDomain" . | printf "sshd.%s" }}
{{- else if and (eq .Values.zenith.sshd.service.type "LoadBalancer") .Values.zenith.sshd.service.loadBalancerIP }}
{{- .Values.zenith.sshd.service.loadBalancerIP }}
{{- else }}
{{- fail "Unable to determine apps.sshdHost from Zenith configuration" }}
{{- end }}
{{- else }}
{{- fail "apps.sshdHost is required when the managed Zenith is not enabled" }}
{{- end }}
{{- end -}}

{{/*
Tries to derive the SSHD port from the managed Zenith settings.

If the managed Zenith is not enabled, use port 22.
If the service is a NodePort service and a nodePort is specified, use that.
If the service is a LoadBalancer service, use the specified port.
In all other cases, require the port to be specified.
*/}}
{{- define "azimuth.apps.sshdPort" -}}
{{- if (dig "enabled" true .Values.zenith) }}
{{- if and (eq .Values.zenith.sshd.service.type "NodePort") .Values.zenith.sshd.service.nodePort }}
{{- .Values.zenith.sshd.service.nodePort }}
{{- else if (eq .Values.zenith.sshd.service.type "LoadBalancer") }}
{{- .Values.zenith.sshd.service.port }}
{{- else }}
{{- fail "Unable to determine apps.sshdPort from Zenith configuration" }}
{{- end }}
{{- else }}
22
{{- end }}
{{- end -}}

{{/*
Tries to derive the external URL for the registrar from from the managed Zenith settings.
*/}}
{{- define "azimuth.apps.registrarExternalUrl" -}}
{{- if (dig "enabled" true .Values.zenith) }}
{{- $global := deepCopy .Values.global.ingress }}
{{- $common := dig "common" "ingress" dict .Values.zenith | deepCopy }}
{{- $registrar := dig "registrar" "ingress" dict .Values.zenith | deepCopy }}
{{- $ingress := mergeOverwrite $global $common $registrar }}
{{- $proto := $ingress.tls.enabled | ternary "https" "http" }}
{{- $defaultHost := printf "%s.%s" (tpl $ingress.subdomain .) $ingress.baseDomain }}
{{- $host := default $defaultHost $ingress.host }}
{{- printf "%s://%s" $proto $host }}
{{- else }}
{{- fail "apps.registrarExternalUrl is required when the managed Zenith is not enabled" }}
{{- end }}
{{- end -}}

{{/*
Tries to derive the admin URL for the registrar from from the managed Zenith settings.
*/}}
{{- define "azimuth.apps.registrarAdminUrl" -}}
{{- if (dig "enabled" true .Values.zenith) }}
{{- printf "http://%s-zenith-registrar" .Release.Name }}
{{- else }}
{{- fail "apps.registrarAdminUrl is required when the managed Zenith is not enabled" }}
{{- end }}
{{- end -}}

{{/*
Tries to derive the external Azimuth URL from the settings.
*/}}
{{- define "azimuth.externalUrl" -}}
{{- $ingress := mergeOverwrite (deepCopy .Values.global.ingress) .Values.ingress }}
{{- $proto := $ingress.tls.enabled | ternary "https" "http" }}
{{- $host := tpl $ingress.host . }}
{{- printf "%s://%s" $proto $host }}
{{- end -}}

{{/*
Tries to derive the Zenith auth service URL from the Azimuth settings.

This must be usable from the Zenith subchart, so the chart name is hard-coded.
*/}}
{{- define "azimuth.auth.verifyUrl" -}}
{{- $fullName := "" }}
{{- if contains "azimuth" .Release.Name }}
{{- $fullName = .Release.Name | lower | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $fullName = printf "%s-azimuth" .Release.Name | lower | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- $serviceName := printf "%s-%s" $fullName "api" | lower | trunc 63 | trimSuffix "-" }}
{{- printf "http://%s.%s.svc.cluster.local/api/session/verify/" $serviceName .Release.Namespace -}}
{{- end -}}

{{/*
Tries to derive the Zenith signin redirect URL from the Azimuth settings.

This must be usable from the Zenith subchart, so has to use .Values.global.ingress
as the best-guess at what was actually used for Azimuth.
*/}}
{{- define "azimuth.auth.signinUrl" -}}
{{- $proto := .Values.global.ingress.tls.enabled | ternary "https" "http" }}
{{- printf "%s://%s.%s/auth/login/" $proto .Values.global.ingress.portalSubdomain .Values.global.ingress.baseDomain }}
{{- end -}}
