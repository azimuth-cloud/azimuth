from easykube import Configuration, ApiError, SyncClient

from .provider import dto
from .settings import cloud_settings


AZIMUTH_IDENTITY_API_VERSION = "identity.azimuth.stackhpc.com/v1alpha1"


# Configure the Kubernetes client from the environment
ekconfig = Configuration.from_environment()


def ensure_realm(tenancy: dto.Tenancy):
    """
    Ensures that an identity realm exists for the given tenancy.
    """
    realm_name = cloud_settings.IDENTITY_REALM_NAME_TEMPLATE.format(
        tenancy_id = tenancy.id,
        tenancy_name = tenancy.name
    )
    namespace = cloud_settings.KUBERNETES_NAMESPACE_TEMPLATE.format(
        tenancy_id = tenancy.id,
        tenancy_name = tenancy.name
    )
    with ekconfig.sync_client() as client:
        # Create the namespace if required
        try:
            client.api("v1").resource("namespaces").create({
                "metadata": {
                    "name": namespace,
                },
            })
        except ApiError as exc:
            # Swallow the conflict that occurs when the namespace already exists
            if exc.status_code != 409 or exc.reason.lower() != "alreadyexists":
                raise
        # Then create the realm
        _ = client.api(AZIMUTH_IDENTITY_API_VERSION).resource("realms").create_or_patch(
            realm_name,
            {
                "metadata": {
                    "name": realm_name,
                    "labels": {
                        "app.kubernetes.io/managed-by": "azimuth",
                    },
                },
                "spec": {
                    "tenancyId": tenancy.id,
                },
            },
            namespace = namespace
        )
    return realm_name
