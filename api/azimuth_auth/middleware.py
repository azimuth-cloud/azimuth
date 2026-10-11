"""
Django middlewares for the Azimuth auth package.
"""

import contextlib

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

    @contextlib.contextmanager
    def update_session_token(self, auth_session, request):
        """
        Context manager that ensures that the most up-to-date token is stored in the
        session.
        """
        if auth_settings.TOKEN_SESSION_KEY in request.session:
            # Get the original session token before the request processing happens
            original_token = request.session[auth_settings.TOKEN_SESSION_KEY]
            yield
            # If the session token has changed during the request processing that means
            # a reauthentication has happened, which takes precedence
            # It is also possible that the token has been removed from the session, e.g.
            # during a logout
            session_token = request.session.get(auth_settings.TOKEN_SESSION_KEY)
            if session_token and session_token == original_token:
                # If the token in the auth session has changed, update it
                current_token = auth_session.token()
                if current_token != original_token:
                    request.session[auth_settings.TOKEN_SESSION_KEY] = current_token
        else:
            # If there is no token in the session, we don't put one in
            yield

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
        with auth_settings.SESSION_PROVIDER.from_token(token) as auth_session:
            with self.update_session_token(auth_session, request):
                request.auth_session = auth_session
                response = self.get_response(request)
                return response
