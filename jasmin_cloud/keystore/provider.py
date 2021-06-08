"""
Module implementing a key store that uses the provider's native functionality
to store public keys.
"""

from ..provider.errors import ObjectNotFoundError

from .base import KeyStore
from .errors import KeyNotFound


class ProviderKeyStore(KeyStore):
    """
    Key store implementation that consumes keypairs using provider functionality.
    """
    def get_key(self, username, *, unscoped_session, **kwargs):
        # Just return the SSH public key from the provider session
        try:
            return unscoped_session.ssh_public_key(username)
        except ObjectNotFoundError:
            raise KeyNotFound(username)
