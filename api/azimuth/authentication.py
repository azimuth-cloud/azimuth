"""
Django REST Framework authentication backend for the Azimuth app.
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


class AuthSessionAuthentication(BaseAuthentication):
    """
    Authentication backend that looks for an auth session attached to the request.
    """
    def authenticate(self, request):
        auth_session = getattr(request, "auth_session", None)
        # If there is no auth session present, the request is not authenticated
        if not auth_session:
            return None
        # Otherwise, try to initialise a provider session from the auth session
        # This session will be returned as the auth object for DRF
        try:
            session = cloud_settings.PROVIDER.from_auth_session(auth_session)
        except errors.AuthenticationError as exc:
            # If a session cannot be resolved from the token, then it has expired
            logger.exception('Authentication failed: %s', str(exc))
            raise AuthenticationFailed(str(exc))
        else:
            # If the token resolved, return an authenticated user
            logger.info('[%s] Found authenticated user', session.username())
            return (AuthenticatedUser(session.username()), session)

    def authenticate_header(self, request):
        return "Token"
