"""
URL definitions for the ``jasmin_cloud`` Django app.
"""

from django.urls import path, re_path, include

from .views import provider, clusters


app_name = 'jasmin_cloud'
urlpatterns = [
    path('authenticate/', provider.authenticate, name = 'authenticate'),
    path('session/', provider.session, name = 'session'),
    path('tenancies/', provider.tenancies, name = 'tenancies'),
    path('tenancies/<slug:tenant>/', include([
        path('quotas/', provider.quotas, name = 'quotas'),
        path('images/', include([
            path('', provider.images, name = 'images'),
            path('<slug:image>/', provider.image_details, name = 'image_details'),
        ])),
        path('sizes/', include([
            path('', provider.sizes, name = 'sizes'),
            path('<slug:size>/', provider.size_details, name = 'size_details'),
        ])),
        path('external_ips/', include([
            path('', provider.external_ips, name = 'external_ips'),
            re_path(r'^(?P<ip>\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})/$',
                provider.external_ip_details,
                name = 'external_ip_details'),
        ])),
        path('volumes/', include([
            path('', provider.volumes, name = 'volumes'),
            path('<slug:volume>/', provider.volume_details, name = 'volume_details'),
        ])),
        path('machines/', include([
            path('', provider.machines, name = 'machines'),
            path('<slug:machine>/', include([
                path('', provider.machine_details, name = 'machine_details'),
                path('start/', provider.machine_start, name = 'machine_start'),
                path('stop/', provider.machine_stop, name = 'machine_stop'),
                path('restart/', provider.machine_restart, name = 'machine_restart'),
            ])),
        ])),
        path('cluster_types/', include([
            path('', clusters.cluster_types, name = 'cluster_types'),
            path('<slug:cluster_type>/', clusters.cluster_type_details, name = 'cluster_type_details'),
        ])),
        path('clusters/', include([
            path('', clusters.clusters, name = 'clusters'),
            path('<slug:cluster>/', clusters.cluster_details, name = 'cluster_details'),
        ]))
    ])),
]
