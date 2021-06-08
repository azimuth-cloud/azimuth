"""
Base definitions for the ``jasmin_cloud.keystore`` package.
"""


class KeyStore:
    """
    Abstract base class for a key store.

    A key store allows the locating of an SSH public key for a username.
    """
    def get_key(
        self,
        username,
        *,
        request = None,
        unscoped_session = None,
        scoped_session = None
    ):
        """
        Returns the SSH public key for the given username.

        Args:
            username: The username to locate an SSH key for.
            request: The active request.
            unscoped_session: The active unscoped session.
            scoped_session: The active scoped session.

        Returns:
            The SSH public key as a string.
        """
        raise NotImplementedError
