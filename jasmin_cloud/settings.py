"""
Settings helpers for the ``jasmin_cloud`` Django app.
"""

from django.conf import settings

from settings_object import SettingsObject, Setting, ObjectFactorySetting


class JasminCloudSettings(SettingsObject):
    """
    Settings object for the ``JASMIN_CLOUD`` setting.
    """
    #: The name of the header containing the cloud token
    TOKEN_HEADER = Setting(default = 'HTTP_X_CLOUD_TOKEN')
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
