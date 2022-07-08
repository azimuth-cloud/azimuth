"""
Module containing authenticators for OpenStack clouds.
"""

from urllib.parse import urlencode

from django import forms
from django.shortcuts import redirect

import requests

from .base import BaseAuthenticator
from .form import FormAuthenticator
from .redirect import RedirectAuthenticator


class OpenStackFormAuthenticator(FormAuthenticator):
    """
    Base class for OpenStack authenticators that use a form to authenticate.
    """
    def __init__(self, auth_url, verify_ssl = True):
        self.auth_url = auth_url.rstrip('/')
        self.token_url = f"{self.auth_url}/auth/tokens"
        self.verify_ssl = verify_ssl

    def get_identity(self, form_data):
        """
        Returns the identity to use for the token request, derived from the form data.
        """
        raise NotImplementedError

    def authenticate(self, form_data):
        # Authenticate the user by submitting an appropriate request to the token URL
        response = requests.post(
            self.token_url,
            json = dict(auth = dict(identity = self.get_identity(form_data))),
            verify = self.verify_ssl
        )
        # If the response is a success, return the token
        if response.status_code == 201:
            return response.headers['X-Subject-Token']
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
    def __init__(self, auth_url, domain = 'default', verify_ssl = True):
        super().__init__(auth_url, verify_ssl)
        self.domain = domain

    def get_identity(self, form_data):
        return dict(
            methods = ['password'],
            password = dict(
                user = dict(
                    domain = dict(name = self.domain),
                    name = form_data['username'],
                    password = form_data['password']
                )
            )
        )


class ApplicationCredentialForm(forms.Form):
    """
    Form for authenticating with an application credential.
    """
    application_credential_id = forms.CharField()
    application_credential_secret = forms.CharField(widget = forms.PasswordInput)


class ApplicationCredentialAuthenticator(OpenStackFormAuthenticator):
    """
    Authenticator that authenticates with an OpenStack cloud using an application credential.
    """
    form_class = ApplicationCredentialForm

    def get_identity(self, form_data):
        return dict(
            methods = ['application_credential'],
            application_credential = dict(
                id = form_data['application_credential_id'],
                secret = form_data['application_credential_secret']
            )
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
    uses_crossdomain_post_requests = True

    def __init__(self, auth_url, provider):
        self.federation_url = "{}/auth/OS-FEDERATION/websso/{}".format(auth_url, provider)

    def get_redirect_to(self, request, auth_complete_url):
        return "{}?{}".format(self.federation_url, urlencode({ 'origin': auth_complete_url }))

    def auth_complete(self, request):
        # The token should be in the POST data
        return request.POST.get('token')
