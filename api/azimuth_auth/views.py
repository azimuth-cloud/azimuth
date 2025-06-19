"""
Views for the Azimuth auth package.
"""

import json
import unicodedata
from urllib.parse import urlencode, urlparse

from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt, csrf_protect
from django.views.decorators.http import require_http_methods, require_safe

from .forms import AuthenticatorSelectForm, authenticator_choices
from .settings import auth_settings


def url_has_allowed_host_and_scheme(url, allowed_domains, require_https=False):
    """
    Modified version of Django's url_has_allowed_host_and_scheme that allows us to
    validate against wildcard domains.

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
        url=next_url,
        allowed_domains={request.get_host(), *auth_settings.NEXT_URL_ALLOWED_DOMAINS},
        require_https=request.is_secure(),
    )
    return next_url if url_is_safe else auth_settings.NEXT_URL_DEFAULT_URL


def set_next_url_cookie(response, next_url, secure):
    """
    Sets the next URL cookie on the given response to the given URL.

    We use a separate cookie rather than using the session because in order for some
    authenticators to redirect correctly (e.g. OpenStack federation) we need to be able
    to access the next URL from a cross-domain POST request. This requires storing
    the URL in a cookie with SameSite="None", which we don't want to do with the
    session cookie. However the next URL is not sensitive data, and is checked for
    safety anyway, so it can go in a cross-domain cookie.
    """
    if next_url:
        response.set_signed_cookie(
            auth_settings.NEXT_URL_COOKIE_NAME,
            next_url,
            httponly=True,
            secure=secure,
            samesite=(
                "None"
                if any(
                    a["AUTHENTICATOR"].uses_crossdomain_post_requests
                    for a in auth_settings.AUTHENTICATORS
                )
                else "Lax"
            ),
        )
    else:
        response.delete_cookie(auth_settings.NEXT_URL_COOKIE_NAME)
    return response


def redirect_to_login(code=None, force_change_method=False):
    """
    Redirect to the login endpoint, with an optional code and/or forcing a change of
    method.
    """
    redirect_to = reverse("azimuth_auth:login")
    params = {}
    if code:
        params[auth_settings.MESSAGE_CODE_PARAM] = code
    if force_change_method:
        params[auth_settings.CHANGE_METHOD_PARAM] = "1"
    if params:
        redirect_to = "{}?{}".format(redirect_to, urlencode(params))
    return redirect(redirect_to)


def redirect_to_start(authenticator_choice, code=None):
    """
    Redirect to the specified authenticator choice with an optional code.
    """
    # If the choice is of the form <name>/<option>, then we need to include the option
    # as a GET parameter in the URL that we redirect to
    if "/" in authenticator_choice:
        authenticator, option = authenticator_choice.split("/", maxsplit=1)
    else:
        authenticator = authenticator_choice
        option = None
    redirect_to = reverse("azimuth_auth:start", kwargs={"authenticator": authenticator})
    params = {}
    if option:
        params[auth_settings.SELECTED_OPTION_PARAM] = option
    if code:
        params[auth_settings.MESSAGE_CODE_PARAM] = code
    if params:
        redirect_to = "{}?{}".format(redirect_to, urlencode(params))
    return redirect(redirect_to)


@require_http_methods(["GET"])
def authenticators(request):
    """
    Returns the list of available authenticators, primarily for use by the SDK.
    """
    return JsonResponse(
        {
            a["NAME"]: a["AUTHENTICATOR"].get_representation()
            for a in auth_settings.AUTHENTICATORS
        }
    )


@require_http_methods(["GET", "POST"])
def login(request):
    """
    Begin the authentication flow by selecting an authenticator.
    """
    # For POST requests, process the authenticator selection form
    if request.method == "POST":
        form = AuthenticatorSelectForm(request.POST)
        if form.is_valid():
            authenticator = form.cleaned_data["authenticator"]
            remember = form.cleaned_data.get("remember", False)
            response = redirect_to_start(authenticator)
            if remember:
                response.set_signed_cookie(
                    auth_settings.AUTHENTICATOR_COOKIE_NAME,
                    authenticator,
                    httponly=True,
                    secure=request.is_secure(),
                )
            else:
                response.delete_cookie(auth_settings.AUTHENTICATOR_COOKIE_NAME)
        else:
            response = render(request, "azimuth_auth/select.html", {"form": form})
    # For GET requests, decide if we can redirect or whether we need to show the form
    #   * If there is a remembered choice and no change was requested, use that
    #   * If there is exactly one authenticator, use that
    #   * Otherwise show the selection form
    else:
        valid_authenticator_choices = [choice for choice, _ in authenticator_choices()]
        authenticator_choice = request.get_signed_cookie(
            auth_settings.AUTHENTICATOR_COOKIE_NAME, None
        )
        if (
            authenticator_choice
            and authenticator_choice in valid_authenticator_choices
            and request.GET.get(auth_settings.CHANGE_METHOD_PARAM, "0") == "0"
        ):
            response = redirect_to_start(authenticator_choice)
        elif len(valid_authenticator_choices) == 1:
            response = redirect_to_start(valid_authenticator_choices[0])
        else:
            form = AuthenticatorSelectForm()
            response = render(request, "azimuth_auth/select.html", {"form": form})
    # Whatever our response, make sure we set the next URL cookie
    return set_next_url_cookie(response, get_next_url(request), request.is_secure())


@require_safe
def start(request, authenticator):
    """
    Start an interactive, i.e. browser-based, authentication flow for the authenticator.
    """
    # First, verify that the requested authenticator exists
    try:
        authenticator_obj = next(
            a["AUTHENTICATOR"]
            for a in auth_settings.AUTHENTICATORS
            if a["NAME"] == authenticator
        )
    except StopIteration:
        return redirect_to_login("invalid_authentication_method", True)
    # If the authenticator provides options, require that one is present
    valid_options = set(opt for opt, _ in authenticator_obj.get_options())
    if valid_options:
        try:
            # Then see if there is an option and validate that
            option = request.GET[auth_settings.SELECTED_OPTION_PARAM]
        except KeyError:
            return redirect_to_login("invalid_authentication_method", True)
        if option not in valid_options:
            return redirect_to_login("invalid_authentication_method", True)
    else:
        option = None
    # Stash the selected option in the session
    if option:
        request.session[auth_settings.SELECTED_OPTION_SESSION_KEY] = option
    else:
        request.session.pop(auth_settings.SELECTED_OPTION_SESSION_KEY, None)
    # Ask the authenticator to begin the authentication process
    return authenticator_obj.auth_start(
        request,
        request.build_absolute_uri(
            reverse("azimuth_auth:complete", kwargs={"authenticator": authenticator})
        ),
        option,
    )


@require_http_methods(["GET", "POST"])
@csrf_exempt
def complete(request, authenticator):
    """
    Complete an interactive, i.e. browser-based, authentication flow for the
    authenticator.
    """
    try:
        authenticator_obj = next(
            a["AUTHENTICATOR"]
            for a in auth_settings.AUTHENTICATORS
            if a["NAME"] == authenticator
        )
    except StopIteration:
        return redirect_to_login("invalid_authentication_method", True)

    def handle_request(request):
        # If the authenticator provides options, make sure we have a valid selection
        valid_options = set(opt for opt, _ in authenticator_obj.get_options())
        if valid_options:
            try:
                option = request.session[auth_settings.SELECTED_OPTION_SESSION_KEY]
            except KeyError:
                return redirect_to_login("invalid_authentication_method", True)
            if option not in valid_options:
                return redirect_to_login("invalid_authentication_method", True)
        else:
            option = None
        # Ask the authenticator to produce a token from the request
        token = authenticator_obj.auth_complete(request, option)
        if token:
            # On a successful authentication, store the token in the session
            request.session[auth_settings.TOKEN_SESSION_KEY] = token
            # Unset the stored option
            request.session.pop(auth_settings.SELECTED_OPTION_SESSION_KEY, None)
            # Either redirect or return to the next URL
            next_url = get_next_url(request)
            if next_url:
                response = redirect(next_url)
            else:
                response = render(request, "azimuth_auth/complete.html")
            # On a successful authentication, we also want to clear the next URL cookie
            return set_next_url_cookie(response, None, request.is_secure())
        else:
            # On a failed authentication redirect back to the start for the
            # authenticator, but indicate that the authentication failed
            return redirect_to_start(
                f"{authenticator}/{option}" if option else authenticator,
                authenticator_obj.failure_code,
            )

    # Enable CSRF protection unless it will break the authenticator
    if not authenticator_obj.uses_crossdomain_post_requests:
        handle_request = csrf_protect(handle_request)
    return handle_request(request)


@require_http_methods(["POST"])
@csrf_exempt
def token(request, authenticator):
    """
    Use the authenticator to get a token in a non-interactive flow, e.g. for the SDK.
    """
    try:
        authenticator_obj = next(
            a["AUTHENTICATOR"]
            for a in auth_settings.AUTHENTICATORS
            # Some authenticators, e.g. openstack_federation, can only be used
            # interactively
            if a["NAME"] == authenticator and not a["AUTHENTICATOR"].interactive_only
        )
    except StopIteration:
        return JsonResponse(
            {"message": f"Could not find authenticator '{authenticator}'."}, status=404
        )
    # Try to pass the authentication data from the request
    try:
        auth_data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse(
            {"message": "Request does not contain valid JSON."}, status=400
        )
    # If the authenticator has options, a valid option should be given
    valid_options = set(opt for opt, _ in authenticator_obj.get_options())
    if valid_options:
        try:
            option = auth_data.pop("authenticator_option")
        except KeyError:
            return JsonResponse(
                {"message": "Authenticator option is required."}, status=400
            )
        if option not in valid_options:
            return JsonResponse(
                {"message": "Given authenticator option is not valid."}, status=400
            )
    else:
        option = None
    # The auth_token method of the authenticator should return a token or null
    # depending on whether the given auth data is valid or not
    token = authenticator_obj.auth_token(auth_data, option)
    if token:
        return JsonResponse(
            {
                "authenticator_type": authenticator_obj.authenticator_type,
                "authenticator": authenticator,
                "authenticator_option": option,
                "token": token,
            },
            status=201,
        )
    else:
        return JsonResponse({"message": "Invalid credentials provided."}, status=401)


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
        return render(
            request, "azimuth_auth/logout_confirm.html", dict(next_url=next_url)
        )
