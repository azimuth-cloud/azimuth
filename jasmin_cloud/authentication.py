"""
Authentication helpers and backends for the ``jasmin_cloud`` Django app.
"""

from django.contrib.auth import backends, get_user_model

from .provider import errors
from .settings import cloud_settings


UserModel = get_user_model()


class ProviderBackend(backends.ModelBackend):
    """
    Authentication backend that uses the configured :py:class:`~.provider.base.Provider`
    for authentication.

    We use the model backend, but rather than checking passwords in the database
    we use the provider. The authenticated :py:class:`~.provider.base.UnscopedSession`
    is saved in the session to be retrieved later.
    """
    def authenticate(self, request, username = None, password = None, **kwargs):
        provider = cloud_settings.PROVIDER
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
        request.session['unscoped_session'] = session
        return user
