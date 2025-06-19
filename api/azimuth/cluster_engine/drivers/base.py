"""
This module defines the base class for cluster managers.
"""

import typing as t

from ...scheduling import dto as scheduling_dto
from .. import dto


class Driver:
    """
    Base class for a cluster driver.

    Drivers do not need to worry about validation etc. They just deal with the machinery
    of managing a cluster of a particular type.
    """

    def cluster_types(self, ctx: dto.Context) -> t.Iterable[dto.ClusterType]:
        """
        Lists the available cluster types.
        """
        raise NotImplementedError

    def find_cluster_type(self, name: str, ctx: dto.Context) -> dto.ClusterType:
        """
        Find a cluster type by name.
        """
        raise NotImplementedError

    def clusters(self, ctx: dto.Context) -> t.Iterable[dto.Cluster]:
        """
        List the clusters that are deployed.
        """
        raise NotImplementedError

    def find_cluster(self, id: str, ctx: dto.Context) -> dto.Cluster:  # noqa: A002
        """
        Find a cluster by id.
        """
        raise NotImplementedError

    def create_cluster(
        self,
        name: str,
        cluster_type: dto.ClusterType,
        params: t.Mapping[str, t.Any],
        resources: scheduling_dto.PlatformResources,
        schedule: scheduling_dto.PlatformSchedule | None,
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

    def patch_cluster(
        self, cluster: dto.Cluster, params: t.Mapping[str, t.Any], ctx: dto.Context
    ) -> dto.Cluster:
        """
        Patches the given existing cluster.
        """
        raise NotImplementedError

    def delete_cluster(
        self, cluster: dto.Cluster, ctx: dto.Context
    ) -> dto.Cluster | None:
        """
        Deletes an existing cluster.
        """
        raise NotImplementedError

    def close(self):
        """
        Release any resources held by this driver.
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
