"""
Base definitions for the ``jasmin_cloud.keystore`` package.
"""

from .errors import UnsupportedOperation


class KeyStore:
    """
    Abstract base class for a key store.

    A key store allows the locating of an SSH public key for a username.
    """
    #: Indicates whether the key store supports updating of keys
    supports_key_update = False

    def get_key(
        self,
        username,
        *,
        request = None,
        unscoped_session = None,
    ):
        """
        Returns the SSH public key for the given username.

        Args:
            username: The username to locate an SSH key for.
            request: The active request.
            unscoped_session: The active unscoped session.

        Returns:
            The SSH public key.
        """
        raise NotImplementedError

    def update_key(
        self,
        username,
        public_key,
        *,
        request = None,
        unscoped_session = None,
    ):
        """
        Update the SSH public key for the given username.

        Args:
            username: The username to update the SSH key for.
            public_key: The new SSH public key.
            request: The active request.
            unscoped_session: The active unscoped session.

        Returns:
            The new SSH public key.
        """
        raise UnsupportedOperation(
            "Updating SSH public keys is not supported with the current configuration."
        )
