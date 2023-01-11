import dataclasses
import typing as t

from easykube import Configuration, ApiError, SyncClient

from .provider import dto
from .settings import cloud_settings


AZIMUTH_IDENTITY_API_VERSION = "identity.azimuth.stackhpc.com/v1alpha1"


# Configure the Kubernetes client from the environment
ekconfig = Configuration.from_environment()


@dataclasses.dataclass(frozen = True)
class Realm:
    """
    DTO representing an identity realm.
    """
    #: The realm name
    name: str
    #: The status of the realm
    status: str
    #: The issuer URL for the realm
    oidc_issuer_url: t.Optional[str]
    #: The admin URL for the realm
    admin_url: t.Optional[str]

    @classmethod
    def from_k8s_object(cls, obj):
        """
        Creates a realm from the given Kubernetes realm.
        """
        status = obj.get("status", {})
        return cls(
            obj["metadata"]["name"],
            status.get("phase", "Unknown"),
            status.get("oidcIssuerUrl"),
            status.get("adminUrl")
        )


def get_realm(tenancy: dto.Tenancy) -> t.Optional[Realm]:
    """
    Returns the identity realm for the tenancy.
    """
    with ekconfig.sync_client() as client:
        try:
            realm = client.api(AZIMUTH_IDENTITY_API_VERSION).resource("realms").fetch(
                cloud_settings.IDENTITY_REALM_NAME_TEMPLATE.format(
                    tenancy_id = tenancy.id,
                    tenancy_name = tenancy.name
                ),
                namespace = cloud_settings.KUBERNETES_NAMESPACE_TEMPLATE.format(
                    tenancy_id = tenancy.id,
                    tenancy_name = tenancy.name
                )
            )
        except ApiError as exc:
            if exc.status_code == 404:
                return None
            else:
                raise
        else:
            return Realm.from_k8s_object(realm)


def ensure_realm(tenancy: dto.Tenancy) -> Realm:
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
        realm = client.api(AZIMUTH_IDENTITY_API_VERSION).resource("realms").create_or_patch(
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
    return Realm.from_k8s_object(realm)
