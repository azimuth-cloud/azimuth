"""
This module defines the base class for cluster managers.
"""


class Engine:
    """
    Base class for a cluster engine.
    """
    def create_manager(self, username, tenancy):
        """
        Creates a cluster manager for the given tenancy.

        Args:
            username: The username of the user.
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

    def find_cluster(self, id):
        """
        Find a cluster by id.

        Args:
            id: The id of the cluster.

        Returns:
            A :py:class:`~..dto.Cluster`.
        """
        raise NotImplementedError

    def create_cluster(self, name, cluster_type, params, *args, **kwargs):
        """
        Creates a new cluster with the given name, type and parameters.

        Args:
            name: The name of the cluster.
            cluster_type: The :py:class:`~..dto.ClusterType`.
            params: Dictionary of parameter values as required by the
                    cluster type.
            args: Any additional arguments as required by implementations.
            kwargs: Any additional arguments as required by implementations.

        Returns:
            A :py:class:`~..dto.Cluster`.
        """
        raise NotImplementedError

    def update_cluster(self, cluster, params, *args, **kwargs):
        """
        Updates an existing cluster with the given parameters.

        Args:
            cluster: The cluster to update.
                     Can be an id or a :py:class:`~..dto.Cluster`.
            params: Dictionary of parameters values as required by the
                    cluster type.
            args: Any additional arguments as required by implementations.
            kwargs: Any additional arguments as required by implementations.

        Returns:
            The updated :py:class:`~..dto.Cluster`.
        """
        raise NotImplementedError

    def patch_cluster(self, cluster, *args, **kwargs):
        """
        Patches the given existing cluster.

        Args:
            cluster: The cluster to patch.
                     Can be an id or a :py:class:`~..dto.Cluster`.
            args: Any additional arguments as required by implementations.
            kwargs: Any additional arguments as required by implementations.

        Returns:
            The :py:class:`~..dto.Cluster` being patched.
        """
        raise NotImplementedError

    def delete_cluster(self, cluster, *args, **kwargs):
        """
        Deletes an existing cluster.

        Args:
            cluster: The cluster to delete.
                     Can be an id or a :py:class:`~..dto.Cluster`.
            args: Any additional arguments as required by implementations.
            kwargs: Any additional arguments as required by implementations.

        Returns:
            The deleted :py:class:`~..dto.Cluster`.
        """
        raise NotImplementedError

    def close(self):
        """
        Release any resources held by this cluster manager.
        """
        # By default, this is a NOOP
