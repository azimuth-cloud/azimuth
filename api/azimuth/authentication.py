"""
Django REST Framwork authentication backend for the Azimuth app.
"""

import logging

from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed

from .provider import errors
from .settings import cloud_settings


logger = logging.getLogger(__name__)


class AuthenticatedUser:
    """
    Fake user that is returned to represent an authenticated user
    """
    def __init__(self, username):
        self.username = username
        self.is_authenticated = True

    def __str__(self):
        return self.username


class TokenHeaderAuthentication(BaseAuthentication):
    """
    Authentication backend that uses a token set by Azimuth auth for authentication.
    """
    def authenticate(self, request):
        # First, see if the token header is set
        token = request.META.get(cloud_settings.TOKEN_HEADER)
        # If it is not, we are done
        if not token:
            return None
        # If there is a token, try to resolve a session with the configured provider
        # This session will be returned as the auth object
        try:
            session = cloud_settings.PROVIDER.from_token(token)
        except errors.AuthenticationError as exc:
            # If a session cannot be resolved from the token, then it has expired
            logger.exception('Authentication failed: %s', str(exc))
            raise AuthenticationFailed(str(exc))
        else:
            # If the token resolved, return an authenticated user
            logger.info('[%s] Authenticated user from token', session.username())
            return (AuthenticatedUser(session.username()), session)

    def authenticate_header(self, request):
        return "Token"
