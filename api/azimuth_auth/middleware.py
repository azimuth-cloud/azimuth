"""
Django middlewares for the Azimuth auth package.
"""

from .settings import auth_settings
from .session import errors


class Middleware:
    """
    Middleware that adds an auth session to a request based on a token.

    The token can either be given as a bearer token or taken from the session.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            session_ctx = auth_settings.SESSION_PROVIDER.from_request(request)
        except errors.AuthenticationError:
            return self.get_response(request)
        else:
            with session_ctx as session:
                request.auth_session = session
                return self.get_response(request)
