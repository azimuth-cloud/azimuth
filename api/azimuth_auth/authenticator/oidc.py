import base64
import json
import logging
import urllib.parse

import httpx
import oauthlib.common
import oauthlib.oauth2

from . import redirect


class AuthorizationCodeAuthenticator(redirect.RedirectAuthenticator):
    """
    Authenticator that uses the OIDC authorization flow to obtain a token.

    The OAuth2 flow is implemented here rather than using an ingress auth callout with
    oauth2-proxy primarily because we need to be able to have some requests that are
    "optionally authenticated".

    This makes it possible to do things like render the Azimuth homepage to
    unauthenticated users so that they can discover docs on how to register while also
    understanding when a user is authenticated, and to present nicer messages to API
    consumers when unauthenticated requests are made.

    This kind of optional authentication is extremely difficult to configure with the
    ingress callout as implemented by the NGINX ingress controller.

    Potential issues with writing our own authentication code are mitigated by using the
    oauthlib library to generate OAuth2 request URIs/bodies and to parse the responses.
    """

    authenticator_type = "oidc_authcode"

    def __init__(
        self,
        authorization_url,
        token_url,
        client_id,
        client_secret,
        scope,
        state_session_key,
        verify_ssl,
    ):
        self.authorization_url = authorization_url
        self.token_url = token_url
        self.client_id = client_id
        self.client_secret = client_secret
        self.scope = scope
        self.state_session_key = state_session_key
        self.verify_ssl = verify_ssl
        self.logger = logging.getLogger(__name__)

    def prepare_redirect_url(self, redirect_url):
        # Strip parameters from the URL
        components = urllib.parse.urlsplit(redirect_url)
        components = components._replace(query="", fragment="")
        return urllib.parse.urlunsplit(components)

    def get_redirect_to(self, request, auth_complete_url, selected_option=None):
        client = oauthlib.oauth2.WebApplicationClient(self.client_id)
        # Generate new state parameter and stash it in the session
        state = request.session[self.state_session_key] = (
            oauthlib.common.generate_token()
        )
        # Generate the full authorization URL with parameters
        return client.prepare_request_uri(
            self.authorization_url,
            redirect_uri=self.prepare_redirect_url(auth_complete_url),
            scope=self.scope,
            state=state,
        )

    def auth_complete(self, request, selected_option=None):
        client = oauthlib.oauth2.WebApplicationClient(self.client_id)
        # Pull the state from the session
        # If it fails, log the error and try again
        try:
            state = request.session.pop(self.state_session_key)
        except KeyError:
            self.logger.warning("no OIDC state in session")
            return None
        # Extract the code from the URL
        # If it fails, log the error and try again
        request_uri = request.build_absolute_uri()
        try:
            code = client.parse_request_uri_response(request_uri, state)["code"]
        except (oauthlib.oauth2.OAuth2Error, KeyError):
            self.logger.exception("error extracting authcode")
            return None
        # Make the token request
        # If it fails, log the error and try again
        try:
            response = httpx.post(
                self.token_url,
                data=dict(
                    oauthlib.common.urldecode(
                        client.prepare_request_body(
                            code,
                            self.prepare_redirect_url(request_uri),
                            include_client_id=True,
                            client_secret=self.client_secret,
                        )
                    )
                ),
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                verify=self.verify_ssl,
            )
        except httpx.RequestError:
            self.logger.exception("error fetching token")
            return None
        if not response.is_success:
            self.logger.error(
                f"error fetching token "
                f'"{response.status_code} {response.reason_phrase}" '
                f"{response.text}"
            )
            return None
        # Parse the token from the response
        # If it fails, log the error and try again
        try:
            token_data = client.parse_request_body_response(
                response.text, scope=self.scope
            )
        except oauthlib.oauth2.OAuth2Error:
            self.logger.exception("error extracting token from response")
            return None
        # The token that we return is a base64-encoded JSON dump of the token data
        # This means that the OIDC session can consume both the access and refresh
        # tokens
        return base64.b64encode(json.dumps(token_data).encode()).decode()
