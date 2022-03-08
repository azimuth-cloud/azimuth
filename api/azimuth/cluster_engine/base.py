"""
This module defines the base class for cluster managers.
"""

from dataclasses import dataclass
import typing as t

from ..provider import base as cloud_base

from . import dto, errors


class Engine:
    """
    Base class for a cluster engine.
    """
    def create_manager(self, cloud_session: cloud_base.ScopedSession) -> 'ClusterManager':
        """
        Creates a cluster manager for the given tenancy-scoped cloud session.
        """
        raise NotImplementedError


class ClusterManager:
    """
    Base class for a tenancy-scoped cluster manager.
    """
    def __init__(self, cloud_session: cloud_base.ScopedSession):
        self._cloud_session = cloud_session

    def _cluster_types(self) -> t.Iterator[dto.ClusterType]:
        """
        Private method that lists the available cluster types.
        
        Any pre- or post-processing is handled by the public method.
        """
        raise NotImplementedError

    def cluster_types(self) -> t.Iterable[dto.ClusterType]:
        """
        Lists the available cluster types.
        """
        return self._cluster_types()

    def _find_cluster_type(self, name: str) -> dto.ClusterType:
        """
        Find a cluster type by name.
        
        Any pre- or post-processing is handled by the public method.
        """
        raise NotImplementedError

    def find_cluster_type(self, name: str) -> dto.ClusterType:
        """
        Find a cluster type by name.
        """
        return self._find_cluster_type(name)

    def _clusters(self) -> t.Iterable[dto.Cluster]:
        """
        List the clusters that are deployed.
        
        Any pre- or post-processing is handled by the public method.
        """
        raise NotImplementedError

    def clusters(self) -> t.Iterable[dto.Cluster]:
        """
        List the clusters that are deployed.
        """
        for cluster in self._clusters():
            yield self._cloud_session.cluster_modify(cluster)

    def _find_cluster(self, id: str) -> dto.Cluster:
        """
        Find a cluster by id.
        
        Any pre- or post-processing is handled by the public method.
        """
        raise NotImplementedError

    def find_cluster(self, id: str) -> dto.Cluster:
        """
        Find a cluster by id.
        """
        return self._cloud_session.cluster_modify(self._find_cluster(id))

    def validate_cluster_params(
        self,
        cluster_type: t.Union[dto.ClusterType, str],
        params: t.Mapping[str, t.Any],
        prev_params: t.Mapping[str, t.Any] = {}
    ) -> t.Mapping[str, t.Any]:
        """
        Validates the given parameter values against the given cluster type.

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

    def _create_cluster(
        self,
        name: str,
        cluster_type: dto.ClusterType,
        params: t.Mapping[str, t.Any],
        ssh_key: str,
        credential: dto.Credential
    ):
        """
        Create a new cluster with the given name, type and parameters.
        
        Any pre- or post-processing is handled by the public method, such as ensuring the
        parameters are validated and a cloud credential is available.
        """
        raise NotImplementedError

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
            print("VALIDATING PARAMETERS HERE")
            params = self.validate_cluster_params(cluster_type, params)
        # Inject any cloud-specific parameters
        params.update(self._cloud_session.cluster_parameters())
        credential = self._cloud_session.cluster_credential()
        cluster = self._create_cluster(name, cluster_type, params, ssh_key, credential)
        return self._cloud_session.cluster_modify(cluster)

    def _update_cluster(
        self,
        cluster: dto.Cluster,
        params: t.Mapping[str, t.Any],
        credential: dto.Credential
    ) -> dto.Cluster:
        """
        Updates an existing cluster with the given parameters.
        
        Any pre- or post-processing is handled by the public method, such as ensuring the
        parameters are validated, the cluster is in a valid state for the operator and a
        cloud credential is available.
        """
        raise NotImplementedError

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
        credential = self._cloud_session.cluster_credential()
        cluster = self._update_cluster(cluster, params, credential)
        return self._cloud_session.cluster_modify(cluster)

    def _patch_cluster(
        self,
        cluster: dto.Cluster,
        credential: dto.Credential
    ) -> dto.Cluster:
        """
        Patches the given existing cluster.
        
        Any pre- or post-processing is handled by the public method, such as ensuring the
        parameters are validated, the cluster is in a valid state for the operator and a
        cloud credential is available.
        """
        raise NotImplementedError

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
        credential = self._cloud_session.cluster_credential()
        cluster = self._patch_cluster(cluster, credential)
        return self._cloud_session.cluster_modify(cluster)

    def _delete_cluster(
        self,
        cluster: dto.Cluster,
        credential: dto.Credential
    ) -> t.Optional[dto.Cluster]:
        """
        Deletes an existing cluster.
        
        Any pre- or post-processing is handled by the public method, such as ensuring the
        parameters are validated, the cluster is in a valid state for the operator and a
        cloud credential is available.
        """
        raise NotImplementedError

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
        credential = self._cloud_session.cluster_credential()
        cluster = self._delete_cluster(cluster, credential)
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
