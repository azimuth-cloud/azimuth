"""
Module containing authenticators for OpenStack clouds.
"""

from urllib.parse import urlencode

from django.shortcuts import redirect
from django.urls import reverse

import requests

from .base import BaseAuthenticator
from .form import FormAuthenticator


class OpenStackAuthenticator(BaseAuthenticator):
    """
    Base class for OpenStack authenticators.
    """
    def __init__(self, auth_url, verify_ssl = True):
        self.auth_url = auth_url.rstrip('/')
        self.token_url = f"{self.auth_url}/auth/tokens"
        self.verify_ssl = verify_ssl

    def refresh_token(self, token):
        response = requests.post(
            self.token_url,
            json = dict(
                auth = dict(
                    identity = dict(
                        methods = ['token'],
                        token = dict(id = token)
                    )
                )
            ),
            verify = self.verify_ssl
        )
        # If the response is a success, return the token
        if response.status_code == 201:
            token = response.headers['X-Subject-Token']
            expires = response.json()['token']['expires_at']
            return token, expires
        # For all other statuses, raise the corresponding exception
        response.raise_for_status()


class PasswordAuthenticator(OpenStackAuthenticator, FormAuthenticator):
    """
    Authenticator that authenticates with an OpenStack cloud using the
    password authentication method.
    """
    def __init__(self, auth_url, domain = 'default', verify_ssl = True):
        super().__init__(auth_url, verify_ssl)
        self.domain = domain

    def authenticate(self, form_data):
        # Authenticate the user by submitting an appropriate request to the token URL
        response = requests.post(
            self.token_url,
            json = dict(
                auth = dict(
                    identity = dict(
                        methods = ['password'],
                        password = dict(
                            user = dict(
                                domain = dict(name = self.domain),
                                name = form_data['username'],
                                password = form_data['password']
                            )
                        )
                    )
                )
            ),
            verify = self.verify_ssl
        )
        # If the response is a success, return the token
        if response.status_code == 201:
            token = response.headers['X-Subject-Token']
            expires = response.json()['token']['expires_at']
            return token, expires
        # If the response is an authentication error, return null
        if response.status_code == 401:
            return None
        # For all other statuses, raise the corresponding exception
        response.raise_for_status()


class FederatedAuthenticator(OpenStackAuthenticator):
    """
    Authenticator that authenticates with an OpenStack cloud using federated identity.

    The way federated authentication with Keystone works is that we redirect to a
    Keystone URL under /v3/auth/OS-FEDERATION, specifying where we want the token to
    be sent. Keystone then negotiates the external authentication before rendering
    an auto-submitting form that sends the token back to us using a cross-domain
    POST request.
    """
    uses_crossdomain_post_requests = True

    def __init__(self, auth_url, provider, verify_ssl = True):
        super().__init__(auth_url, verify_ssl)
        self.federation_url = "{}/auth/OS-FEDERATION/websso/{}".format(self.auth_url, provider)

    def auth_start(self, request):
        origin_url = request.build_absolute_uri(reverse('azimuth_auth:complete'))
        redirect_url = "{}?{}".format(self.federation_url, urlencode({ 'origin': origin_url }))
        return redirect(redirect_url)

    def auth_complete(self, request):
        # The token should be in the POST data
        token = request.POST.get('token')
        if not token:
            return None
        # Because we only receive the token, we need to make another request to check when it expires
        response = requests.get(
            self.token_url,
            headers = { 'X-Auth-Token': token, 'X-Subject-Token': token },
            verify = self.verify_ssl
        )
        # If the response is a success, return the token
        if response.status_code == 200:
            expires = response.json()['token']['expires_at']
            return token, expires
        # For all other statuses, raise the corresponding exception
        response.raise_for_status()
