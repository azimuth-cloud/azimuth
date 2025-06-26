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


class PermissionDeniedError(Error, RuntimeError):
    """
    Raised when permission is denied while accessing a resource.
    """


class BadInputError(Error, RuntimeError):
    """
    Raised when the input to a create or update is invalid.
    """


class ObjectNotFoundError(Error, RuntimeError):
    """
    Raised when an object is not found.
    """


class InvalidOperationError(Error, RuntimeError):
    """
    Raised when an invalid operation is attempted.
    """


class UnsupportedOperationError(Error, NotImplementedError):
    """
    Raised when the requested operation is not supported by a provider.
    """


class CommunicationError(Error, RuntimeError):
    """
    Raised when an unexpected communication problem occurs.
    """
