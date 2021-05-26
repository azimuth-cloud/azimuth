"""
Views for the cloud-auth package.
"""

from urllib.parse import urlencode

from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_http_methods, require_safe

from .settings import auth_settings


def get_next_url(request):
    """
    Return the next URL to go to if one is present in the session, GET or POST data
    and is safe to use.
    """
    if auth_settings.NEXT_URL_PARAM in request.POST:
        next_url = request.POST[auth_settings.NEXT_URL_PARAM]
    elif auth_settings.NEXT_URL_PARAM in request.GET:
        next_url = request.GET[auth_settings.NEXT_URL_PARAM]
    else:
        # URLs in the session are single use
        next_url = request.session.pop(auth_settings.NEXT_URL_SESSION_KEY, None)
    url_is_safe = url_has_allowed_host_and_scheme(
        url = next_url,
        allowed_hosts = { request.get_host(), *auth_settings.NEXT_URL_ALLOWED_HOSTS },
        require_https = request.is_secure(),
    )
    return next_url if url_is_safe else None


def redirect_to_login(code = None):
    """
    Redirect to the login endpoint with an optional code.
    """
    redirect_to = reverse('cloud_auth:login')
    if code:
        redirect_to = "{}?{}".format(
            redirect_to,
            urlencode({ auth_settings.MESSAGE_CODE_PARAM: code })
        )
    return redirect(redirect_to)


@require_safe
def login(request):
    """
    Begin the authentication flow for the configured authenticator.
    """
    # Store the next URL in the session for use at the end of the authentication
    next_url = get_next_url(request)
    if next_url:
        request.session[auth_settings.NEXT_URL_SESSION_KEY] = next_url
    else:
        request.session.pop(auth_settings.NEXT_URL_SESSION_KEY, None)
    return auth_settings.AUTHENTICATOR.auth_start(request)


@require_http_methods(["GET", "POST"])
def complete(request):
    """
    Complete the authentication flow for the configured authenticator.
    """
    # The auth_complete method of the authenticator should return a token or null
    # depending on whether authentication was successful
    token = auth_settings.AUTHENTICATOR.auth_complete(request)
    if token:
        # On a successful authentication, store the token in the session
        request.session[auth_settings.SESSION_TOKEN_KEY] = token
        # Either redirect or return to the next URL
        next_url = get_next_url(request)
        if next_url:
            return redirect(next_url)
        else:
            return render(request, 'cloud_auth/complete.html')
    else:
        # On a failed authentication, redirect to login but indicate that the auth failed
        return redirect_to_login('invalid_credentials')


@require_http_methods(["GET", "POST"])
def logout(request):
    """
    Terminate the current session.
    """
    next_url = get_next_url(request)
    # On a POST request, flush the session and redirect
    if request.method == "POST":
        request.session.flush()
        if next_url:
            return redirect(next_url)
        else:
            return redirect_to_login('logout_successful')
    else:
        # On GET requests, show the confirm page
        return render(request, "cloud_auth/logout_confirm.html", dict(next_url = next_url))
