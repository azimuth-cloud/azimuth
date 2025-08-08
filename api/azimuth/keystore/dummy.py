"""
Module implementing a dummy key store that returns the same key for every user.
"""

from .base import KeyStore


class DummyKeyStore(KeyStore):
    """
    Key store implementation that returns a single key for all users.

    Args:
        key: The single public key to use for all users.
        ssh_key_is_public: The key should be visible in the Azimuth UI
    """

    def __init__(self, ssh_key_is_public=True, key=None):
        self.key = key
        self.ssh_key_is_public = ssh_key_is_public

    def get_key(self, username, **kwargs):
        return self.key
