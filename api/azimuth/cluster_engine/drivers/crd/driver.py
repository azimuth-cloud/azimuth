"""
This module contains the cluster engine implementation for azimuth-caas-crd.
"""
import dateutil.parser
import re
import typing as t

import easykube

from azimuth.cluster_engine.drivers import base
from azimuth.cluster_engine import dto
from azimuth.cluster_engine import errors

CAAS_API_VERSION = "caas.azimuth.stackhpc.com/v1alpha1"


def _escape_name(name):
    return re.sub("[^a-z0-9]+", "-", name).strip("-")


def _get_namespace(project_id):
    safe_project_id = _escape_name(project_id)
    return f"caas-{safe_project_id}"


# TODO(johngarbutt): share with cluster API better?
def _ensure_namespace(client, namespace):
    try:
        client.api("v1").resource("namespaces").create(
            {"metadata": {"name": namespace}}
        )
    except easykube.ApiError as exc:
        # Swallow the conflict that occurs when the namespace already exists
        if exc.status_code != 409 or exc.reason.lower() != "alreadyexists":
            raise


def get_k8s_client(project_id):
    namespace = _get_namespace(project_id)
    ekconfig = easykube.Configuration.from_environment()
    client = ekconfig.sync_client(default_namespace=namespace)
    _ensure_namespace(client, namespace)
    return client


def get_cluster_types(client) -> t.Iterable[dto.ClusterType]:
    raw_types = list(client.api(CAAS_API_VERSION).resource("clustertypes").list())
    cluster_types = []
    for raw in raw_types:
        if not raw["status"] or raw["status"]["phase"] != "Available":
            continue
        cluster_types.append(
            dto.ClusterType.from_dict(raw.metadata.name, raw.status.uiMeta)
        )
    return cluster_types


def get_cluster_dto(raw_cluster):
    raw_status = raw_cluster.get("status", {})
    status = dto.ClusterStatus.CONFIGURING
    if raw_status and raw_status.get("phase") == "Ready":
        status = dto.ClusterStatus.READY
    if raw_status and raw_status.get("phase") == "Deleting":
        status = dto.ClusterStatus.DELETING
    return dto.Cluster(
        id=raw_cluster.metadata.uid,
        name=raw_cluster.metadata.name,
        cluster_type=raw_cluster.spec.clusterTypeName,
        status=status,
        task=None,
        error_message=None,
        parameter_values=dict(asdf="asdf"),
        tags=["asdf"],
        outputs=dict(),
        created=dateutil.parser.parse(raw_cluster.metadata.creationTimestamp),
        updated=dateutil.parser.parse(raw_cluster.metadata.creationTimestamp),
        patched=dateutil.parser.parse(raw_cluster.metadata.creationTimestamp),
        services=[],
    )


def get_clusters(client) -> t.Iterable[dto.Cluster]:
    raw_clusters = list(client.api(CAAS_API_VERSION).resource("clusters").list())
    clusters = []
    for raw_cluster in raw_clusters:
        cluster = get_cluster_dto(raw_cluster)
        clusters.append(cluster)
    return clusters


def create_cluster(client, name: str, cluster_type_name: str, params: dict):
    safe_name = _escape_name(name)
    secret_name = f"openstack-{safe_name}"
    secret_resource = client.api("v1").resource("secrets")
    # TODO(johngarbutt) how do we get these deleted?
    secret_resource.create_or_replace(
        secret_name,
        {"metadata": {"name": secret_name}, "stringData": {"clouds.yaml": "TODO!"}},
    )

    cluster_spec = {
        "clusterTypeName": cluster_type_name,
        "cloudCredentialsSecretName": secret_name,
    }
    if params:
        cluster_spec["extraVars"] = {}
        for key, value in params.items():
            cluster_spec["extraVars"][key] = str(value)
    cluster_resource = client.api(CAAS_API_VERSION).resource("clusters")
    cluster = cluster_resource.create(
        {
            "metadata": {
                "name": safe_name,
                "labels": {"app.kubernetes.io/managed-by": "azimuth"},
            },
            "spec": cluster_spec,
        }
    )
    return get_cluster_dto(cluster)


def delete_cluster(client, name: str):
    safe_name = _escape_name(name)
    cluster_resource = client.api(CAAS_API_VERSION).resource("clusters")
    cluster_resource.delete(safe_name)
    # TODO(johngarbutt): is this racing the operator?
    raw_cluster = cluster_resource.fetch(safe_name)
    return get_cluster_dto(raw_cluster)


# TODO(johngarbutt) horrible testing hack!
if __name__ == "__main__":
    fake_project_id = "123"
    client = get_k8s_client(fake_project_id)
    print(get_cluster_types(client))
    clusters = get_clusters(client)
    print(clusters)
    if not clusters:
        create_cluster(client, "jg-test", "quick-test", {})
    clusters = get_clusters(client)
    print(clusters)
    if clusters:
        delete_cluster(client, "jg-test")
    clusters = get_clusters(client)
    print(clusters)


class Driver(base.Driver):
    """
    Cluster engine driver implementation for AWX.

    Cluster types correspond to available job templates, and clusters correspond
    to inventories. A cluster is configured by launching a job using the job
    template for the cluster type and the cluster inventory.
    """

    def __init__(self):
        pass

    def cluster_types(self, ctx: dto.Context) -> t.Iterable[dto.ClusterType]:
        client = get_k8s_client(ctx.tenancy.id)
        return get_cluster_types(client)

    def find_cluster_type(self, name: str, ctx: dto.Context) -> dto.ClusterType:
        """
        See :py:meth:`.base.Driver.find_cluster_type`.
        """
        all_types = self.cluster_types(ctx)
        for ctype in all_types:
            if ctype.name == name:
                return ctype
        raise errors.ObjectNotFoundError(name)

    def clusters(self, ctx: dto.Context) -> t.Iterable[dto.Cluster]:
        """
        List the clusters that are deployed.
        """
        client = get_k8s_client(ctx.tenancy.id)
        return get_clusters(client)

    def find_cluster(self, id: str, ctx: dto.Context) -> dto.Cluster:
        """
        Find a cluster by id.
        """
        all_clusters = self.clusters(ctx)
        for cluster in all_clusters:
            if cluster.id == id:
                return cluster
        raise errors.ObjectNotFoundError(id)

    def create_cluster(
        self,
        name: str,
        cluster_type: dto.ClusterType,
        params: t.Mapping[str, t.Any],
        ssh_key: str,
        ctx: dto.Context,
    ) -> dto.Cluster:
        """
        Create a new cluster with the given name, type and parameters.
        """
        client = get_k8s_client(ctx.tenancy.id)
        # TODO(johngarbutt): pass in the ssh key, or add to params?
        return create_cluster(client, name, cluster_type.name, params)

    def update_cluster(
        self, cluster: dto.Cluster, params: t.Mapping[str, t.Any], ctx: dto.Context
    ) -> dto.Cluster:
        """
        Updates an existing cluster with the given parameters.
        """
        raise NotImplementedError

    def patch_cluster(self, cluster: dto.Cluster, ctx: dto.Context) -> dto.Cluster:
        """
        Patches the given existing cluster.
        """
        raise NotImplementedError

    def delete_cluster(
        self, cluster: dto.Cluster, ctx: dto.Context
    ) -> t.Optional[dto.Cluster]:
        """
        Deletes an existing cluster.
        """
        client = get_k8s_client(ctx.tenancy.id)
        return delete_cluster(client, cluster.name)
