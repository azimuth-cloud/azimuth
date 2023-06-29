import dataclasses
import re
import typing as t

from easykube import Configuration, ApiError

from .cluster_engine import dto as cluster_dto
from .provider import dto


AZIMUTH_IDENTITY_API_VERSION = "identity.azimuth.stackhpc.com/v1alpha1"


# Configure the Kubernetes client from the environment
ekconfig = Configuration.from_environment()


def sanitize(value):
    """
    Returns a sanitized form of the given value suitable for Kubernetes resource names.
    """
    return re.sub("[^a-z0-9]+", "-", str(value).lower()).strip("-")


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
    sanitized_tenancy_name = sanitize(tenancy.name)
    with ekconfig.sync_client() as client:
        try:
            realm = client.api(AZIMUTH_IDENTITY_API_VERSION).resource("realms").fetch(
                f"az-{sanitized_tenancy_name}",
                namespace = f"az-{sanitized_tenancy_name}"
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
    sanitized_tenancy_name = sanitize(tenancy.name)
    namespace = f"az-{sanitized_tenancy_name}"
    with ekconfig.sync_client(default_field_manager = "azimuth") as client:
        # Create the namespace if required
        try:
            client.api("v1").resource("namespaces").create({
                "metadata": {
                    "name": namespace,
                    "labels": {
                        "app.kubernetes.io/managed-by": "azimuth",
                    },
                },
            })
        except ApiError as exc:
            # Swallow the conflict that occurs when the namespace already exists
            if exc.status_code != 409 or exc.reason.lower() != "alreadyexists":
                raise
        # Then create the realm
        realm = client.apply_object(
            {
                "apiVersion": AZIMUTH_IDENTITY_API_VERSION,
                "kind": "Realm",
                "metadata": {
                    "name": f"az-{sanitized_tenancy_name}",
                    "namespace": namespace,
                    "labels": {
                        "app.kubernetes.io/managed-by": "azimuth",
                    },
                },
                "spec": {
                    "tenancyId": tenancy.id,
                },
            },
            force = True
        )
    return Realm.from_k8s_object(realm)


def ensure_platform_for_cluster(
    tenancy: dto.Tenancy,
    realm: Realm,
    cluster: cluster_dto.Cluster
):
    """
    Ensures that an identity platform exists for the cluster.
    """
    sanitized_name = sanitize(cluster.name)
    sanitized_tenancy_name = sanitize(tenancy.name)
    with ekconfig.sync_client(default_field_manager = "azimuth") as client:
        client.apply_object(
            {
                "apiVersion": AZIMUTH_IDENTITY_API_VERSION,
                "kind": "Platform",
                "metadata": {
                    "name": f"caas-{sanitized_name}",
                    "namespace": f"az-{sanitized_tenancy_name}",
                    "labels": {
                        "app.kubernetes.io/managed-by": "azimuth",
                    },
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
            force = True
        )


def remove_platform_for_cluster(tenancy: dto.Tenancy, cluster: cluster_dto.Cluster):
    """
    Removes the identity platform for the cluster.
    """
    sanitized_name = sanitize(cluster.name)
    sanitized_tenancy_name = sanitize(tenancy.name)
    with ekconfig.sync_client(default_field_manager = "azimuth") as client:
        client.api(AZIMUTH_IDENTITY_API_VERSION).resource("platforms").delete(
            f"caas-{sanitized_name}",
            namespace = f"az-{sanitized_tenancy_name}"
        )
