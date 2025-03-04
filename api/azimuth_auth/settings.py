"""
Settings for the Azimuth auth package.
"""

import functools

from django.core.exceptions import ImproperlyConfigured

import httpx

from settings_object import (
    SettingsObject,
    Setting,
    MergedDictSetting,
    NestedSetting,
    ObjectFactorySetting,

)


class ChoiceSetting(Setting):
    """
    Setting that allows choosing from a fixed set of choices.
    """
    def __init__(self, choices, *args, **kwargs):
        self.choices = choices
        super().__init__(*args, **kwargs)

    def _transform(self, instance, value):
        if value in self.choices:
            return value
        else:
            choices = ",".join(str(choice) for choice in self.choices)
            raise ImproperlyConfigured(f"{instance.name}.{self.name} must be one of {choices}")


class OIDCDiscoverySetting(Setting):
    """
    Setting whose default value is populated by OIDC discovery.
    """
    def __init__(self, key):
        self.key = key

    def _get_default(self, instance):
        try:
            return instance.DISCOVERY_DATA[self.key]
        except KeyError:
            raise ImproperlyConfigured(f"{self.key} not present in OIDC discovery data")


class OIDCSettings(SettingsObject):
    """
    Settings for OIDC authentication.
    """
    #: The URL for the OIDC issuer
    ISSUER_URL = Setting()
    #: The authorization URL for the OIDC issuer
    #: If not given, OIDC discovery is used to discover it
    AUTHORIZATION_URL = OIDCDiscoverySetting("authorization_endpoint")
    #: The token URL for the OIDC issuer
    #: If not given, OIDC discovery is used to discover it
    TOKEN_URL = OIDCDiscoverySetting("token_endpoint")
    #: The userinfo URL for the OIDC issuer
    #: If not given, OIDC discovery is used to discover it
    USERINFO_URL = OIDCDiscoverySetting("userinfo_endpoint")

    #: The claim to extract the user's ID from
    USERID_CLAIM = Setting(default = "sub")
    #: The claim to extract the username from
    USERNAME_CLAIM = Setting(default = "preferred_username")
    #: The claim to extract the user's email address from
    EMAIL_CLAIM = Setting(default = "email")
    #: The claim to extract the user's groups from
    GROUPS_CLAIM = Setting(default = "groups")

    #: The OIDC client ID
    CLIENT_ID = Setting()
    #: The OIDC client secret
    CLIENT_SECRET = Setting()

    #: The scope to use for the OIDC request
    SCOPE = Setting(default = "openid profile email")

    #: The session key to use to store the OIDC state
    STATE_SESSION_KEY = Setting(default = "oidc_state")

    #: Indicates whether to verify SSL for the OIDC issuer
    VERIFY_SSL = Setting(default = True)

    @functools.cached_property
    def DISCOVERY_DATA(self):
        """
        The data from the discovery endpoint for the specified issuer.
        """
        discovery_url = self.ISSUER_URL.rstrip("/") + "/.well-known/openid-configuration"
        response = httpx.get(discovery_url, verify = self.VERIFY_SSL)
        response.raise_for_status()
        return response.json()


class OpenStackSettings(SettingsObject):
    """
    Settings for OpenStack authentication.
    """
    #: The auth URL for the target OpenStack
    AUTH_URL = Setting()
    #: The region to use
    REGION = Setting(default = None)
    #: The interface to use when interacting with OpenStack
    INTERFACE = Setting(default = "public")
    #: Indicates whether to verify SSL when talking to OpenStack
    VERIFY_SSL = Setting(default = True)

    #: Indicates if the appcred authenticator should be hidden
    APPCRED_HIDDEN = Setting(default = True)

    #: Indicates if password authentication is enabled
    PASSWORD_ENABLED = Setting(default = False)
    #: The domains to enable password authentication for
    PASSWORD_DOMAINS = Setting(default = list)

    #: Indicates if federated authentication is enabled
    FEDERATED_ENABLED = Setting(default = False)
    #: The federated identity providers
    FEDERATED_IDENTITY_PROVIDERS = Setting(default = list)


