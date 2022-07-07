"""
Django middlewares for the Azimuth auth package.
"""

from datetime import datetime, timedelta
import logging

from dateutil import parser, tz

from .settings import auth_settings


logger = logging.getLogger(__name__)


class BaseMiddleware:
    """
    Base class for other Azimuth auth middlewares.

    Each middleware implements a particular method by which a token may be provided,
    e.g. bearer tokens or session data.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def get_token(self, request):
        """
        Get the current token from the request. May return null if no token is present.
        """
        raise NotImplementedError

    def __call__(self, request):
        token = self.get_token(request)
        if token:
            request.META[auth_settings.DOWNSTREAM_TOKEN_HEADER] = token
        return self.get_response(request)


class BearerTokenMiddleware(BaseMiddleware):
    """
    Middleware that reads token information from a bearer token.
    """
    def get_token(self, request):
        header = request.META.get(auth_settings.BEARER_TOKEN_HEADER, "").strip()
        # If no prefix is configured, use an empty string
        # This means that startswith always returns true and removeprefix does nothing
        prefix = auth_settings.BEARER_TOKEN_PREFIX or ""
        if header and header.startswith(prefix):
            return header.removeprefix(prefix).strip()


class SessionTokenMiddleware(BaseMiddleware):
    """
    Middleware that reads token information from the session.
    """
    def get_token(self, request):
        return request.session.get(auth_settings.TOKEN_SESSION_KEY, None)
