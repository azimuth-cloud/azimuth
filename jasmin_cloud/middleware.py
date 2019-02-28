"""
Django middleware for the jasmin-cloud app.
"""

from .provider.base  import UnscopedSession


def provider_cleanup(get_response):
    """
    Middleware to clean up the provider session in the request.auth property.
    """
    def middleware(request):
        # Run the view first
        response = get_response(request)
        # If the request has an auth property that is an unscoped session, close it
        session = getattr(request, 'auth', None)
        if isinstance(session, UnscopedSession):
            session.close()
        return response
    return middleware
