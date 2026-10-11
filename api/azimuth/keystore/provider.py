"""
Module implementing a key store that uses the provider's native functionality
to store public keys.
"""

from ..provider import errors as provider_errors  # noqa: TID252
from . import base, errors


class ProviderKeyStore(base.KeyStore):
    """
    Key store implementation that consumes keypairs using provider functionality.
    """

    supports_key_update = True

    def get_key(self, username, *, unscoped_session, **kwargs):
        # Just return the SSH public key from the provider session
        try:
            return unscoped_session.ssh_public_key()
        except provider_errors.UnsupportedOperationError as exc:
            raise errors.UnsupportedOperation(str(exc))
        except provider_errors.ObjectNotFoundError:
            raise errors.KeyNotFound(username)

    def update_key(self, username, public_key, *, unscoped_session, **kwargs):
        # Just use the provider session to update the public key
        return unscoped_session.update_ssh_public_key(public_key)
