{{/*
Expand the name of the chart.
*/}}
{{- define "azimuth.name" -}}
{{- .Chart.Name | lower | trunc 63 | trimSuffix "-" | trimSuffix "." }}
{{- end }}

{{/*
Create a default fully qualified name for a chart-level resource.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.

This template must be usable from subcharts, so the chart name is hard-coded.
*/}}
{{- define "azimuth.fullname" -}}
{{- if contains "azimuth" .Release.Name }}
{{- .Release.Name | lower | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-azimuth" .Release.Name | lower | trunc 63 | trimSuffix "-" | trimSuffix "." }}
{{- end }}
{{- end }}

{{/*
Create a fully qualified name for a component resource.
*/}}
{{- define "azimuth.componentname" -}}
{{- $context := index . 0 }}
{{- $componentName := index . 1 }}
{{- $fullName := include "azimuth.fullname" $context }}
{{- printf "%s-%s" $fullName $componentName | lower | trunc 63 | trimSuffix "-" | trimSuffix "." }}
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
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | lower | trunc 63 | trimSuffix "-" | trimSuffix "." }}
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
