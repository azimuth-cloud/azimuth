"""
This module defines the base class for cluster managers.
"""

from dataclasses import dataclass


@dataclass
class Credential:
    """
    DTO for a credential that is passed from the provider to interact with a cloud.

    Credentials should be ephemeral and have an expiry, e.g. a token.
    """
    #: The credential type
    type: str
    #: The credential data
    data: dict


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

    def create_cluster(self, name, cluster_type, params, ssh_key, credential):
        """
        Creates a new cluster with the given name, type and parameters.

        Args:
            name: The name of the cluster.
            cluster_type: The :py:class:`~..dto.ClusterType`.
            params: Dictionary of parameter values as required by the
                    cluster type.
            ssh_key: The SSH public key to inject for admin access.
            credential: The :py:class:`Credential` to use for accessing cloud resources.

        Returns:
            A :py:class:`~..dto.Cluster`.
        """
        raise NotImplementedError

    def update_cluster(self, cluster, params, credential):
        """
        Updates an existing cluster with the given parameters.

        Args:
            cluster: The cluster to update.
                     Can be an id or a :py:class:`~..dto.Cluster`.
            params: Dictionary of parameters values as required by the
                    cluster type.
            credential: The :py:class:`Credential` to use for accessing cloud resources.

        Returns:
            The updated :py:class:`~..dto.Cluster`.
        """
        raise NotImplementedError

    def patch_cluster(self, cluster, credential):
        """
        Patches the given existing cluster.

        Args:
            cluster: The cluster to patch.
                     Can be an id or a :py:class:`~..dto.Cluster`.
            credential: The :py:class:`Credential` to use for accessing cloud resources.

        Returns:
            The :py:class:`~..dto.Cluster` being patched.
        """
        raise NotImplementedError

    def delete_cluster(self, cluster, credential):
        """
        Deletes an existing cluster.

        Args:
            cluster: The cluster to delete.
                     Can be an id or a :py:class:`~..dto.Cluster`.
            credential: The :py:class:`Credential` to use for accessing cloud resources.

        Returns:
            The deleted :py:class:`~..dto.Cluster`.
        """
        raise NotImplementedError

    def close(self):
        """
        Release any resources held by this cluster manager.
        """
        # By default, this is a NOOP
