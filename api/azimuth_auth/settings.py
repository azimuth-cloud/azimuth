"""
Settings for the Azimuth auth package.
"""

from settings_object import SettingsObject, Setting, MergedDictSetting, ObjectFactorySetting


class AzimuthAuthSettings(SettingsObject):
    """
    Settings object for the ``AZIMUTH_AUTH`` setting.
    """
    #: The authenticator to use
    AUTHENTICATOR = ObjectFactorySetting()

    #: The name of the header in which to place the token for downstream code
    DOWNSTREAM_TOKEN_HEADER = Setting(default = "HTTP_X_CLOUD_TOKEN")

    #: For the bearer token middleware, this is the name of the header that the token will be in
    BEARER_TOKEN_HEADER = Setting(default = "HTTP_AUTHORIZATION")
    #: For the bearer token middleware, this is the prefix that will be present and needs to be stripped
    BEARER_TOKEN_PREFIX = Setting(default = "Bearer")

    #: For the session middleware, this is the name of the session key in which the token is stored
    TOKEN_SESSION_KEY = Setting(default = "token")
    #: For the session middleware, this is the amount of time, in seconds, before the token expires that
    #: middleware will attempt to refresh it
    #: Defaults to 10 minutes if not given
    TOKEN_REFRESH_INTERVAL = Setting(default = 600)

    #: The HTTP parameter to get the next URL from
    NEXT_URL_PARAM = Setting(default = "next")
    #: The session key to store the next URL
    NEXT_URL_COOKIE_NAME = Setting(default = "next-url")
    #: The allowed domains for the next URL
    NEXT_URL_ALLOWED_DOMAINS = Setting(default = set)
    #: The default next URL if the user-supplied URL is not given or not permitted
    NEXT_URL_DEFAULT_URL = Setting(default = "/dashboard")

    #: The HTTP parameter to get the message code from
    MESSAGE_CODE_PARAM = Setting(default = "code")
    #: The default message level
    DEFAULT_MESSAGE_LEVEL = Setting(default = "danger")
    #: The messages to use for each code
    #: Each item can be either a string or a dict with a string and a level
    MESSAGES = MergedDictSetting({
        "session_expired": "Your session has expired. Please sign in again.",
        "invalid_credentials": "The provided credentials are invalid. Please try again.",
        "logout_successful": { "message": "You have been signed out.", "level": "success" },
    })


auth_settings = AzimuthAuthSettings("AZIMUTH_AUTH")
