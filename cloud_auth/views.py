"""
Views for the cloud-auth package.
"""

from urllib.parse import urlencode

from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.csrf import csrf_exempt, csrf_protect
from django.views.decorators.http import require_http_methods, require_safe

from .settings import auth_settings


def get_next_url(request):
    """
    Return the next URL to go to if one is present in the cookie, GET or POST data
    and is safe to use.
    """
    if auth_settings.NEXT_URL_PARAM in request.POST:
        next_url = request.POST[auth_settings.NEXT_URL_PARAM]
    elif auth_settings.NEXT_URL_PARAM in request.GET:
        next_url = request.GET[auth_settings.NEXT_URL_PARAM]
    else:
        next_url = request.get_signed_cookie(auth_settings.NEXT_URL_COOKIE_NAME, None)
    url_is_safe = url_has_allowed_host_and_scheme(
        url = next_url,
        allowed_hosts = { request.get_host(), *auth_settings.NEXT_URL_ALLOWED_HOSTS },
        require_https = request.is_secure(),
    )
    return next_url if url_is_safe else auth_settings.NEXT_URL_DEFAULT_URL


def set_next_url_cookie(response, next_url, secure):
    """
    Sets the next URL cookie on the given response to the given URL.

    We use a separate cookie rather than using the session because in order for some
    authenticators to redirect correctly (e.g. OpenStack federation) we need to be able
    to access the next URL from a cross-domain POST request. This requires storing
    the URL in a cookie with SameSite='None', which we don't want to do with the
    session cookie. However the next URL is not sensitive data, and is checked for safety
    anyway, so it can go in a cross-domain cookie.
    """
    if next_url:
        response.set_signed_cookie(
            auth_settings.NEXT_URL_COOKIE_NAME,
            next_url,
            httponly = True,
            secure = secure,
            samesite = (
                'None'
                if auth_settings.AUTHENTICATOR.uses_crossdomain_post_requests
                else 'Lax'
            )
        )
    else:
        response.delete_cookie(auth_settings.NEXT_URL_COOKIE_NAME)
    return response


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
    next_url = get_next_url(request)
    response = auth_settings.AUTHENTICATOR.auth_start(request)
    return set_next_url_cookie(response, next_url, request.is_secure())


@require_http_methods(["GET", "POST"])
@csrf_exempt
def complete(request):
    """
    Complete the authentication flow for the configured authenticator.
    """
    def handle_request(request):
        # The auth_complete method of the authenticator should return a token or null
        # depending on whether authentication was successful
        token = auth_settings.AUTHENTICATOR.auth_complete(request)
        if token:
            # On a successful authentication, store the token in the session
            request.session[auth_settings.TOKEN_SESSION_KEY] = token
            # Either redirect or return to the next URL
            next_url = get_next_url(request)
            if next_url:
                response = redirect(next_url)
            else:
                response = render(request, 'cloud_auth/complete.html')
            # On a successful authentication, we also want to clear the next URL cookie
            return set_next_url_cookie(response, None, request.is_secure())
        else:
            # On a failed authentication, redirect to login but indicate that the auth failed
            return redirect_to_login('invalid_credentials')
    # Enable CSRF protection unless it will break the authenticator
    if not auth_settings.AUTHENTICATOR.uses_crossdomain_post_requests:
        handle_request = csrf_protect(handle_request)
    return handle_request(request)


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
