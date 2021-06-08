"""
Module containing errors that can be raised by key stores.
"""


class Error(Exception):
    """
    Base class for key store errors.
    """


class KeyNotFound(Error):
    """
    Raised when no SSH key can be found for a user.
    """
