"""
Shared test helpers.
"""

from contextlib import contextmanager

from azimuth.settings import cloud_settings


@contextmanager
def override_cloud_settings(**overrides):
    """
    Override top-level keys of the ``AZIMUTH`` setting as seen by
    ``azimuth.settings.cloud_settings``.
    """
    original_user_settings = cloud_settings.user_settings
    original_settings_cache = cloud_settings.settings_cache
    cloud_settings.user_settings = {**original_user_settings, **overrides}
    cloud_settings.settings_cache = {}
    try:
        yield
    finally:
        cloud_settings.user_settings = original_user_settings
        cloud_settings.settings_cache = original_settings_cache
