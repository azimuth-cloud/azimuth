"""
This module contains the cluster engine implementation for azimuth-caas-crd.
"""
import re
import typing as t

import easykube

from azimuth.cluster_engine.drivers import base
from azimuth.cluster_engine import dto
from azimuth.cluster_engine import errors

CAAS_API_VERSION = "caas.azimuth.stackhpc.com/v1alpha1"


def _get_namespace(project_id):
    safe_project_id = re.sub("[^a-z0-9]+", "-", project_id).strip("-")
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


def get_cluster_types(client):
    raw_templates = list(client.api(CAAS_API_VERSION).resource("clustertypes").list())
    return raw_templates


def get_k8s_client(project_id):
    namespace = _get_namespace(project_id)
    ekconfig = easykube.Configuration.from_environment()
    client = ekconfig.sync_client(default_namespace=namespace)
    _ensure_namespace(client, namespace)
    return client


# TODO(johngarbutt) horrible testing hack!
if __name__ == "__main__":
    client = get_k8s_client("123")
    print(get_cluster_types(client))


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
        raise NotImplementedError

    def find_cluster_type(self, name: str, ctx: dto.Context) -> dto.ClusterType:
        """
        See :py:meth:`.base.Driver.find_cluster_type`.
        """
        self._log("Fetching job template '%s'", name, ctx=ctx)
        raise errors.ObjectNotFoundError(name)

    def clusters(self, ctx: dto.Context) -> t.Iterable[dto.Cluster]:
        """
        List the clusters that are deployed.
        """
        namespace = ctx.tenancy.id
        raise NotImplementedError

    def find_cluster(self, id: str, ctx: dto.Context) -> dto.Cluster:
        """
        Find a cluster by id.
        """
        raise NotImplementedError

    def create_cluster(
        self,
        name: str,
        cluster_type: dto.ClusterType,
        params: t.Mapping[str, t.Any],
        ssh_key: str,
        ctx: dto.Context,
    ):
        """
        Create a new cluster with the given name, type and parameters.
        """
        raise NotImplementedError

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
        raise NotImplementedError

    def close(self):
        """
        Release any resources held by this driver.
        """
        self._client.close()

    def __enter__(self):
        """
        Called when entering a context manager block.
        """
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """
        Called when exiting a context manager block. Ensures that close is called.
        """
        self._client.__exit__(exc_type, exc_value, traceback)

    def __del__(self):
        """
        Ensures that close is called when the session is garbage collected.
        """
        self.close()
