"""
Settings helpers for the ``azimuth`` Django app.
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
    #: The name of the template inventory
    TEMPLATE_INVENTORY = Setting(default = "openstack")
    #: Determines whether teams should be created on demand
    #: If set to false, then teams must be created manually in AWX, giving admins
    #: control of which tenancies have CaaS enabled and which do not
    CREATE_TEAMS = Setting(default = False)
    #: Determines whether newly created teams should have the allow all permission granted
    #: Only used if CREATE_TEAMS = True
    CREATE_TEAM_ALLOW_ALL_PERMISSION = Setting(default = False)

    ####
    # Admin settings
    ####
    #: The username to use for admin operations (e.g. creating resources)
    #: Defaults to the same as the CaaS username
    ADMIN_USERNAME = Setting(default = lambda settings: settings.USERNAME)
    #: The password to use for admin operations
    #: Defaults to the same as the CaaS password
    ADMIN_PASSWORD = Setting(default = lambda settings: settings.PASSWORD)
    #: A list of extra credentials to create which will be attached to projects
    EXTRA_CREDENTIALS = Setting(default = [])
    #: List of default projects to create
    DEFAULT_PROJECTS = Setting(default = [
        {
            "NAME": "Demo Appliances",
            "GIT_URL": "https://github.com/stackhpc/demo-appliances.git",
            "GIT_VERSION": "master",
            "METADATA_ROOT": "https://raw.githubusercontent.com/stackhpc/demo-appliances/master/ui-meta",
        }
    ])


class ProviderSetting(ObjectFactorySetting):
    """
    Custom setting for the provider that will inject a cluster engine if AWX
    is enabled.
    """
    def __get__(self, instance, owner):
        if not instance:
            raise TypeError("Settings cannot be accessed as class attributes")
        try:
            provider = instance.user_settings[self.name]
        except KeyError:
            provider = self._get_default(instance)
        # If AWX is enabled and no cluster engine is specified in the params
        # then inject one here
        if (
            isinstance(provider, dict) and
            "FACTORY" in provider and
            "CLUSTER_ENGINE" not in provider["PARAMS"] and
            instance.AWX.ENABLED
        ):
            provider["PARAMS"]["CLUSTER_ENGINE"] = dict(
                FACTORY = "azimuth.provider.cluster_engine.awx.Engine",
                PARAMS = dict(
                    URL = instance.AWX.URL,
                    USERNAME = instance.AWX.USERNAME,
                    PASSWORD = instance.AWX.PASSWORD,
                    CREATE_TEAMS = instance.AWX.CREATE_TEAMS,
                    CREATE_TEAM_ALLOW_ALL_PERMISSION = instance.AWX.CREATE_TEAM_ALLOW_ALL_PERMISSION,
                    VERIFY_SSL = instance.AWX.VERIFY_SSL,
                    TEMPLATE_INVENTORY = instance.AWX.TEMPLATE_INVENTORY
                )
            )
        # Process the given specification
        return self._process_item(provider, "{}.{}".format(instance.name, self.name))


class AppsSettings(SettingsObject):
    """
    Settings for apps.
    """
    #: Indicates if apps are enabled
    ENABLED = Setting(default = False)

    #: The base domain for the app proxy
    BASE_DOMAIN = Setting()
    #: Indicates whether SSL should be verified for apps
    #: This applies both to clients when associating keys with the registrar using the external
    #: endpoint and when determining whether a service is ready
    VERIFY_SSL = Setting(default = True)
    #: The address of the app proxy SSHD service
    #: Defaults to the base domain
    SSHD_HOST = Setting(default = lambda settings: settings.BASE_DOMAIN)
    #: The port for the app proxy SSHD service
    SSHD_PORT = Setting(default = 22)
    #: The external URL of the app proxy registrar, as needed by clients
    REGISTRAR_EXTERNAL_URL = Setting(
        default = lambda settings: f"https://registrar.{settings.BASE_DOMAIN}"
    )
    #: The admin URL of the app proxy registrar, for reserving subdomains
    REGISTRAR_ADMIN_URL = Setting()

    #: The URL of the script to use to execute post-deploy actions
    POST_DEPLOY_SCRIPT_URL = Setting(
        default = "https://raw.githubusercontent.com/stackhpc/ansible-collection-azimuth-tools/main/bin/run-playbook"
    )


def default_cluster_api_provider(settings):
    """
    Returns the default Cluster API provider.

    By default, the provider that matches the specified cloud provider is used.
    """
    if settings.PROVIDER.provider_name == "openstack":
        return {
            "FACTORY": "azimuth.cluster_api.openstack.Provider",
        }
    else:
        return None


class AzimuthSettings(SettingsObject):
    """
    Settings object for the ``AZIMUTH`` setting.
    """
    #: The name of the header containing the cloud token
    TOKEN_HEADER = Setting(default = "HTTP_X_CLOUD_TOKEN")

    #: The name of the header that may contain the tenancy id for a verification
    VERIFY_TENANCY_ID_HEADER = Setting(default = "HTTP_X_AUTH_TENANCY_ID")

    #: Cloud provider configuration
    PROVIDER = ProviderSetting()

    #: Cluster API configuration
    CLUSTER_API_PROVIDER = ObjectFactorySetting(default = default_cluster_api_provider)

    #: SSH key store configuration
    SSH_KEY_STORE = ObjectFactorySetting(
        # By default, use functionality from the provider to store SSH keys
        default = dict(
            FACTORY = "azimuth.keystore.provider.ProviderKeyStore",
        )
    )
    #: An iterable of allowed SSH key types
    SSH_ALLOWED_KEY_TYPES = Setting(default = {
        # By default, DSA keys are not permitted
        # "ssh-dss",
        # RSA keys are permitted, subject to SSH_RSA_MIN_BITS below
        "ssh-rsa",
        # All three sizes of ECDSA are permitted
        "ecdsa-sha2-nistp256",
        "ecdsa-sha2-nistp384",
        "ecdsa-sha2-nistp521",
        # ED25519 is permitted by default
        "ssh-ed25519",
    })
    #: The minimum size for RSA keys (by default, 1024 bit keys are not allowed)
    SSH_RSA_MIN_BITS = Setting(default = 2048)

    #: AWX configuration
    AWX = NestedSetting(AwxSettings)

    #: Configuration for apps
    APPS = NestedSetting(AppsSettings)

    #: The clouds that are available
    #: Should be a mapping of name => (label, url) dictionaries
    AVAILABLE_CLOUDS = Setting()
    #: The name of the current cloud
    CURRENT_CLOUD = Setting()


cloud_settings = AzimuthSettings("AZIMUTH")
