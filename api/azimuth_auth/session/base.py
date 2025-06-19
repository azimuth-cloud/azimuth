"""
Module containing the base session.
"""

import typing as t

from . import dto


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
        raise NotImplementedError

    def user(self) -> dto.User:
        """
        Returns the user for the session.
        """
        raise NotImplementedError

    def ssh_public_key(self) -> str:
        """
        Returns the SSH public key for the session user.
        """
        raise NotImplementedError

    def update_ssh_public_key(self, public_key: str) -> str:
        """
        Updates the SSH public key for the session user.
        """
        raise NotImplementedError

    def tenancies(self) -> t.Iterable[dto.Tenancy]:
        """
        The list of tenancies that the session is able to access.
        """
        raise NotImplementedError

    def credential(self, tenancy_id: str) -> dto.Credential:
        """
        Returns the credential for the specified tenancy ID.
        """
        raise NotImplementedError

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
