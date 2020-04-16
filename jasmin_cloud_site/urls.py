"""
Root URL configuration for the JASMIN Cloud API site.
"""

from django.conf.urls import url, include


urlpatterns = [
    url(r'^api/', include('jasmin_cloud.urls', namespace = 'jasmin_cloud')),
]
