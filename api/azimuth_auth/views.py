"""
Views for the Azimuth auth package.
"""

import unicodedata
from urllib.parse import urlparse, urlencode

from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt, csrf_protect
from django.views.decorators.http import require_http_methods, require_safe

from .settings import auth_settings


def url_has_allowed_host_and_scheme(url, allowed_domains, require_https = False):
    """
    Modified version of Django's url_has_allowed_host_and_scheme that allows us to validate
    against wildcard domains.

    https://github.com/django/django/blob/ba9ced3e9a643a05bc521f0a2e6d02e3569de374/django/utils/http.py#L239
    """
    if url is not None:
        url = url.strip()
    if not url:
        return False
    # Chrome considers any URL with more than two slashes to be absolute, but
    # urlparse is not so flexible. Treat any url with three slashes as unsafe.
    if url.startswith("///"):
        return False
    try:
        url_info = urlparse(url)
    except ValueError:  # e.g. invalid IPv6 addresses
        return False
    # Forbid URLs like http:///example.com - with a scheme, but without a hostname.
    # In that URL, example.com is not the hostname but, a path component. However,
    # Chrome will still consider example.com to be the hostname, so we must not
    # allow this syntax
    if not url_info.netloc and url_info.scheme:
        return False
    # Forbid URLs that start with control characters. Some browsers (like
    # Chrome) ignore quite a few control characters at the start of a
    # URL and might consider the URL as scheme relative
    if unicodedata.category(url[0])[0] == "C":
        return False
    scheme = url_info.scheme
    # Consider URLs without a scheme (e.g. //example.com/p) to be http
    if not url_info.scheme and url_info.netloc:
        scheme = "http"
    # Reject URLs that have a scheme that we don't like
    valid_schemes = ["https"] if require_https else ["http", "https"]
    if scheme and scheme not in valid_schemes:
        return False
    # If we get this far, check the host
    # First, we allow any relative URLs
    if not url_info.netloc:
        return True
    # Then check whether the host is in any of our domains
    return any(url_info.netloc.endswith(domain) for domain in allowed_domains)


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
        allowed_domains = { request.get_host(), *auth_settings.NEXT_URL_ALLOWED_DOMAINS },
        require_https = request.is_secure(),
    )
    return next_url if url_is_safe else auth_settings.NEXT_URL_DEFAULT_URL


def set_next_url_cookie(response, next_url, secure):
    """
    Sets the next URL cookie on the given response to the given URL.

    We use a separate cookie rather than using the session because in order for some
    authenticators to redirect correctly (e.g. OpenStack federation) we need to be able
    to access the next URL from a cross-domain POST request. This requires storing
    the URL in a cookie with SameSite="None", which we don't want to do with the
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
                "None"
                if auth_settings.AUTHENTICATOR.uses_crossdomain_post_requests
                else "Lax"
            )
        )
    else:
        response.delete_cookie(auth_settings.NEXT_URL_COOKIE_NAME)
    return response


def redirect_to_login(code = None):
    """
    Redirect to the login endpoint with an optional code.
    """
    redirect_to = reverse("azimuth_auth:login")
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
                response = render(request, "azimuth_auth/complete.html")
            # On a successful authentication, we also want to clear the next URL cookie
            return set_next_url_cookie(response, None, request.is_secure())
        else:
            # On a failed authentication, redirect to login but indicate that the auth failed
            return redirect_to_login("invalid_credentials")
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
            return redirect_to_login("logout_successful")
    else:
        # On GET requests, show the confirm page
        return render(request, "azimuth_auth/logout_confirm.html", dict(next_url = next_url))
