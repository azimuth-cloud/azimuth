"""
Django middleware for restoring the cloud provider.
"""


class CleanupProviderMiddleware:
    """
    Middleware to cleanup any active cloud provider session on the request.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        # See if there is a session on the request after the view has run
        # If there is, close it
        session = getattr(request, 'auth', None)
        if session:
            session.close()
        return response
