"""
Settings helpers for the ``jasmin_cloud`` Django app.
"""

from settings_object import (
    SettingsObject,
    Setting,
    NestedSetting,
    ObjectFactorySetting
)


class AwxSettings(SettingsObject):
    """
    Settings object for the AWX settings.
    """
    ####
    # General settings
    ####
    #: Indicates if AWX is enabled
    ENABLED = Setting(default = False)
    #: The AWX URL
    URL = Setting()
    #: Indicates whether to verify SSL when connecting over HTTPS
    VERIFY_SSL = Setting(default = True)

    ####
    # CaaS settings
    ####
    #: The username to use for CaaS operations
    USERNAME = Setting()
    #: The password to use for CaaS operations
    PASSWORD = Setting()
    #: The name of the credential type to use
    #: This should correspond to the selected provider
    #: If CREATE_RESOURCES = True, credential types will be created that can be used
    CREDENTIAL_TYPE = Setting(default = 'OpenStack Token')
    #: The name of the template inventory
    TEMPLATE_INVENTORY = Setting(default = 'openstack')
    #: Indicates whether teams should be created on demand
    #: If set to false, then teams must be created manually in AWX, giving admins
    #: control of which tenancies have CaaS enabled and which do not
    CREATE_TEAMS = Setting(default = False)

    ####
    # Admin settings
    ####
    #: The username to use for admin operations (e.g. creating resources)
    #: Defaults to the same as the CaaS username
    ADMIN_USERNAME = Setting(default = lambda settings: settings.USERNAME)
    #: The password to use for admin operations
    #: Defaults to the same as the CaaS password
    ADMIN_PASSWORD = Setting(default = lambda settings: settings.PASSWORD)
    #: The image to use for the CaaS execution environment
    EXECUTION_ENVIRONMENT_IMAGE = Setting(default = 'quay.io/ansible/awx-ee:0.2.0')


class ProviderSetting(ObjectFactorySetting):
    """
    Custom setting for the provider that will inject a cluster engine if AWX
    is enabled.
    """
    def __get__(self, instance, owner):
        if not instance:
            raise TypeError('Settings cannot be accessed as class attributes')
        try:
            provider = instance.user_settings[self.name]
        except KeyError:
            provider = self._get_default(instance)
        # If AWX is enabled and no cluster engine is specified in the params
        # then inject one here
        if (
            isinstance(provider, dict) and
            'FACTORY' in provider and
            'CLUSTER_ENGINE' not in provider['PARAMS'] and
            instance.AWX.ENABLED
        ):
            provider['PARAMS']['CLUSTER_ENGINE'] = dict(
                FACTORY = 'jasmin_cloud.provider.cluster_engine.awx.Engine',
                PARAMS = dict(
                    URL = instance.AWX.URL,
                    USERNAME = instance.AWX.USERNAME,
                    PASSWORD = instance.AWX.PASSWORD,
                    CREDENTIAL_TYPE = instance.AWX.CREDENTIAL_TYPE,
                    CREATE_TEAMS = instance.AWX.CREATE_TEAMS,
                    VERIFY_SSL = instance.AWX.VERIFY_SSL,
                    TEMPLATE_INVENTORY = instance.AWX.TEMPLATE_INVENTORY
                )
            )

        # Process the given specification
        return self._process_item(provider, '{}.{}'.format(instance.name, self.name))


class JasminCloudSettings(SettingsObject):
    """
    Settings object for the ``JASMIN_CLOUD`` setting.
    """
    #: The name of the header containing the cloud token
    TOKEN_HEADER = Setting(default = 'HTTP_X_CLOUD_TOKEN')
    #: Cloud provider configuration
    PROVIDER = ProviderSetting()
    #: SSH key store configuration
    SSH_KEY_STORE = ObjectFactorySetting()
    #: AWX configuration
    AWX = NestedSetting(AwxSettings)
    #: The clouds that are available
    #: Should be a mapping of name => (label, url) dictionaries
    AVAILABLE_CLOUDS = Setting()
    #: The name of the current cloud
    CURRENT_CLOUD = Setting()


cloud_settings = JasminCloudSettings('JASMIN_CLOUD')
