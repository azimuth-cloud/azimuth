"""
Views for the Azimuth auth package.
"""

import unicodedata
from urllib.parse import urlparse, urlencode

from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt, csrf_protect
from django.views.decorators.http import require_http_methods, require_safe

from .forms import AuthenticatorSelectForm
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
                if any(
                    a['AUTHENTICATOR'].uses_crossdomain_post_requests
                    for a in auth_settings.AUTHENTICATORS
                )
                else "Lax"
            )
        )
    else:
        response.delete_cookie(auth_settings.NEXT_URL_COOKIE_NAME)
    return response


def redirect_with_code(redirect_to, code = None):
    """
    Redirect to the given URL with an optional code.
    """
    if code:
        redirect_to = "{}?{}".format(
            redirect_to,
            urlencode({ auth_settings.MESSAGE_CODE_PARAM: code })
        )
    return redirect(redirect_to)


def redirect_to_login(code = None):
    """
    Redirect to the login endpoint with an optional code.
    """
    return redirect_with_code(reverse("azimuth_auth:login"), code)


def redirect_to_start(authenticator, code = None):
    """
    Redirect to the specified authenticator with an optional code.
    """
    if any(a["NAME"] == authenticator for a in auth_settings.AUTHENTICATORS):
        return redirect_with_code(
            reverse(
                "azimuth_auth:start",
                kwargs = { "authenticator": authenticator }
            ),
            code
        )
    else:
        return redirect_to_login(code)


@require_http_methods(["GET", "POST"])
def login(request):
    """
    Begin the authentication flow by selecting an authenticator.
    """
    response = None
    # If a remembered authenticator is set and is valid, use it unless we are
    # explicitly changing methods
    authenticator = request.get_signed_cookie(auth_settings.AUTHENTICATOR_COOKIE_NAME, None)
    if (
        authenticator and
        any(a["NAME"] == authenticator for a in auth_settings.AUTHENTICATORS) and
        request.GET.get("change_method", "0") != "1"
    ):
        response = redirect("azimuth_auth:start", authenticator = authenticator)
    elif len(auth_settings.AUTHENTICATORS) > 1:
        # If there are multiple authenticators, render the selection form
        if request.method == "POST":
            form = AuthenticatorSelectForm(request.POST)
            if form.is_valid():
                authenticator = form.cleaned_data["authenticator"]
                remember = form.cleaned_data.get("remember", False)
                # The authenticator returned by the form may be a combination of <name>/<option>
                if "/" in authenticator:
                    authenticator, option = authenticator.split("/", maxsplit = 1)
                else:
                    option = None
                redirect_url = reverse(
                    "azimuth_auth:start",
                    kwargs = { "authenticator": authenticator }
                )
                # If there is an option, include it as a parameter in the redirect
                if option:
                    qs = urlencode({ auth_settings.SELECTED_OPTION_PARAM: option })
                    redirect_url = f"{redirect_url}?{qs}"
                response = redirect(redirect_url)
                if remember:
                    response.set_signed_cookie(
                        auth_settings.AUTHENTICATOR_COOKIE_NAME,
                        authenticator,
                        httponly = True,
                        secure = request.is_secure()
                    )
                else:
                    response.delete_cookie(auth_settings.AUTHENTICATOR_COOKIE_NAME)
                return response
        else:
            form = AuthenticatorSelectForm()
        response = render(request, "azimuth_auth/select.html", { "form": form })
    else:
        # If there is only one authenticator, redirect straight to it
        authenticator = auth_settings.AUTHENTICATORS[0]["NAME"]
        response = redirect("azimuth_auth:start", authenticator = authenticator)
    return set_next_url_cookie(response, get_next_url(request), request.is_secure())


@require_safe
def start(request, authenticator):
    """
    Start the authentication flow for the selected authenticator.
    """
    # First, verify that the requested authenticator exists
    try:
        authenticator_obj = next(
            a["AUTHENTICATOR"]
            for a in auth_settings.AUTHENTICATORS
            if a["NAME"] == authenticator
        )
    except StopIteration:
        return redirect_to_login("invalid_authentication_method")
    # If the authenticator provides options, require that one is present
    valid_options = set(opt for opt, _ in authenticator_obj.get_options())
    if valid_options:
        try:
            # Then see if there is an option and validate that
            option = request.GET[auth_settings.SELECTED_OPTION_PARAM]
        except KeyError:
            return redirect_to_login("invalid_authentication_method")
        if option not in valid_options:
            return redirect_to_login("invalid_authentication_method")
    else:
        option = None
    return authenticator_obj.auth_start(
        request,
        request.build_absolute_uri(
            reverse(
                "azimuth_auth:complete",
                kwargs = { "authenticator": authenticator }
            )
        ),
        option
    )


@require_http_methods(["GET", "POST"])
@csrf_exempt
def complete(request, authenticator):
    """
    Complete the authentication flow for the configured authenticator.
    """
    try:
        authenticator_obj = next(
            a["AUTHENTICATOR"]
            for a in auth_settings.AUTHENTICATORS
            if a["NAME"] == authenticator
        )
    except StopIteration:
        return redirect_to_login("invalid_authentication_method")
    def handle_request(request):
        # The auth_complete method of the authenticator should return a token or null
        # depending on whether authentication was successful
        token = authenticator_obj.auth_complete(request)
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
            return redirect_to_start(authenticator, authenticator_obj.failure_code)
    # Enable CSRF protection unless it will break the authenticator
    if not authenticator_obj.uses_crossdomain_post_requests:
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
