"""
This module contains the cluster engine implementation for azimuth-caas-crd.
"""
import datetime
import dateutil.parser
import logging
import time
import typing as t

import easykube

from azimuth.acls import allowed_by_acls
from azimuth.cluster_engine.drivers import base
from azimuth.cluster_engine import dto
from azimuth.cluster_engine import errors
from azimuth.scheduling import dto as scheduling_dto, k8s as scheduling_k8s
from azimuth import utils


CAAS_API_VERSION = "caas.azimuth.stackhpc.com/v1alpha1"
LOG = logging.getLogger(__name__)


def get_k8s_client(ctx: dto.Context, ensure_namespace: bool = False):
    ekconfig = easykube.Configuration.from_environment()
    client = ekconfig.sync_client()
    client.default_namespace = utils.get_namespace(client, ctx.tenancy)
    if ensure_namespace:
        utils.ensure_namespace(client, client.default_namespace, ctx.tenancy)
    return client


def _get_cluster_type_dto(raw):
    if raw.get("status") and raw.get("status", {}).get("phase") == "Available":
        return dto.ClusterType.from_dict(
            raw.metadata.name,
            raw.status.uiMeta,
            raw.metadata.resourceVersion,
        )


def get_cluster_types(client, tenancy) -> t.Iterable[dto.ClusterType]:
    raw_types = list(client.api(CAAS_API_VERSION).resource("clustertypes").list())
    cluster_types = []
    for raw in raw_types:
        if allowed_by_acls(raw, tenancy):
            cluster_type = _get_cluster_type_dto(raw)
            if cluster_type:
                cluster_types.append(cluster_type)
    return cluster_types


def get_cluster_dto(raw_cluster, status_if_ready: t.Optional[dto.ClusterStatus] = None):
    raw_status = raw_cluster.get("status", {})
    status = dto.ClusterStatus.CONFIGURING
    task = None
    outputs = dict()
    error_message = None
    created_at = dateutil.parser.parse(raw_cluster.metadata.creationTimestamp)
    updated_at = created_at
    patched_at = None

    if raw_status:
        phase = raw_status.get("phase")
        if phase == "Ready":
            status = dto.ClusterStatus.READY
            if status_if_ready:
                status = status_if_ready
        elif phase == "Deleting":
            status = dto.ClusterStatus.DELETING
            task = "Deleting platform"
        elif phase == "Failed":
            status = dto.ClusterStatus.ERROR
            error_message = "General Error"
        elif phase == "Creating":
            status = dto.ClusterStatus.CONFIGURING
            task = "Creating platform"
        elif phase == "Configuring":
            status = dto.ClusterStatus.CONFIGURING
            task = "Re-configuring platform"

        if "outputs" in raw_status:
            outputs = raw_status["outputs"]

        if raw_status.get("error"):
            error_message = raw_status["error"]

        if raw_status.get("updatedTimestamp"):
            updated_at = dateutil.parser.parse(raw_status["updatedTimestamp"])

        if raw_status.get("patchedTimestamp"):
            patched_at = dateutil.parser.parse(raw_status["patchedTimestamp"])

    # If there is a schedule in the annotations, unserialize it
    annotations = raw_cluster["metadata"].get("annotations", {})
    schedule_json = annotations.get("azimuth.stackhpc.com/schedule")
    schedule = (
        scheduling_dto.PlatformSchedule.from_json(schedule_json)
        if schedule_json
        else None
    )

    return dto.Cluster(
        id=raw_cluster.metadata.uid,
        name=raw_cluster.metadata.name,
        cluster_type=raw_cluster.spec.clusterTypeName,
        cluster_type_version=raw_cluster.spec.clusterTypeVersion,
        status=status,
        task=task,
        error_message=error_message,
        parameter_values=raw_cluster.spec.extraVars,
        tags=[],
        outputs=outputs,
        created=created_at,
        updated=updated_at,
        patched=patched_at,
        services=[],
        created_by_username=raw_cluster.spec.get("createdByUsername"),
        created_by_user_id=raw_cluster.spec.get("createdByUserId"),
        updated_by_username=raw_cluster.spec.get("updatedByUsername"),
        updated_by_user_id=raw_cluster.spec.get("updatedByUserId"),
        schedule=schedule,
    )


def get_clusters(client) -> t.Iterable[dto.Cluster]:
    raw_clusters = list(client.api(CAAS_API_VERSION).resource("clusters").list())
    clusters = []
    for raw_cluster in raw_clusters:
        cluster = get_cluster_dto(raw_cluster)
        clusters.append(cluster)
    return clusters


def _get_cluster_type(client, cluster_type_name: str, tenancy):
    clustertypes_resource = client.api(CAAS_API_VERSION).resource("clustertypes")
    raw = clustertypes_resource.fetch(cluster_type_name)
    if not allowed_by_acls(raw, tenancy):
        raise errors.ObjectNotFoundError(f"Cannot find cluster type {cluster_type_name}")
    cluster_type = _get_cluster_type_dto(raw)
    if cluster_type:
        return cluster_type
    else:
        raise Exception(f"Unable to find cluster type {cluster_type_name}")


