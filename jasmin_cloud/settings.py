"""
Settings helpers for the ``jasmin_cloud`` Django app.
"""

from django.conf import settings

from jasmin_django_utils.appsettings import SettingsObject, ObjectFactorySetting


class JasminCloudSettings(SettingsObject):
    """
    Settings object for the ``JASMIN_CLOUD`` setting.
    """
    PROVIDER = ObjectFactorySetting()
    SSH_KEY_STORE = ObjectFactorySetting()


cloud_settings = JasminCloudSettings('JASMIN_CLOUD', getattr(settings, 'JASMIN_CLOUD', {}))
