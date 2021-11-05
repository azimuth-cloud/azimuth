"""
URL definitions for the ``azimuth`` Django app.
"""

from django.urls import path, include

from . import views


app_name = "azimuth"
urlpatterns = [
    path("", views.cloud_info, name = "cloud_info"),
    path("session/", views.session, name = "session"),
    path("session/verify/", views.session_verify, name = "session_verify"),
    path("ssh_public_key/", views.ssh_public_key, name = "ssh_public_key"),
    path("tenancies/", views.tenancies, name = "tenancies"),
    path("tenancies/<slug:tenant>/", include([
        path("quotas/", views.quotas, name = "quotas"),
        path("images/", include([
            path("", views.images, name = "images"),
            path("<slug:image>/", views.image_details, name = "image_details"),
        ])),
        path("sizes/", include([
            path("", views.sizes, name = "sizes"),
            path("<slug:size>/", views.size_details, name = "size_details"),
        ])),
        path("external_ips/", include([
            path("", views.external_ips, name = "external_ips"),
            path("<slug:ip>/", views.external_ip_details, name = "external_ip_details"),
        ])),
        path("volumes/", include([
            path("", views.volumes, name = "volumes"),
            path("<slug:volume>/", views.volume_details, name = "volume_details"),
        ])),
        path("machines/", include([
            path("", views.machines, name = "machines"),
            path("<slug:machine>/", include([
                path("", views.machine_details, name = "machine_details"),
                path("logs/", views.machine_logs, name = "machine_logs"),
                path("start/", views.machine_start, name = "machine_start"),
                path("stop/", views.machine_stop, name = "machine_stop"),
                path("restart/", views.machine_restart, name = "machine_restart"),
                path("console/", views.machine_console, name = "machine_console"),
                path("firewall_rules/", include([
                    path("", views.machine_firewall_rules, name = "machine_firewall_rules"),
                    path(
                        "<slug:rule>/",
                        views.machine_firewall_rule_details,
                        name = "machine_firewall_rule_details"
                    )
                ])),
            ])),
        ])),
        path("kubernetes_cluster_templates/", include([
            path("", views.kubernetes_cluster_templates, name = "kubernetes_cluster_templates"),
            path(
                "<slug:template>/",
                views.kubernetes_cluster_template_details,
                name = "kubernetes_cluster_template_details"
            ),
        ])),
        path("kubernetes_clusters/", include([
            path("", views.kubernetes_clusters, name = "kubernetes_clusters"),
            path("<slug:cluster>/", include([
                path(
                    "",
                    views.kubernetes_cluster_details,
                    name = "kubernetes_cluster_details"
                ),
                path(
                    "kubeconfig/",
                    views.kubernetes_cluster_generate_kubeconfig,
                    name = "kubernetes_cluster_generate_kubeconfig"
                )
            ])),
        ])),
        path("cluster_types/", include([
            path("", views.cluster_types, name = "cluster_types"),
            path(
                "<slug:cluster_type>/",
                views.cluster_type_details,
                name = "cluster_type_details"
            ),
        ])),
        path("clusters/", include([
            path("", views.clusters, name = "clusters"),
            path("<slug:cluster>/", include([
                path("", views.cluster_details, name = "cluster_details"),
                path("patch/", views.cluster_patch, name = "cluster_patch"),
            ])),
        ]))
    ])),
]
