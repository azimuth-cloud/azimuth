from . import base


class Provider(base.Provider):
    """
    Null provider implementation that doesn't implement anything.
    """
    def _from_auth_session(self, auth_session, auth_user):
        return UnscopedSession(auth_session, auth_user)


class UnscopedSession(base.UnscopedSession):
    """
    Unscoped session implementation for the null provider.
    """
    def _scoped_session(self, auth_user, tenancy, credential_data):
        return ScopedSession(auth_user, tenancy)


class ScopedSession(base.ScopedSession):
    """
    Scoped session implementation for the null provider.
    """
