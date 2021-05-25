"""
Module containing authenticators for OpenStack clouds.
"""

import requests

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
