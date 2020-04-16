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
    #: Cloud provider configuration
    PROVIDER = ObjectFactorySetting()
    #: SSH key store configuration
    SSH_KEY_STORE = ObjectFactorySetting()


cloud_settings = JasminCloudSettings('JASMIN_CLOUD')
