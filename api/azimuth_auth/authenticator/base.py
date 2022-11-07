"""
Module containing the base authenticator.
"""


class BaseAuthenticator:
    """
    Base class for an authenticator, defining the expected interface.
    """
    #: The code that should be used to indicate a failed authentication
    failure_code = "invalid_credentials"

    #: Indicates if the authenticator uses cross-domain POST requests in the auth completion
    #: This has implications for the CSRF protection and next URL cookie
    #:
    #: WARNING
    #: For authenticators that use cross-domain POST requests, the next URL redirection
    #: will only work over HTTPS in Chrome. Other browsers are likely to follow suit.
    #: See this blog article for more information:
    #:   https://blog.chromium.org/2019/10/developers-get-ready-for-new.html
    uses_crossdomain_post_requests = False

    def get_options(self):
        """
        Allows the authenticator to contribute multiple options to the authenticator
        selection dropdown, corresponding to different parameterisations of the authenticator.

        This method should return a list of (option, label) pairs for the options understood
        by the authenticator. The options will be treated as strings.

        If an empty list is returned, the authenticator just contributes itself to the
        selection dropdown, i.e. it has a single parameterisation.

        The selected option is made available to the auth_start method as selected_option.
        """
        return []

    def auth_start(self, request, auth_complete_url, selected_option = None):
        """
        Process a request to start the authentication flow for this authenticator.

        Receives the request, the URL for the complete endpoint for the authenticator in a
        suitable form for use in redirects (i.e. absolute) and the selected option, if
        the authenticator supports options. It should return a response object.

        This method will only ever receive safe requests.
        """
        raise NotImplementedError

    def auth_complete(self, request):
        """
        Process a request to complete the authentication flow for this authenticator.

        Receives the request and should return either a token if the authentication was
        successful or None if not.

        This method may receive GET or POST requests depending on the implementation.
        """
        raise NotImplementedError
