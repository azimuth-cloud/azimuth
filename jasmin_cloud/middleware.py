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
        # First, see if the token cookie is set
        token = request.get_signed_cookie(cloud_settings.TOKEN_COOKIE_NAME, None)
        if token:
            try:
                # If there is a token, try to resolve a session with the configured provider
                # Set the resolved session as a request property
                request.provider_session = cloud_settings.PROVIDER.from_token(token)
            except errors.AuthenticationError as e:
                # If a session cannot be resolved from the token, do nothing
                pass
        # Defer to the next middleware for a response
        response = get_response(request)
        # See if there is a session on the request after the view has run
        session = getattr(request, 'provider_session', None)
        if session:
            # If there is an open session, set the token cookie and close it
            response.set_signed_cookie(
                cloud_settings.TOKEN_COOKIE_NAME,
                session.token(),
                secure = True,
                httponly = True,
                samesite = 'Strict'
            )
            session.close()
        else:
            # If there is not a session, delete the cookie
            response.delete_cookie(cloud_settings.TOKEN_COOKIE_NAME)
        # And we are done
        return response
    return middleware
