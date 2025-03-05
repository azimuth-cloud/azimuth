import importlib
import itertools
import time

from django.conf import settings
from django.contrib.sessions.backends.base import UpdateError
from django.contrib.sessions.exceptions import SessionInterrupted
from django.utils.cache import patch_vary_headers
from django.utils.http import http_date


# The maximum number of characters that can go into a single cookie
# The max is usually 4096 including the cookie name, so this should give some leeway
MAX_COOKIE_LENGTH = 4000


class SessionMiddleware:
    """
    Middleware class that initialises the session backend from state that is possibly
    split over multiple cookies.
    """
    def __init__(self, get_response):
        self.get_response = get_response
        # Load the session store
        engine = importlib.import_module(settings.SESSION_ENGINE)
        self.SessionStore = engine.SessionStore

    def get_session_cookie_data(self, request):
        """
        Returns the combined data from all the session cookies in the request.
        """
        # If the exact cookie name is present in the session, use that
        if settings.SESSION_COOKIE_NAME in request.COOKIES:
            return request.COOKIES[settings.SESSION_COOKIE_NAME]
        # If not, use the session cookie name as a prefix and look up cookies of
        # the form "<cookie name>_{0,1,2,3}" until they no longer exist
        data = ""
        for index in itertools.count():
            cookie_name = f"{settings.SESSION_COOKIE_NAME}_{index}"
            if cookie_name in request.COOKIES:
                data = data + request.COOKIES[cookie_name]
            else:
                break
        # Make sure we return none instead of an empty string
        return data or None

    def set_session_cookies(self, request, response, data, max_age, expires):
        """
        Sets the session cookies required to store the given data.
        """
        # Start with a set of the session cookies currently in the request
        # At the end of this method, we need to remove any cookies still in the set
        cookies_to_remove = {
            name
            for name in request.COOKIES.keys()
            if name.startswith(settings.SESSION_COOKIE_NAME)
        }
        if len(data) < MAX_COOKIE_LENGTH:
            # If the whole data fits in a single cookie, just use the cookie name
            response.set_cookie(
                settings.SESSION_COOKIE_NAME,
                data,
                max_age = max_age,
                expires = expires,
                domain = settings.SESSION_COOKIE_DOMAIN,
                path = settings.SESSION_COOKIE_PATH,
                secure = settings.SESSION_COOKIE_SECURE or None,
                httponly = settings.SESSION_COOKIE_HTTPONLY or None,
                samesite = settings.SESSION_COOKIE_SAMESITE,
            )
            cookies_to_remove.discard(settings.SESSION_COOKIE_NAME)
        else:
            # If not, write cookies with chunks of data until there is no data left
            for index in itertools.count():
                cookie_name = f"{settings.SESSION_COOKIE_NAME}_{index}"
                response.set_cookie(
                    cookie_name,
                    data[:MAX_COOKIE_LENGTH],
                    max_age = max_age,
                    expires = expires,
                    domain = settings.SESSION_COOKIE_DOMAIN,
                    path = settings.SESSION_COOKIE_PATH,
                    secure = settings.SESSION_COOKIE_SECURE or None,
                    httponly = settings.SESSION_COOKIE_HTTPONLY or None,
                    samesite = settings.SESSION_COOKIE_SAMESITE,
                )
                cookies_to_remove.discard(cookie_name)
                data = data[MAX_COOKIE_LENGTH:]
                if not data:
                    break
        # Remove any cookies that are no longer required
        for cookie_name in cookies_to_remove:
            response.delete_cookie(
                cookie_name,
                path = settings.SESSION_COOKIE_PATH,
                domain = settings.SESSION_COOKIE_DOMAIN,
                samesite = settings.SESSION_COOKIE_SAMESITE,
            )

    def delete_session_cookies(self, request, response):
        """
        Configures the response to remove all session cookies present in the request.
        """
        # Delete every cookie that has the session cookie name as a prefix
        for cookie_name in request.COOKIES.keys():
            if cookie_name.startswith(settings.SESSION_COOKIE_NAME):
                response.delete_cookie(
                    cookie_name,
                    path = settings.SESSION_COOKIE_PATH,
                    domain = settings.SESSION_COOKIE_DOMAIN,
                    samesite = settings.SESSION_COOKIE_SAMESITE,
                )

    def __call__(self, request):
        # NOTE(mkjpryor)
        # Most of this code is borrowed from the Django session middleware
        # https://github.com/django/django/blob/main/django/contrib/sessions/middleware.py

        # Initialise the session store from the cookie(s)
        session_key = self.get_session_cookie_data(request)
        request.session = self.SessionStore(session_key)
        # Get the response
        response = self.get_response(request)
        # Save the session if required
        try:
            accessed = request.session.accessed
            modified = request.session.modified
            empty = request.session.is_empty()
        except AttributeError:
            return response
        # If the session is empty, remove all the session cookies
        # If not, save the session if it has been modified or configured to save every request
        if empty:
            self.delete_session_cookies(request, response)
            patch_vary_headers(response, ("Cookie",))
        else:
            if accessed:
                patch_vary_headers(response, ("Cookie",))
            if modified or settings.SESSION_SAVE_EVERY_REQUEST:
                if request.session.get_expire_at_browser_close():
                    max_age = None
                    expires = None
                else:
                    max_age = request.session.get_expiry_age()
                    expires_time = time.time() + max_age
                    expires = http_date(expires_time)
                # Save the session data and refresh the client cookie.
                # Skip session save for 5xx responses.
                if response.status_code < 500:
                    try:
                        request.session.save()
                    except UpdateError:
                        raise SessionInterrupted(
                            "The request's session was deleted before the "
                            "request completed. The user may have logged "
                            "out in a concurrent request, for example."
                        )
                    self.set_session_cookies(
                        request,
                        response,
                        request.session.session_key,
                        max_age,
                        expires
                    )
        return response
