"""
Module containing authenticators for OpenStack clouds.
"""

from urllib.parse import urlencode

from django.shortcuts import redirect
from django.urls import reverse

import requests

from .base import BaseAuthenticator
from .form import FormAuthenticator


class PasswordAuthenticator(FormAuthenticator):
    """
    Authenticator that authenticates with an OpenStack cloud using the
    password authentication method.
    """
    def __init__(self, auth_url, domain = 'default', verify_ssl = True):
        self.token_url = auth_url.rstrip('/') + '/auth/tokens'
        self.domain = domain
        self.verify_ssl = verify_ssl

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
            return response.headers['X-Subject-Token']
        # If the response is an authentication error, return null
        if response.status_code == 401:
            return None
        # For all other statuses, raise the corresponding exception
        response.raise_for_status()


class FederatedAuthenticator(BaseAuthenticator):
    """
    Authenticator that authenticates with an OpenStack cloud using federated identity.

    The way federated authentication with Keystone works is that we redirect to a
    Keystone URL under /v3/auth/OS-FEDERATION, specifying where we want the token to
    be sent. Keystone then negotiates the external authentication before rendering
    an auto-submitting form that sends the token back to us using a cross-domain
    POST request.
    """
    uses_crossdomain_post_requests = True

    def __init__(self, federation_url):
        self.federation_url = federation_url

    def auth_start(self, request):
        origin_url = request.build_absolute_uri(reverse('cloud_auth:complete'))
        redirect_url = "{}?{}".format(self.federation_url, urlencode({ 'origin': origin_url }))
        return redirect(redirect_url)

    def auth_complete(self, request):
        # The token should be in the POST data
        return request.POST.get('token')
