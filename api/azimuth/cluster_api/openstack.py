import yaml

from .base import Provider as ProviderBase, Session as SessionBase


class Provider(ProviderBase):
    """
    Cluster API provider for OpenStack.
    """
    provider_name = "openstack"


class Session(SessionBase):
    """
    Cluster API session for OpenStack.
    """
    provider_name = "openstack"

    def _create_credential(self, cluster_name):
        # Use the OpenStack connection to create a new app cred for the cluster
        # If an app cred already exists with the same name, delete it
        user = self._cloud_session._connection.identity.current_user
        app_cred_name = f"azimuth-{cluster_name}"
        existing = user.application_credentials.find_by_name(app_cred_name)
        if existing:
            existing._delete()
        app_cred = user.application_credentials.create(
            name = app_cred_name,
            description = f"Used by Azimuth to manage Kubernetes cluster '{cluster_name}'.",
        )
        # Make a clouds.yaml for the app cred and return it in stringData
        return {
            "stringData": {
                "clouds.yaml": yaml.safe_dump({
                    "clouds": {
                        "openstack": {
                            "identity_api_version": 3,
                            "interface": "public",
                            "auth_type": "v3applicationcredential",
                            "auth": {
                                "auth_url": self._cloud_session._connection.endpoints["identity"],
                                "application_credential_id": app_cred.id,
                                "application_credential_secret": app_cred.secret,
                                "project_id": app_cred.project_id,
                            },
                            # Disable SSL verification for now
                            "verify": False,
                        },
                    },
                })
            }
        }

    def _modify_cluster_spec(self, cluster_spec, is_create):
        # On create only, inject the network IDs for the external and internal networks
        if is_create:
            cluster_spec.update({
                "externalNetworkId": self._cloud_session._external_network().id,
                "networkId": self._cloud_session._tenant_network(True).id,
            })
        return cluster_spec
