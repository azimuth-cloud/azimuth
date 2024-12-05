"""
Django middlewares for the Azimuth auth package.
"""

from .settings import auth_settings


class Middleware:
    """
    Middleware that adds an auth session to a request based on a token.

    The token can either be given as a bearer token or taken from the session.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def get_bearer_token(self, request):
        header = request.META.get(auth_settings.BEARER_TOKEN_HEADER, "").strip()
        # If no prefix is configured, use an empty string
        # This means that startswith always returns true and removeprefix does nothing
        prefix = auth_settings.BEARER_TOKEN_PREFIX or ""
        return header.removeprefix(prefix).strip()

    def get_session_token(self, request):
        return request.session.get(auth_settings.TOKEN_SESSION_KEY, None)

    def __call__(self, request):
        # Try the bearer token first
        token = self.get_bearer_token(request)
        # If no bearer token is given, try the session token
        if not token:
            token = self.get_session_token(request)
        # If there is still no token, we are done
        if not token:
            return self.get_response(request)
        # If there is a token, use it to create a session
        with auth_settings.SESSION_PROVIDER.from_token(token) as session:
            request.auth_session = session
            # Process the rest of the response inside the context manager
            return self.get_response(request)
