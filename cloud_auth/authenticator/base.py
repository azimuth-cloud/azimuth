"""
Module containing the base authenticator.
"""


class BaseAuthenticator:
    """
    Base class for an authenticator, defining the expected interface.
    """
    #: Indicates whether POST requests to the auth_complete endpoint should have
    #: CSRF protection enabled
    csrf_protect = True

    def auth_start(self, request):
        """
        Process a request for the login endpoint and return a response.

        This method will only ever receive safe requests.
        """
        raise NotImplementedError

    def auth_complete(self, request):
        """
        Process a request for the complete endpoint and return either a token if the
        authentication was successful or null if not.

        This method may receive GET or POST requests depending on the implementation.
        """
        raise NotImplementedError
