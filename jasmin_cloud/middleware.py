"""
Django middleware for restoring the cloud provider.
"""

from .provider import errors
from .settings import cloud_settings


def provider_session(get_response):
    """
    Middleware to inject a cloud provider session onto the request based on a token in a cookie.
    """
    def middleware(request):
        # First, process the request
        response = get_response(request)
        # See if there is a session on the request after the view has run
        session = getattr(request, 'auth', None)
        if session:
            # If there is an open session, set the token cookie and close it
            response.set_signed_cookie(
                cloud_settings.TOKEN_COOKIE_NAME,
                session.token(),
                secure = cloud_settings.TOKEN_COOKIE_SECURE,
                httponly = True,
                samesite = 'Strict'
            )
            session.close()
        else:
            # If there is not a session, delete the cookie
            response.delete_cookie(cloud_settings.TOKEN_COOKIE_NAME)
        return response
    return middleware
