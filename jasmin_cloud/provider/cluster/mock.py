"""
This module defines a mock implementation of a cluster engine.
"""

from .. import errors
from . import base


class Engine(base.Engine):
    """
    Base class for a cluster engine.
    """
    def __init__(self, cluster_types):
        self._cluster_types = cluster_types

    def create_manager(self, tenancy):
        """
        Creates a cluster manager for the given tenancy.

        Args:
            tenancy: The :py:class:`~..provider.dto.Tenancy`.

        Returns:
            A :py:class:`ClusterManager`.
        """
        return ClusterManager(self._cluster_types)


class ClusterManager(base.ClusterManager):
    """
    Base class for a tenancy-scoped cluster manager.
    """
    def __init__(self, cluster_types):
        self._cluster_types = cluster_types

    def cluster_types(self):
        return tuple(self._cluster_types)

    def find_cluster_type(self, name):
        try:
            return next(ct for ct in self.cluster_types() if ct.name == name)
        except StopIteration:
            raise errors.ObjectNotFoundError("Could not find cluster type '{}'".format(name))

    def clusters(self):
        return []

    def find_cluster(self, name):
        try:
            return next(c for c in self.clusters() if c.name == name)
        except StopIteration:
            raise errors.ObjectNotFoundError("Could not find cluster '{}'".format(name))

    def create_cluster(self, name, cluster_type, params):
        raise NotImplementedError

    def update_cluster(self, name, params):
        raise NotImplementedError

    def delete_cluster(self, name):
        raise NotImplementedError