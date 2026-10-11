class Error(Exception):
    """
    Base class for all other errors in this module.
    """


class QuotaExceededError(Error):
    """
    Raised when a quota is exceeded.
    """
