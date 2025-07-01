"""
Module containing the base class for authenticators that begin with a redirection.
"""

from django.shortcuts import redirect, render

from ..settings import auth_settings  # noqa: TID252
from .base import BaseAuthenticator


class RedirectAuthenticator(BaseAuthenticator):
    """
    Base class for an authenticator that begins with a redirection.

    Its main purpose is to ensure that we can break a redirection loop when an
    authentication fails.
    """

    # Authentications that begin with a redirect require a browser
    interactive_only = True

    failure_code = "external_auth_failed"
    failure_template = "azimuth_auth/external_auth_failed.html"

    def get_redirect_to(self, request, auth_complete_url, selected_option=None):
        """
        Return the URL for the redirection to begin the auth process.
        """
        raise NotImplementedError

    def auth_start(self, request, auth_complete_url, selected_option=None):
        # If a code is set, render an error page with an option to switch
        # If not, do the redirect
        if request.GET.get(auth_settings.MESSAGE_CODE_PARAM, None):
            return render(
                request, self.failure_template, {"try_again_link": request.path_info}
            )
        else:
            return redirect(
                self.get_redirect_to(request, auth_complete_url, selected_option)
            )
