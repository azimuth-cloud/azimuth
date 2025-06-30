"""
Module containing the base session.
"""

import typing as t

from . import dto, errors


class Provider:
    """
    Base class for an authentication session provider.
    """

    def from_token(self, token: str) -> "Session":
        """
        Create an authentication session from a token.
        """
        raise NotImplementedError


class Session:
    """
    Base class for an auth session.
    """

    def token(self) -> str:
        """
        Returns the token for the session.
        """
        raise errors.UnsupportedOperationError("Operation not supported.")

    def user(self) -> dto.User:
        """
        Returns the user for the session.
        """
        raise errors.UnsupportedOperationError("Operation not supported.")

    def ssh_public_key(self) -> str:
        """
        Returns the SSH public key for the session user.
        """
        raise errors.UnsupportedOperationError("Operation not supported.")

    def update_ssh_public_key(self, public_key: str) -> str:
        """
        Updates the SSH public key for the session user.
        """
        raise errors.UnsupportedOperationError("Operation not supported.")

    def tenancies(self) -> t.Iterable[dto.Tenancy]:
        """
        The list of tenancies that the session is able to access.
        """
        raise errors.UnsupportedOperationError("Operation not supported.")

    def credential(self, tenancy_id: str, provider: str) -> t.Optional[dto.Credential]:
        """
        Returns the credential for the specified tenancy ID and provider.

        If no such credential exists, None is returned.
        """
        raise errors.UnsupportedOperationError("Operation not supported.")

    def close(self):
        """
        Closes the session and performs any cleanup.
        """
        # This is a NOOP by default

    def __enter__(self):
        """
        Called when entering a context manager block.
        """
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """
        Called when exiting a context manager block. Ensures that close is called.
        """
        self.close()

    def __del__(self):
        """
        Ensures that close is called when the session is garbage collected.
        """
        self.close()
