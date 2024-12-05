"""
This module defines the exceptions that can be thrown by an auth session.
"""


class Error(Exception):
    """
    Base class for all other errors in this module.
    """


class AuthenticationError(Error, RuntimeError):
    """
    Raised when authentication fails.
    """


class CommunicationError(Error, RuntimeError):
    """
    Raised when an unexpected communication problem occurs.
    """