class AuthenticatorsSetting(ObjectFactorySetting):
    """
    Custom setting for providing the default authenticators based on other settings.
    """
    def _get_default(self, instance):
        authenticators = []
        if instance.AUTH_TYPE == "oidc":
            # Include the authcode authenticator
            authenticators.append(
                {
                    "NAME": "oidc",
                    "LABEL": "OpenID Connect",
                    "HIDDEN": False,
                    "AUTHENTICATOR": {
                        "FACTORY": "azimuth_auth.authenticator.oidc.AuthorizationCodeAuthenticator",
                        "PARAMS": {
                            "AUTHORIZATION_URL": instance.OIDC.AUTHORIZATION_URL,
                            "TOKEN_URL": instance.OIDC.TOKEN_URL,
                            "CLIENT_ID": instance.OIDC.CLIENT_ID,
                            "CLIENT_SECRET": instance.OIDC.CLIENT_SECRET,
                            "SCOPE": instance.OIDC.SCOPE,
                            "STATE_SESSION_KEY": instance.OIDC.STATE_SESSION_KEY,
                            "VERIFY_SSL": instance.OIDC.VERIFY_SSL,
                        },
                    },
                }
            )
        elif instance.AUTH_TYPE == "openstack":
            # Always include the appcred authenticator
            authenticators.append(
                {
                    "NAME": "appcred",
                    "LABEL": "Application Credential",
                    "HIDDEN": instance.OPENSTACK.APPCRED_HIDDEN,
                    "AUTHENTICATOR": {
                        "FACTORY": "azimuth_auth.authenticator.openstack.ApplicationCredentialAuthenticator",
                        "PARAMS": {
                            "AUTH_URL": instance.OPENSTACK.AUTH_URL,
                            "VERIFY_SSL": instance.OPENSTACK.VERIFY_SSL,
                        },
                    },
                }
            )
            if instance.OPENSTACK.FEDERATED_ENABLED:
                identity_providers = []
                for idp in instance.OPENSTACK.FEDERATED_IDENTITY_PROVIDERS:
                    protocol = idp["protocol"]
                    provider = idp.get("provider")
                    name = f"{provider}_{protocol}" if provider else protocol
                    label = idp.get("label") or name
                    identity_providers.append(
                        {
                            "protocol": protocol,
                            "provider": provider,
                            "name": name,
                            "label": label,
                        }
                    )
                authenticators.append(
                    {
                        "NAME": "federated",
                        "AUTHENTICATOR": {
                            "FACTORY": "azimuth_auth.authenticator.openstack.FederatedAuthenticator",
                            "PARAMS": {
                                "AUTH_URL": instance.OPENSTACK.AUTH_URL,
                                "IDENTITY_PROVIDERS": identity_providers,
                            },
                        },
                    }
                )
            if instance.OPENSTACK.PASSWORD_ENABLED:
                authenticators.append(
                    {
                        "NAME": "password",
                        "AUTHENTICATOR": {
                            "FACTORY": "azimuth_auth.authenticator.openstack.PasswordAuthenticator",
                            "PARAMS": {
                                "AUTH_URL": instance.OPENSTACK.AUTH_URL,
                                "DOMAINS": [
                                    {
                                        "name": domain["name"],
                                        "label": domain.get("label") or domain["name"],
                                    }
                                    for domain in instance.OPENSTACK.PASSWORD_DOMAINS
                                ],
                                "VERIFY_SSL": instance.OPENSTACK.VERIFY_SSL,
                            },
                        },
                    }
                )
        return authenticators


