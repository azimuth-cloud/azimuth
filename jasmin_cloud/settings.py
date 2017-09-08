"""
Settings helpers for the ``jasmin_cloud`` Django app.
"""

from django.conf import settings
from django.utils.module_loading import import_string
from django.core.exceptions import ImproperlyConfigured


def resolve_object_factory(factory_definition):
    """
    Helper function to resolve object factory definitions to objects.
    """
    factory = import_string(factory_definition['FACTORY'])
    kwargs = { k.lower(): v for k, v in factory_definition['PARAMS'].items() }
    return factory(**kwargs)


class BaseSettings:
    """
    Base class for settings objects.
    """
    #: Dictionary of default values for settings with static defaults.
    DEFAULTS = {}
    #: Tuple or list of settings that contain dotted strings that should be imported.
    IMPORT_STRINGS = ()
    #: Tuple or list of settings that contain definitions of the form::
    #:
    #:     {
    #:         'FACTORY': 'dotted.path.to.factory.function',
    #:         'PARAMS': {
    #:             'PARAM1': 'value for param 1',
    #:         },
    #:     }
    #:
    #: Keys in ``PARAMS`` are lower-cased and used as ``kwargs`` for the factory.
    OBJECT_FACTORIES = ()

    def __init__(self, name, user_settings = {}):
        self.name = name
        self.user_settings = user_settings

    def __getattr__(self, attr):
        if attr in self.user_settings:
            # First, try user settings
            val = self.user_settings[attr]
        elif attr in self.DEFAULTS:
            # Then try the defaults dict (for simple defaults)
            val = self.DEFAULTS[attr]
        elif hasattr(self, '_default_' + attr.lower()):
            # Then see if there is a method to generate the default
            val = getattr(self, '_default_' + attr.lower())()
        else:
            # If no default is available, the setting is required in user_settings
            raise ImproperlyConfigured("Required setting: {}.{}".format(self.name, attr))

        # If the setting is an import string, perform the import
        if attr in self.IMPORT_STRINGS:
            val = import_string(val)

        # If the settings is an object factory, resolve it
        if attr in self.OBJECT_FACTORIES:
            val = resolve_object_factory(val)

        # Check if the setting has a valid function defined
        # Validate functions should raise if the setting has an error
        if hasattr(self, '_validate_' + attr.lower()):
            getattr(self, '_validate_' + attr.lower())(val)

        # Before returning, cache the value for future use
        setattr(self, attr, val)
        return val


class JasminCloudSettings(BaseSettings):
    """
    Settings object for the ``JASMIN_CLOUD`` setting.
    """
    OBJECT_FACTORIES = ('PROVIDER',)


cloud_settings = JasminCloudSettings('JASMIN_CLOUD', getattr(settings, 'JASMIN_CLOUD', {}))
