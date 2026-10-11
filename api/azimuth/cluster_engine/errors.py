"""
This module defines the exceptions that can be thrown by a cluster engine.
"""


class Error(Exception):
    """
    Base class for all other errors in this module.
    """


class BadInputError(Error, RuntimeError):
    """
    Raised when the input to a create or update is invalid. Invalid input to a
    find should raise :py:class:`ObjectNotFoundError`.
    """


class UnsupportedOperationError(Error, NotImplementedError):
    """
    Raised when the requested operation is not supported by a provider.
    """


class InvalidOperationError(Error, RuntimeError):
    """
    Raised when an operation is invalid for the current state of the target.
    """


class QuotaExceededError(InvalidOperationError):
    """
    Raised when a quota is exceeded.
    """


class ImproperlyConfiguredError(Error, RuntimeError):
    """
    Raised when a tenancy is not configured as expected/required.
    """


class ObjectNotFoundError(Error, RuntimeError):
    """
    Raised when an object requested by ID is not found.
    """


class AuthenticationError(Error, RuntimeError):
    """
    Raised when authentication fails when accessing a resource.
    """


class PermissionDeniedError(Error, RuntimeError):
    """
    Raised when permission is denied while accessing a resource.
    """


class CommunicationError(Error, RuntimeError):
    """
    Raised when an unexpected communication problem occurs.
    """


class OperationTimedOutError(Error, RuntimeError):
    """
    Raised when an operation takes too long to wait for.
    """


class ValidationError(BadInputError):
    """
    Raised when a validation fails.
    """

    def __init__(self, message, errors):
        super().__init__(message)
        self._errors = errors

    @property
    def errors(self):
        return self._errors
