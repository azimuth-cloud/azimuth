"""
Module containing authentication helpers and `authentication backends`_ for the
JASMIN Cloud API.

.. _authentication backends: https://docs.djangoproject.com/en/1.11/topics/auth/customizing/#specifying-authentication-backends
"""

from django.conf import settings
from django.contrib.auth import backends, get_user_model

from . import models
from .provider import errors


UserModel = get_user_model()


class ProviderBackend(backends.ModelBackend):
    """
    Authentication backend that uses the configured :py:class:`~.provider.base.Provider`
    for authentication.

    We use the model backend, but rather than checking passwords in the database
    we use the provider. The authenticated :py:class:`~.provider.base.UnscopedSession`
    is saved in the database to be retrieved later.
    """
    def authenticate(self, request, username = None, password = None, **kwargs):
        provider = settings.JASMIN_CLOUD['PROVIDER']
        try:
            session = provider.authenticate(username, password)
        except errors.AuthenticationError:
            return None
        try:
            user = UserModel.objects.get(username = username)
        except UserModel.DoesNotExist:
            user = UserModel.objects.create_user(username = username)
        if not self.user_can_authenticate(user):
            return None
        models.CloudSession.objects.update_or_create(
            user = user, defaults = { 'session' : session }
        )
        return user
