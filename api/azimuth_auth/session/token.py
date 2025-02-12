from django import http

from ..settings import auth_settings

from . import base, errors


class Provider(base.Provider):
    """
    Base class for authentication session providers that use token authentication.
    """
    def get_bearer_token(self, request: http.HttpRequest) -> str:
        """
        Extracts a bearer token from the request, if present.
        """
        header = request.META.get(auth_settings.BEARER_TOKEN_HEADER, "").strip()
        # If no prefix is configured, use an empty string
        # This means that removeprefix does nothing
        prefix = auth_settings.BEARER_TOKEN_PREFIX or ""
        return header.removeprefix(prefix).strip()

    def get_session_token(self, request: http.HttpRequest) -> str:
        """
        Extracts a token from the session, if present.
        """
        return request.session.get(auth_settings.TOKEN_SESSION_KEY, "")

    def from_token(self, token: str) -> base.Session:
        """
        Create an authentication session from a token.
        """
        raise NotImplementedError

    def from_request(self, request: http.HttpRequest) -> base.Session:
        # Try the bearer token first
        token = self.get_bearer_token(request)
        # If no bearer token is given, try the session token
        if not token:
            token = self.get_session_token(request)
        if token:
            return self.from_token(token)
        else:
            raise errors.AuthenticationError("no token present")
