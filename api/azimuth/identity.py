import dataclasses

from easykube import ApiError, Configuration

from . import utils
from .cluster_engine import dto as cluster_dto
from .provider import dto

AZIMUTH_IDENTITY_API_VERSION = "identity.azimuth.stackhpc.com/v1alpha1"


# Configure the Kubernetes client from the environment
ekconfig = Configuration.from_environment()


@dataclasses.dataclass(frozen=True)
class Realm:
    """
    DTO representing an identity realm.
    """

    #: The realm name
    name: str
    #: The status of the realm
    status: str
    #: The issuer URL for the realm
    oidc_issuer_url: str | None
    #: The admin URL for the realm
    admin_url: str | None

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
            status.get("adminUrl"),
        )


def get_realm(tenancy: dto.Tenancy) -> Realm | None:
    """
    Returns the identity realm for the tenancy.
    """
    with ekconfig.sync_client() as client:
        tenancy_namespace = utils.get_namespace(client, tenancy)
        try:
            realm = (
                client.api(AZIMUTH_IDENTITY_API_VERSION)
                .resource("realms")
                .fetch(tenancy_namespace, namespace=tenancy_namespace)
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
    with ekconfig.sync_client(default_field_manager="azimuth") as client:
        tenancy_namespace = utils.get_namespace(client, tenancy)
        # Create the namespace if required
        utils.ensure_namespace(client, tenancy_namespace, tenancy)
        # We create a realm with the same name as the tenancy namespace
        # This means that we don't get a realm name of the format {namespace}-{name}
        # because in the case where the namespace and name are identical, the identity
        # operator reduces that to just {name}
        realm = client.apply_object(
            {
                "apiVersion": AZIMUTH_IDENTITY_API_VERSION,
                "kind": "Realm",
                "metadata": {
                    "name": tenancy_namespace,
                    "namespace": tenancy_namespace,
                    "labels": {
                        "app.kubernetes.io/managed-by": "azimuth",
                    },
                },
                "spec": {
                    "tenancyId": tenancy.id,
                },
            },
            force=True,
        )
    return Realm.from_k8s_object(realm)


def ensure_platform_for_cluster(
    tenancy: dto.Tenancy, realm: Realm, cluster: cluster_dto.Cluster
):
    """
    Ensures that an identity platform exists for the cluster.
    """
    with ekconfig.sync_client(default_field_manager="azimuth") as client:
        tenancy_namespace = utils.get_namespace(client, tenancy)
        client.apply_object(
            {
                "apiVersion": AZIMUTH_IDENTITY_API_VERSION,
                "kind": "Platform",
                "metadata": {
                    "name": f"caas-{utils.sanitise(cluster.name)}",
                    "namespace": tenancy_namespace,
                    "labels": {
                        "app.kubernetes.io/managed-by": "azimuth",
                    },
                    "ownerReferences": [
                        {
                            "apiVersion": "caas.azimuth.stackhpc.com/v1alpha1",
                            "kind": "Cluster",
                            "name": utils.sanitise(cluster.name),
                            "uid": cluster.id,
                            "blockOwnerDeletion": True,
                        },
                    ],
                },
                "spec": {
                    "realmName": realm.name,
                    "zenithServices": {
                        service.name: {
                            "subdomain": service.subdomain,
                            "fqdn": service.fqdn,
                        }
                        for service in cluster.services
                    },
                },
            },
            force=True,
        )
