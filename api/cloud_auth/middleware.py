"""
Django middlewares for the cloud-auth package.
"""

from datetime import datetime, timedelta
import logging

from dateutil import parser, tz

from .settings import auth_settings


logger = logging.getLogger(__name__)


class BaseMiddleware:
    """
    Base class for other cloud-auth middlewares.

    Each cloud-auth middleware implements a particular method by which a token
    may be provided, e.g. bearer tokens or session data.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def get_token(self, request):
        """
        Get the current token from the request. May return null if no token is present.
        """
        raise NotImplementedError

    def __call__(self, request):
        token = self.get_token(request)
        if token:
            request.META[auth_settings.DOWNSTREAM_TOKEN_HEADER] = token
        return self.get_response(request)


class BearerTokenMiddleware(BaseMiddleware):
    """
    Middleware that reads token information from a bearer token.
    """
    def get_token(self, request):
        header = request.META.get(auth_settings.BEARER_TOKEN_HEADER, "").strip()
        # If no prefix is configured, use an empty string
        # This means that startswith always returns true and removeprefix does nothing
        prefix = auth_settings.BEARER_TOKEN_PREFIX or ""
        if header and header.startswith(prefix):
            return header.removeprefix(prefix).strip()


class SessionTokenMiddleware(BaseMiddleware):
    """
    Middleware that reads token information from the session.
    """
    def get_token(self, request):
        token = request.session.get(auth_settings.TOKEN_SESSION_KEY, None)
        if token:
            token, expires = token
            # If expires is present, it should be an ISO-formatted string
            # If it is not present, the token is assumed to have no expiry
            if expires:
                now = datetime.now(tz.UTC)
                expires = parser.isoparse(expires)
                delta = timedelta(seconds = auth_settings.TOKEN_REFRESH_INTERVAL)
                # Try to refresh the token if it is within the delta of expiring but not already expired
                if now < expires < now + delta:
                    logger.info('Attempting to refresh expiring token')
                    try:
                        token, expires = auth_settings.AUTHENTICATOR.refresh_token(token)
                    except NotImplementedError:
                        # If token refresh is not implemented, just ignore it
                        logger.info('Authenticator does not support token refresh')
                    except Exception:
                        # Any other exception should be logged, but we still allow the
                        # request to proceed
                        logger.exception('Error occurred during token refresh')
                    else:
                        logger.info('Token refreshed successfully')
                        # Store the refreshed token in the session
                        request.session[auth_settings.TOKEN_SESSION_KEY] = token, expires
                elif now >= expires:
                    logger.info('Token has already expired')
                else:
                    logger.info('Token refresh not required yet')
            return token
        else:
            return None
