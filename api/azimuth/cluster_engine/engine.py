"""
This module defines the base class for cluster managers.
"""

import typing as t

from ..provider import base as cloud_base

from . import dto, errors
from .drivers import base as drivers_base


class Engine:
    """
    Class for the cluster engine.
    """
    def __init__(self, driver: drivers_base.Driver):
        self._driver = driver

    def create_manager(self, cloud_session: cloud_base.ScopedSession) -> 'ClusterManager':
        """
        Creates a cluster manager for the given tenancy-scoped cloud session.
        """
        return ClusterManager(self._driver, cloud_session)


class ClusterManager:
    """
    Class for a tenancy-scoped cluster manager.
    """
    def __init__(self, driver: drivers_base.Driver, cloud_session: cloud_base.ScopedSession):
        self._driver = driver
        self._cloud_session = cloud_session
        self._ctx = dto.Context(
            cloud_session.username(),
            cloud_session.tenancy(),
            cloud_session.cluster_credential()
        )

    def cluster_types(self) -> t.Iterable[dto.ClusterType]:
        """
        Lists the available cluster types.
        """
        return self._driver.cluster_types(self._ctx)

    def find_cluster_type(self, name: str) -> dto.ClusterType:
        """
        Find a cluster type by name.
        """
        return self._driver.find_cluster_type(name, self._ctx)

    def clusters(self) -> t.Iterable[dto.Cluster]:
        """
        List the clusters that are deployed.
        """
        for cluster in self._driver.clusters(self._ctx):
            yield self._cloud_session.cluster_modify(cluster)

    def find_cluster(self, id: str) -> dto.Cluster:
        """
        Find a cluster by id.
        """
        cluster = self._driver.find_cluster(id, self._ctx)
        return self._cloud_session.cluster_modify(cluster)

    def validate_cluster_params(
        self,
        cluster_type: t.Union[dto.ClusterType, str],
        params: t.Mapping[str, t.Any],
        prev_params: t.Mapping[str, t.Any] = {}
    ) -> t.Mapping[str, t.Any]:
        """
        Validates the given user parameter values against the given cluster type.

        If validation fails, a `ValidationError` is raised.
        """
        from . import validation
        if not isinstance(cluster_type, dto.ClusterType):
            cluster_type = self.find_cluster_type(cluster_type)
        validator = validation.build_validator(
            self._cloud_session,
            self,
            cluster_type.parameters,
            prev_params
        )
        return validator(params)

    def create_cluster(
        self,
        name: str,
        cluster_type: dto.ClusterType,
        params: t.Mapping[str, t.Any],
        ssh_key: str
    ) -> dto.Cluster:
        """
        Creates a new cluster with the given name, type and parameters.
        """
        # If the parameters have not already been validated, validated them
        if not getattr(params, "__validated__", False):
            params = self.validate_cluster_params(cluster_type, params)
        params.update(self._cloud_session.cluster_parameters())
        cluster = self._driver.create_cluster(
            name,
            cluster_type,
            params,
            ssh_key,
            self._ctx
        )
        return self._cloud_session.cluster_modify(cluster)

    def update_cluster(
        self,
        cluster: t.Union[dto.Cluster, str],
        params: t.Mapping[str, t.Any]
    ) -> dto.Cluster:
        """
        Updates an existing cluster with the given parameters.
        """
        if not isinstance(cluster, dto.Cluster):
            cluster = self.find_cluster(cluster)
        if cluster.status in {dto.ClusterStatus.CONFIGURING, dto.ClusterStatus.DELETING}:
            raise errors.InvalidOperationError(
                'Cannot update cluster with status {}'.format(cluster.status.name)
            )
        # If the parameters have not already been validated, validated them
        if not getattr(params, "__validated__", False):
            params = self.validate_cluster_params(
                cluster.cluster_type,
                params,
                cluster.parameter_values
            )
        cluster = self._driver.update_cluster(cluster, params, self._ctx)
        return self._cloud_session.cluster_modify(cluster)

    def patch_cluster(
        self,
        cluster: t.Union[dto.Cluster, str]
    ) -> dto.Cluster:
        """
        Patches the given existing cluster.
        """
        if not isinstance(cluster, dto.Cluster):
            cluster = self.find_cluster(cluster)
        if cluster.status in {dto.ClusterStatus.CONFIGURING, dto.ClusterStatus.DELETING}:
            raise errors.InvalidOperationError(
                'Cannot patch cluster with status {}'.format(cluster.status.name)
            )
        cluster = self._driver.patch_cluster(cluster, self._ctx)
        return self._cloud_session.cluster_modify(cluster)

    def delete_cluster(
        self,
        cluster: t.Union[dto.Cluster, str]
    ) -> t.Optional[dto.Cluster]:
        """
        Deletes an existing cluster.
        """
        if not isinstance(cluster, dto.Cluster):
            cluster = self.find_cluster(cluster)
        if cluster.status in {dto.ClusterStatus.CONFIGURING, dto.ClusterStatus.DELETING}:
            raise errors.InvalidOperationError(
                'Cannot delete cluster with status {}'.format(cluster.status.name)
            )
        cluster = self._driver.delete_cluster(cluster, self._ctx)
        if cluster:
            return self._cloud_session.cluster_modify(cluster)
        else:
            return None

    def close(self):
        """
        Release any resources held by this cluster manager.
        """
        # By default, this is a NOOP

    def __enter__(self):
        """
        Called when entering a context manager block.
        """
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """
        Called when exiting a context manager block. Ensures that close is called.
        """
        self.close()

    def __del__(self):
        """
        Ensures that close is called when the session is garbage collected.
        """
        self.close()