def create_cluster(
    client,
    name: str,
    cluster_type_name: str,
    params: dict,
    schedule: t.Optional[scheduling_dto.PlatformSchedule],
    ctx: dto.Context
):
    safe_name = utils.sanitise(name)
    secret_name = f"{safe_name}-caas-credential"
    secret_resource = client.api("v1").resource("secrets")
    string_data = ctx.credential.data
    secret_resource.create_or_replace(
        secret_name,
        {
            "metadata": {
                "name": secret_name,
            },
            "stringData": string_data,
        }
    )

    cluster_type = _get_cluster_type(client, cluster_type_name, ctx.tenancy)
    cluster_spec = {
        "clusterTypeName": cluster_type_name,
        "clusterTypeVersion": cluster_type.version,
        "cloudCredentialsSecretName": secret_name,
        "createdByUsername": ctx.username,
        "createdByUserId": ctx.user_id,
    }
    if params:
        cluster_spec["extraVars"] = {}
        for key, value in params.items():
            cluster_spec["extraVars"][key] = value
    cluster_resource = client.api(CAAS_API_VERSION).resource("clusters")
    cluster = cluster_resource.create(
        {
            "metadata": {
                "name": safe_name,
                "labels": {"app.kubernetes.io/managed-by": "azimuth"},
                # We annotate the cluster with the serialized schedule object
                # This is to avoid doing an N+1 query
                "annotations": (
                    { "azimuth.stackhpc.com/schedule": schedule.to_json() }
                    if schedule
                    else {}
                ),
            },
            "spec": cluster_spec,
        }
    )
    if schedule:
        scheduling_k8s.create_schedule(
            client,
            f"caas-{safe_name}",
            cluster,
            schedule
        )
        # TODO (johngarbutt): create lease here
    return get_cluster_dto(cluster)


def delete_cluster(client, name: str):
    safe_name = utils.sanitise(name)

    # TODO(johngarbutt) should we be refreshing the application cred here?
    cluster_resource = client.api(CAAS_API_VERSION).resource("clusters")
    cluster_resource.delete(safe_name)

    # NOTE(johngarbutt) we are racing the operator here,
    # returning the ready state will confuse people
    time.sleep(0.1)
    # NOTE(sd109) Avoid checking allowed_by_acls here so that deletion is never blocked
    raw_cluster = cluster_resource.fetch(safe_name)
    return get_cluster_dto(raw_cluster, status_if_ready=dto.ClusterStatus.DELETING)


def patch_cluster(client, name: str, params: t.Mapping[str, t.Any], ctx: dto.Context):
    safe_name = utils.sanitise(name)

    # get current version for requested cluster type
    cluster_resource = client.api(CAAS_API_VERSION).resource("clusters")
    inital_raw_cluster = cluster_resource.fetch(safe_name)

    cluster_type_name = inital_raw_cluster["spec"]["clusterTypeName"]
    cluster_type = _get_cluster_type(client, cluster_type_name, ctx.tenancy)
    if not cluster_type:
        raise Exception(f"Cannot update as type {cluster_type_name} not found")

    # Trigger an update, even if no change in version requested
    # TODO(johngarbutt): cluster_upgrade_system_packages=true needed?
    return update_cluster(client, name, params, cluster_type.version, ctx)


def update_cluster(client, name: str, params: t.Mapping[str, t.Any],
                   version: str, ctx: dto.Context):
    safe_name = utils.sanitise(name)

    # trigger updates even when params are same as create or last update
    now = datetime.datetime.now(tz = datetime.timezone.utc)
    now_string = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    params["azimuth_requested_update_at"] = now_string

    # NOTE(johngarbutt): we assume no parameters are being removed here
    spec = dict(
        extraVars=params,
        updatedByUsername=ctx.username,
        updatedByUserId=ctx.user_id,
    )
    if version:
        spec["clusterTypeVersion"] = version

    # TODO(johngarbutt) should we be refreshing the application creds first?
    cluster_resource = client.api(CAAS_API_VERSION).resource("clusters")
    cluster_resource.patch(safe_name, dict(spec=spec))

    # NOTE(johngarbutt) we are racing the operator here,
    # returning the ready state will confuse people
    time.sleep(0.1)
    raw_cluster = cluster_resource.fetch(safe_name)
    if not allowed_by_acls(raw_cluster, ctx.tenancy):
        raise errors.ObjectNotFoundError(f"Cannot update cluster {name} - cluster type not found")

    return get_cluster_dto(raw_cluster, status_if_ready=dto.ClusterStatus.CONFIGURING)


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
        client = get_k8s_client(ctx)
        return get_cluster_types(client, ctx.tenancy)

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
        client = get_k8s_client(ctx)
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
        schedule: t.Optional[scheduling_dto.PlatformSchedule],
        ctx: dto.Context
    ) -> dto.Cluster:
        """
        Create a new cluster with the given name, type and parameters.
        """
        client = get_k8s_client(ctx, True)
        return create_cluster(client, name, cluster_type.name, params, schedule, ctx)

    def update_cluster(
        self,
        cluster: dto.Cluster,
        params: t.Mapping[str, t.Any],
        ctx: dto.Context
    ) -> dto.Cluster:
        """
        Updates an existing cluster with the given parameters.
        """
        client = get_k8s_client(ctx, True)
        return update_cluster(client, cluster.name, params,
                              version=None, ctx=ctx)

    def patch_cluster(
        self,
        cluster: dto.Cluster,
        params: t.Mapping[str, t.Any],
        ctx: dto.Context
    ) -> dto.Cluster:
        """
        Patches the given existing cluster.
        """
        client = get_k8s_client(ctx, True)
        return patch_cluster(client, cluster.name, params, ctx)

    def delete_cluster(
        self,
        cluster: dto.Cluster,
        ctx: dto.Context
    ) -> t.Optional[dto.Cluster]:
        """
        Deletes an existing cluster.
        """
        client = get_k8s_client(ctx, True)
        return delete_cluster(client, cluster.name)
