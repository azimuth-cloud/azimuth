"""
Module containing the base authenticator.
"""


class BaseAuthenticator:
    """
    Base class for an authenticator, defining the expected interface.
    """
    #: Indicates if the authenticator uses cross-domain POST requests in the auth completion
    #: This has implications for the CSRF protection and next URL cookie
    #:
    #: WARNING
    #: For authenticators that use cross-domain POST requests, the next URL redirection
    #: will only work over HTTPS in Chrome. Other browsers are likely to follow suit.
    #: See this blog article for more information:
    #:   https://blog.chromium.org/2019/10/developers-get-ready-for-new.html
    uses_crossdomain_post_requests = False

    def auth_start(self, request):
        """
        Process a request for the login endpoint and return a response.

        This method will only ever receive safe requests.
        """
        raise NotImplementedError

    def auth_complete(self, request):
        """
        Process a request for the complete endpoint and return either a (token, expires) tuple
        if the authentication was successful or None if not.

        expires should be an ISO-8601 formatted string representing the time at which the token
        expires. It may be None if the token does not expire.

        This method may receive GET or POST requests depending on the implementation.
        """
        raise NotImplementedError

    def refresh_token(self, token):
        """
        Given an existing token, attempt to obtain a new token and return a new (token, expires)
        tuple.

        If the authenticator does not support token refresh, NotImplementedError should be
        raised.
        """
        raise NotImplementedError
