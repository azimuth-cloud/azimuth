"""
This module defines the base class for cluster managers.
"""


class Engine:
    """
    Base class for a cluster engine.
    """
    def create_manager(self, tenancy):
        """
        Creates a cluster manager for the given tenancy.

        Args:
            tenancy: The :py:class:`~..dto.Tenancy`.

        Returns:
            A :py:class:`ClusterManager`.
        """
        raise NotImplementedError


class ClusterManager:
    """
    Base class for a tenancy-scoped cluster manager.
    """
    def cluster_types(self):
        """
        Lists the available cluster types.

        Returns:
            An iterable of :py:class:`~..dto.ClusterType`s.
        """
        raise NotImplementedError

    def find_cluster_type(self, name):
        """
        Find a cluster type by name.

        Args:
            name: The name of the cluster type.

        Returns:
            A :py:class:`~..dto.ClusterType`.
        """
        raise NotImplementedError

    def clusters(self):
        """
        List the clusters that are deployed.

        Returns:
            An iterable of :py:class:`~..dto.Cluster`s.
        """
        raise NotImplementedError

    def find_cluster(self, name):
        """
        Find a cluster by name.

        Args:
            name: The name of the cluster.

        Returns:
            A :py:class:`~..dto.Cluster`.
        """
        raise NotImplementedError

    def create_cluster(self, name, cluster_type, params):
        """
        Creates a new cluster with the given name, type and parameters.

        Args:
            name: The name of the cluster.
            cluster_type: The cluster type. Can be a name or a
                          :py:class:`~..dto.ClusterType`.
            params: Dictionary of parameters values as required by the
                    cluster type.

        Returns:
            A :py:class:`~..dto.Cluster`.
        """
        raise NotImplementedError

    def update_cluster(self, name, params):
        """
        Updates an existing named cluster with the given parameters.

        Args:
            name: The name of the cluster.
            cluster_type: The cluster type. Can be a name or a
                          :py:class:`~..dto.ClusterType`.
            params: Dictionary of parameters values as required by the
                    cluster type.

        Returns:
            The updated :py:class:`~..dto.Cluster`.
        """
        raise NotImplementedError

    def delete_cluster(self, name):
        """
        Deletes an existing named cluster.

        Args:
            name: The name of the cluster.

        Returns:
            The deleted :py:class:`~..dto.Cluster`.
        """
        raise NotImplementedError