class SessionProviderSetting(ObjectFactorySetting):
    """
    Custom setting for configuring the session provider based on other settings.
    """
    def _get_default(self, instance):
        if instance.AUTH_TYPE == "oidc":
            return {
                "FACTORY": "azimuth_auth.session.oidc.Provider",
                "PARAMS": {
                    "TOKEN_URL": instance.OIDC.TOKEN_URL,
                    "USERINFO_URL": instance.OIDC.USERINFO_URL,
                    "USERID_CLAIM": instance.OIDC.USERID_CLAIM,
                    "USERNAME_CLAIM": instance.OIDC.USERNAME_CLAIM,
                    "EMAIL_CLAIM": instance.OIDC.EMAIL_CLAIM,
                    "GROUPS_CLAIM": instance.OIDC.GROUPS_CLAIM,
                    "CLIENT_ID": instance.OIDC.CLIENT_ID,
                    "CLIENT_SECRET": instance.OIDC.CLIENT_SECRET,
                    "SCOPE": instance.OIDC.SCOPE,
                    "VERIFY_SSL": instance.OIDC.VERIFY_SSL,
                },
            }
        elif instance.AUTH_TYPE == "openstack":
            return {
                "FACTORY": "azimuth_auth.session.openstack.Provider",
                "PARAMS": {
                    "AUTH_URL": instance.OPENSTACK.AUTH_URL,
                    "REGION": instance.OPENSTACK.REGION,
                    "INTERFACE": instance.OPENSTACK.INTERFACE,
                    "VERIFY_SSL": instance.OPENSTACK.VERIFY_SSL,
                },
            }
        else:
            raise ImproperlyConfigured("unrecognised auth type")


class AzimuthAuthSettings(SettingsObject):
    """
    Settings object for the ``AZIMUTH_AUTH`` setting.
    """
    #: The type of authentication to use
    AUTH_TYPE = ChoiceSetting(["oidc", "openstack"])
    #: Settings for OIDC authentication
    OIDC = NestedSetting(OIDCSettings)
    #: Settings for OpenStack authentication
    OPENSTACK = NestedSetting(OpenStackSettings)

    #: The authenticators to use
    AUTHENTICATORS = AuthenticatorsSetting()

    #: The session provider to use
    SESSION_PROVIDER = SessionProviderSetting()

    #: The HTTP parameter to pass the selected option to the start URL
    SELECTED_OPTION_PARAM = Setting(default = "option")
    #: The session key used to preserve the selected option across redirections
    SELECTED_OPTION_SESSION_KEY = Setting(default = "option")
    
    #: The name of the cookie to store the remembered authenticator
    #: This cookie does not have an expiry date, so the selection persists beyond the session
    AUTHENTICATOR_COOKIE_NAME = Setting(default = "azimuth-authenticator")

    #: For the bearer token middleware, this is the name of the header that the token will be in
    BEARER_TOKEN_HEADER = Setting(default = "HTTP_AUTHORIZATION")
    #: For the bearer token middleware, this is the prefix that will be present and needs to be stripped
    BEARER_TOKEN_PREFIX = Setting(default = "Bearer")

    #: For the session middleware, this is the name of the session key in which the token is stored
    TOKEN_SESSION_KEY = Setting(default = "token")

    #: The HTTP parameter to get the next URL from
    NEXT_URL_PARAM = Setting(default = "next")
    #: The name of the cookie to store the next URL in
    NEXT_URL_COOKIE_NAME = Setting(default = "azimuth-next-url")
    #: The allowed domains for the next URL
    NEXT_URL_ALLOWED_DOMAINS = Setting(default = set)
    #: The default next URL if the user-supplied URL is not given or not permitted
    NEXT_URL_DEFAULT_URL = Setting(default = "/tenancies")

    #: The HTTP parameter used to specify that the method should be changed
    CHANGE_METHOD_PARAM = Setting(default = "change_method")

    #: The HTTP parameter to get the message code from
    MESSAGE_CODE_PARAM = Setting(default = "code")
    #: The default message level
    DEFAULT_MESSAGE_LEVEL = Setting(default = "danger")
    #: The messages to use for each code
    #: Each item can be either a string or a dict with a string and a level
    MESSAGES = MergedDictSetting({
        "session_expired": "Your session has expired. Please sign in again.",
        "invalid_authentication_method": "Invalid authentication method.",
        "invalid_credentials": "The provided credentials are invalid. Please try again.",
        "external_auth_failed": "Authentication with external provider failed.",
        "logout_successful": { "message": "You have been signed out.", "level": "success" },
    })


auth_settings = AzimuthAuthSettings("AZIMUTH_AUTH")
