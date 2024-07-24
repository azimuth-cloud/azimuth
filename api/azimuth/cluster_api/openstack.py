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
        # Create a new credential for the user
        credential = super()._create_credential(cluster_name)
        clouds = yaml.safe_load(credential["clouds.yaml"])
        user_info = yaml.safe_load(credential["user_info.yaml"])
        # Gophercloud weirdly requires the project ID to be present in the app cred
        # All other OpenStack clients bork at this :shrugs:
        clouds["clouds"]["openstack"]["auth"]["project_id"] = user_info["project_id"]
        return { **credential, "clouds.yaml": yaml.safe_dump(clouds) }

    def _ensure_shared_resources(self):
        # Just make sure that the shared tenant network exists
        # This allows templates to target it via a tag filter if they want
        self._cloud_session._tenant_network(True)
        # For consistency, ensure the project share is created
        self._cloud_session._project_share(True)
