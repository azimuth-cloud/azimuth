from . import base, dto


class Provider(base.Provider):
    """
    Null provider implementation that doesn't implement anything.
    """
    provider_name = "null"

    def _from_auth_session(self, auth_session, auth_user):
        return UnscopedSession(auth_session, auth_user)


class UnscopedSession(base.UnscopedSession):
    """
    Unscoped session implementation for the null provider.
    """
    provider_name = "null"

    def _can_use_credential(self, credential):
        # The null provider can use any credential, since it doesn't do anything
        return True

    def _scoped_session(self, auth_user, tenancy, credential_data):
        return ScopedSession(auth_user, tenancy)


class ScopedSession(base.ScopedSession):
    """
    Scoped session implementation for the null provider.
    """
    provider_name = "null"

    def capabilities(self):
        return dto.Capabilities(supports_volumes = False)
