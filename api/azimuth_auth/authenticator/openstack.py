"""
Module containing authenticators for OpenStack clouds.
"""

from urllib.parse import urlencode

import requests
from django import forms

from .form import FormAuthenticator
from .redirect import RedirectAuthenticator


def normalize_auth_url(auth_url):
    """
    Given an auth URL, return the normalized representation.
    """
    return auth_url.rstrip("/").removesuffix("/v3") + "/v3"


class OpenStackFormAuthenticator(FormAuthenticator):
    """
    Base class for OpenStack authenticators that use a form to authenticate.
    """

    def __init__(self, auth_url, verify_ssl=True):
        self.auth_url = normalize_auth_url(auth_url)
        self.token_url = f"{self.auth_url}/auth/tokens"
        self.verify_ssl = verify_ssl

    def get_identity(self, auth_data, selected_option=None):
        """
        Returns the identity to use for the token request, derived from the form data.
        """
        raise NotImplementedError

    def auth_token(self, auth_data, selected_option=None):
        # Try to get the identity data from the provided auth data
        # If the required data is not present, a KeyError will be raised
        try:
            identity = self.get_identity(auth_data, selected_option)
        except KeyError:
            return None
        # Authenticate the user by submitting an appropriate request to the token URL
        response = requests.post(
            self.token_url,
            json=dict(auth=dict(identity=identity)),
            verify=self.verify_ssl,
        )
        # If the response is a success, return the token
        if response.status_code == 201:
            return response.headers["X-Subject-Token"]
        # If the response is an authentication error, return null
        if response.status_code in {401, 404}:
            return None
        # For all other statuses, raise the corresponding exception
        response.raise_for_status()


class PasswordAuthenticator(OpenStackFormAuthenticator):
    """
    Authenticator that authenticates with an OpenStack cloud using the
    password authentication method.
    """

    authenticator_type = "openstack_password"

    def __init__(self, auth_url, domains, verify_ssl=True):
        super().__init__(auth_url, verify_ssl)
        self.domains = domains

    def get_options(self):
        return [
            (domain["name"], domain.get("label") or domain["name"])
            for domain in self.domains
        ]

    def get_identity(self, auth_data, selected_option=None):
        return dict(
            methods=["password"],
            password=dict(
                user=dict(
                    domain=dict(name=selected_option),
                    name=auth_data["username"],
                    password=auth_data["password"],
                )
            ),
        )


class ApplicationCredentialForm(forms.Form):
    """
    Form for authenticating with an application credential.
    """

    application_credential_id = forms.CharField()
    application_credential_secret = forms.CharField(widget=forms.PasswordInput)


class ApplicationCredentialAuthenticator(OpenStackFormAuthenticator):
    """
    Authenticator that authenticates with an OpenStack cloud using an application
    credential.
    """

    authenticator_type = "openstack_application_credential"

    form_class = ApplicationCredentialForm

    def get_identity(self, auth_data, selected_option=None):
        return dict(
            methods=["application_credential"],
            application_credential=dict(
                id=auth_data["application_credential_id"],
                secret=auth_data["application_credential_secret"],
            ),
        )


class FederatedAuthenticator(RedirectAuthenticator):
    """
    Authenticator that authenticates with an OpenStack cloud using federated identity.

    The way federated authentication with Keystone works is that we redirect to a
    Keystone URL under /v3/auth/OS-FEDERATION, specifying where we want the token to
    be sent. Keystone then negotiates the external authentication before rendering
    an auto-submitting form that sends the token back to us using a cross-domain
    POST request.
    """

    PROVIDER_PROTOCOL_TPL = (
        "{auth_url}/auth/OS-FEDERATION/identity_providers/{provider}/protocols/"
        "{protocol}/websso"
    )
    PROTOCOL_ONLY_TPL = "{auth_url}/auth/OS-FEDERATION/websso/{protocol}"

    authenticator_type = "openstack_federation"

    uses_crossdomain_post_requests = True

    def __init__(self, auth_url, identity_providers):
        self.auth_url = normalize_auth_url(auth_url)
        self.identity_providers = identity_providers

    def get_options(self):
        return [
            (provider["name"], provider.get("label") or provider["name"])
            for provider in self.identity_providers
        ]

    def get_redirect_to(self, request, auth_complete_url, selected_option=None):
        provider_cfg = next(
            p for p in self.identity_providers if p["name"] == selected_option
        )
        # Provider is optional, protocol is not
        provider = provider_cfg.get("provider")
        protocol = provider_cfg["protocol"]
        # Template out the federation URL
        template = self.PROVIDER_PROTOCOL_TPL if provider else self.PROTOCOL_ONLY_TPL
        self.federation_url = template.format(
            auth_url=self.auth_url, provider=provider, protocol=protocol
        )
        return "{}?{}".format(
            self.federation_url, urlencode({"origin": auth_complete_url})
        )

    def auth_complete(self, request, selected_option=None):
        # The token should be in the POST data
        return request.POST.get("token")
