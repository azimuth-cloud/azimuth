"""
URL definitions for the ``jasmin_cloud`` Django app.
"""

from django.urls import path, re_path, include

from . import views


app_name = 'jasmin_cloud'
urlpatterns = [
    path('authenticate/', views.authenticate, name = 'authenticate'),
    path('session/', views.session, name = 'session'),
    path('tenancies/', views.tenancies, name = 'tenancies'),
    path('tenancies/<slug:tenant>/', include([
        path('quotas/', views.quotas, name = 'quotas'),
        path('images/', include([
            path('', views.images, name = 'images'),
            path('<slug:image>/', views.image_details, name = 'image_details'),
        ])),
        path('sizes/', include([
            path('', views.sizes, name = 'sizes'),
            path('<slug:size>/', views.size_details, name = 'size_details'),
        ])),
        path('external_ips/', include([
            path('', views.external_ips, name = 'external_ips'),
            re_path(r'^(?P<ip>\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})/$',
                views.external_ip_details,
                name = 'external_ip_details'),
        ])),
        path('volumes/', include([
            path('', views.volumes, name = 'volumes'),
            path('<slug:volume>/', views.volume_details, name = 'volume_details'),
        ])),
        path('machines/', include([
            path('', views.machines, name = 'machines'),
            path('<slug:machine>/', include([
                path('', views.machine_details, name = 'machine_details'),
                path('start/', views.machine_start, name = 'machine_start'),
                path('stop/', views.machine_stop, name = 'machine_stop'),
                path('restart/', views.machine_restart, name = 'machine_restart'),
            ])),
        ])),
        path('cluster_types/', include([
            path('', views.cluster_types, name = 'cluster_types'),
            path('<slug:cluster_type>/', views.cluster_type_details, name = 'cluster_type_details'),
        ])),
        path('clusters/', include([
            path('', views.clusters, name = 'clusters'),
            path('<slug:cluster>/', include([
                path('', views.cluster_details, name = 'cluster_details'),
                path('patch/', views.cluster_patch, name = 'cluster_patch'),
            ])),
        ]))
    ])),
]
