"""
Root URL configuration for the JASMIN Cloud API site.
"""

from django.urls import path, include
from django.http import HttpResponse


def status(request):
    """
    Endpoint used for healthchecks.
    """
    # Just return 204 No Content
    return HttpResponse(status = 204)


urlpatterns = [
    # Install a URL to use for health checks
    # We can't use any of the /api URLs as they either require authentication
    # or don't accept use of the GET method
    path('_status/', status, name = 'status'),
    path('api/', include('jasmin_cloud.urls', namespace = 'jasmin_cloud')),
]
