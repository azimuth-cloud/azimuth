from django import http

from ..settings import auth_settings

from . import base


class Provider(base.Provider):
    """
    Authentication session provider for external auth.
    """
    def __init__(self, user_header: str, groups_header: str):
        self.user_header = user_header
        self.groups_header = groups_header

    def from_request(self, request: http.HttpRequest) -> 'Session':
        raise RuntimeError("error from external auth provider")


class Session(base.Session):
    """
    Authentication session implementation for external authentication.

    Looks for user and group headers in the request, provided by an external auth callout.
    """
