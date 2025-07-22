"""
Module containing the base authenticator.
"""


class BaseAuthenticator:
    """
    Base class for an authenticator, defining the expected interface.
    """

    #: The code that should be used to indicate a failed authentication
    failure_code = "invalid_credentials"

    #: Indicates if the authenticator uses cross-domain POST requests in the auth
    #: completion
    #: This has implications for the CSRF protection and next URL cookie
    #:
    #: WARNING
    #: For authenticators that use cross-domain POST requests, the next URL redirection
    #: will only work over HTTPS in Chrome. Other browsers are likely to follow suit.
    #: See this blog article for more information:
    #:   https://blog.chromium.org/2019/10/developers-get-ready-for-new.html
    uses_crossdomain_post_requests = False

    #: Indicates if the authenticator should only be used in interactive flows, e.g.
    #: if a browser is required in order to complete the authentication
    interactive_only = False

    def get_representation(self):
        """
        Returns a dictionary representation of the authenticator, for use in the SDK.
        """
        if hasattr(self, "authenticator_type"):
            return {
                "type": self.authenticator_type,
                "options": self.get_options(),
            }
        else:
            raise NotImplementedError

    def get_options(self):
        """
        Allows the authenticator to contribute multiple options to the authenticator
        selection dropdown, corresponding to different parameterisations of the
        authenticator.

        This method should return a list of (option, label) pairs for the options
        understood by the authenticator. The options will be treated as strings.

        If an empty list is returned, the authenticator just contributes itself to the
        selection dropdown, i.e. it has a single parameterisation.
        """
        return []

    def auth_start(self, request, auth_complete_url, selected_option=None):
        """
        Process a request to start the authentication flow for this authenticator.

        Receives the request, the URL for the complete endpoint for the authenticator
        in a suitable form for use in redirects (i.e. absolute) and the selected option,
        if the authenticator supports options. It should return a response object.

        This method will only ever receive safe requests.
        """
        raise NotImplementedError

    def auth_complete(self, request, selected_option=None):
        """
        Process a request to complete the authentication flow for this authenticator.

        Receives the request and should return either a token if the authentication was
        successful or None if not.

        This method may receive GET or POST requests depending on the implementation.
        """
        raise NotImplementedError

    def auth_token(self, auth_data, selected_option=None):
        """
        Use the given auth data to attempt to obtain a token.

        Returns the token if successful, None if not..
        """
        raise NotImplementedError
