"""
Settings helpers for the ``jasmin_cloud`` Django app.
"""

from django.conf import settings

from settings_object import SettingsObject, Setting, ObjectFactorySetting


class JasminCloudSettings(SettingsObject):
    """
    Settings object for the ``JASMIN_CLOUD`` setting.
    """
    #: The name of the cookie used to store tokens
    TOKEN_COOKIE_NAME = Setting(default = 'provider-token')
    #: Indicates whether the token cookie should be restricted to secure connections
    #: Should always be True in production
    TOKEN_COOKIE_SECURE = Setting(default = True)
    #: Cloud provider configuration
    PROVIDER = ObjectFactorySetting()
    #: SSH key store configuration
    SSH_KEY_STORE = ObjectFactorySetting()
    #: The clouds that are available
    #: Should be a mapping of name => (label, url) dictionaries
    AVAILABLE_CLOUDS = Setting()
    #: The name of the current cloud
    CURRENT_CLOUD = Setting()


cloud_settings = JasminCloudSettings('JASMIN_CLOUD')
