"""
Module containing a Django authentication backend and Django REST framework
authentication schemes that use the configured provider to validate credentials.

Each of these authentication schemes exposes the resulting
:py:class:`.provider.base.UnscopedSession` as `request.auth`.
"""

from django.contrib.auth import backends, get_user_model
from django.core.exceptions import ImproperlyConfigured

from rest_framework import authentication, exceptions as drf_exceptions

from .provider import errors
from .settings import cloud_settings


class ProviderBackend(backends.ModelBackend):
    """
    Authentication backend that uses the configured cloud provider to validate
    credentials. The resulting token is saved in the session for later.
    """
    def authenticate(self, request, username = None, password = None, **kwargs):
        provider = cloud_settings.PROVIDER
        try:
            session = provider.authenticate(username, password)
        except errors.AuthenticationError:
            return None
        UserModel = get_user_model()
        try:
            user = UserModel.objects.get(username = username)
        except UserModel.DoesNotExist:
            user = UserModel.objects.create_user(username = username)
        # Make sure the session is closed after use
        with session:
            if self.user_can_authenticate(user):
                request.session['provider_token'] = session.token()
                return user


class ProviderBasicAuthentication(authentication.BasicAuthentication):
    """
    DRF authentication scheme for Basic authentication using the configured
    cloud provider to validate the username and password.
    """
    def authenticate_credentials(self, userid, password, request = None):
        # First, let the parent do it's thing
        user, _ = super().authenticate_credentials(userid, password, request)
        # Find the token from the session and use it to rebuild the session
        # NOTE: The token will have been placed there in the previous call by the
        #       provider backend - we are not relying on a persistent session
        try:
            token = request.session['provider_token']
        except KeyError:
            raise ImproperlyConfigured('Please configure the provider backend.')
        # The token is guaranteed to be valid as we only just got it
        return user, cloud_settings.PROVIDER.from_token(token)


class ProviderSessionAuthentication(authentication.SessionAuthentication):
    """
    DRF authentication scheme for session authentication that restores the
    unscoped session from a token stored in the session.
    """
    def authenticate(self, request):
        user_auth_tuple = super().authenticate(request)
        if not user_auth_tuple:
            return
        try:
            token = request.session['provider_token']
        except KeyError:
            raise ImproperlyConfigured('Please configure the provider backend.')
        try:
            return user_auth_tuple[0], cloud_settings.PROVIDER.from_token(token)
        except errors.AuthenticationError as e:
            # If we get here, the session has expired
            request.session.flush()
            raise drf_exceptions.AuthenticationFailed(str(e))


class ProviderTokenAuthentication(authentication.TokenAuthentication):
    """
    DRF authentication scheme for Bearer token authentication that restores the
    unscoped session from the given token.
    """
    keyword = 'Bearer'

    def authenticate_credentials(self, key):
        try:
            session = cloud_settings.PROVIDER.from_token(key)
        except errors.AuthenticationError as e:
            # If we get here, the session has expired
            raise drf_exceptions.AuthenticationFailed(str(e))
        UserModel = get_user_model()
        try:
            user = UserModel.objects.get(username = session.username())
        except UserModel.DoesNotExist:
            user = UserModel.objects.create_user(username = session.username())
        return user, session
