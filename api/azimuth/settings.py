"""
Settings helpers for the ``azimuth`` Django app.
"""

from settings_object import (
    SettingsObject,
    Setting,
    NestedSetting,
    ObjectFactorySetting
)

from .zenith import Zenith


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
    #: Settings for the AWX execution environment for the CaaS
    EXECUTION_ENVIRONMENT = Setting(default = None)
    #: A list of extra credentials to create which will be attached to projects
    EXTRA_CREDENTIALS = Setting(default = list)
    #: List of default projects to create
    DEFAULT_PROJECTS = Setting(default = list)


class ClusterEngineSetting(Setting):
    """
    Custom setting for the cluster engine that will provide Cluster-as-a-Service functionality.
    """
    def _get_default(self, instance):
        # The driver for the default cluster engine comes from the AWX setting
        if instance.AWX.ENABLED:
            from .cluster_engine.drivers import awx
            driver = awx.Driver(
                instance.AWX.URL,
                instance.AWX.USERNAME,
                instance.AWX.PASSWORD,
                instance.AWX.CREATE_TEAMS,
                instance.AWX.CREATE_TEAM_ALLOW_ALL_PERMISSION,
                instance.AWX.VERIFY_SSL,
                instance.AWX.TEMPLATE_INVENTORY
            )
            from .cluster_engine import Engine
            # Inject the Zenith instance into the engine if it is available
            return Engine(driver, instance.APPS)
        else:
            return None


class ClusterApiProviderSetting(ObjectFactorySetting):
    """
    Custom setting for the Cluster API provider that will provide Kubernetes functionality.
    """
    def _get_default(self, instance):
        # The default Cluster API provider matches the specified cloud provider
        if instance.PROVIDER.provider_name == "openstack":
            return {
                "FACTORY": "azimuth.cluster_api.openstack.Provider",
                "PARAMS": {
                    "NAMESPACE_TEMPLATE": instance.KUBERNETES_NAMESPACE_TEMPLATE,
                },
            }
        else:
            return None


class AppsSettings(SettingsObject):
    """
    Settings for the target Zenith app proxy.
    """
    #: Indicates if apps are enabled
    ENABLED = Setting(default = False)

    #: The base domain for the app proxy
    BASE_DOMAIN = Setting()
    #: The external URL of the app proxy registrar, as needed by clients
    REGISTRAR_EXTERNAL_URL = Setting(
        default = lambda settings: f"https://registrar.{settings.BASE_DOMAIN}"
    )
    #: The admin URL of the app proxy registrar, for reserving subdomains
    REGISTRAR_ADMIN_URL = Setting()
    #: The address of the app proxy SSHD service
    #: Defaults to the base domain
    SSHD_HOST = Setting(default = lambda settings: settings.BASE_DOMAIN)
    #: The port for the app proxy SSHD service
    SSHD_PORT = Setting(default = 22)
    #: Indicates whether SSL should be verified when determining whether a service is ready
    VERIFY_SSL = Setting(default = True)
    #: Indicates whether SSL should be verified by clients when associating keys with the
    #: registrar using the external endpoint
    VERIFY_SSL_CLIENTS = Setting(default = True)
    #: Query parameters that should be added to the Zenith URL before redirecting
    #: For example, this can be used to indicate to Keycloak that a specific IdP should be
    #: used by specifying kc_idp_hint
    QUERY_PARAMS = Setting(default = dict)


class ZenithSetting(Setting):
    """
    Setting that produces a Zenith object based on the given values.
    """
    def __init__(self):
        super().__init__(dict)

    def __get__(self, instance, owner):
        user_settings = super().__get__(instance, owner)
        apps_settings = AppsSettings(self.name, user_settings)
        if apps_settings.ENABLED:
            return Zenith(
                apps_settings.BASE_DOMAIN,
                apps_settings.REGISTRAR_EXTERNAL_URL,
                apps_settings.REGISTRAR_ADMIN_URL,
                apps_settings.SSHD_HOST,
                apps_settings.SSHD_PORT,
                apps_settings.VERIFY_SSL,
                apps_settings.VERIFY_SSL_CLIENTS,
                apps_settings.QUERY_PARAMS
            )
        else:
            return None


class MetricsSetting(SettingsObject):
    """
    Settings object for the metrics URLs.
    """
    #: The URL of the cloud metrics page
    CLOUD_METRICS_URL = Setting(default = None)
    #: The URL template for tenant metrics pages
    #: Will be interpolated with the tenancy ID
    TENANT_METRICS_URL_TEMPLATE = Setting(default = None)


class AzimuthSettings(SettingsObject):
    """
    Settings object for the ``AZIMUTH`` setting.
    """
    #: The name of the header containing the cloud token
    TOKEN_HEADER = Setting(default = "HTTP_X_CLOUD_TOKEN")

    #: The name of the header that may contain the tenancy id for a verification
    VERIFY_TENANCY_ID_HEADER = Setting(default = "HTTP_X_AUTH_TENANCY_ID")

    #: Cloud provider configuration
    PROVIDER = ObjectFactorySetting()

    #: Cluster engine configuration
    CLUSTER_ENGINE = ClusterEngineSetting()

    #: Cluster API configuration
    CLUSTER_API_PROVIDER = ClusterApiProviderSetting()

    #: The template to use when creating namespaces for tenancy resources
    KUBERNETES_NAMESPACE_TEMPLATE = Setting(default = "az-{tenancy_name}")
    #: The template to use when creating identity realms for tenancies
    IDENTITY_REALM_NAME_TEMPLATE = Setting(default = "az-{tenancy_name}")
    #: The template to use when creating identity platforms for CaaS clusters
    CLUSTER_PLATFORM_NAME_TEMPLATE = Setting(default = "caas-{cluster_name}")

    #: Configuration for curated sizes
    #: If given, should be a list of dictionaries
    #: Each item must contain an "id" key, corresponding to a flavor in the target cloud
    #: Each item can also optionally define "name" and "description" keys to replace the
    #: name reported by the cloud and the default description
    #: The description is treated as a Django template, and receives the variables "cpus",
    #: "ram", "disk" and "ephemeral_disk"
    CURATED_SIZES = Setting(default = None)

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

    #: Configuration for the Zenith instance for apps
    APPS = ZenithSetting()

    #: The clouds that are available
    #: Should be a mapping of name => (label, url) dictionaries
    AVAILABLE_CLOUDS = Setting()
    #: The name of the current cloud
    CURRENT_CLOUD = Setting()

    #: Configuration for cloud metrics dashboards
    METRICS = NestedSetting(MetricsSetting)

    #: URL for documentation
    DOCUMENTATION_URL = Setting(default = "https://stackhpc.github.io/azimuth-user-docs/")


cloud_settings = AzimuthSettings("AZIMUTH")
