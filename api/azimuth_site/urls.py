"""
Root URL configuration for the Azimuth API.
"""

from django.http import HttpResponse
from django.urls import include, path


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
    path('api/', include('azimuth.urls', namespace = 'azimuth')),
    path('auth/', include('azimuth_auth.urls', namespace = 'azimuth_auth')),
]
