"""
This module defines the interface for a cloud provider.
"""

from typing import Any, Iterable, Mapping, Optional, Tuple, Union

from . import dto, errors, validation


class Provider:
    """
    Class for a cloud provider.
    """
    def authenticate(self, username: str, password: str) -> 'UnscopedSession':
        """
        Creates a new unscoped session for this provider using the given credentials.
        """
        raise errors.UnsupportedOperationError(
            "Operation not supported for provider '{}'".format(self.provider_name)
        )

    def from_token(self, token: str) -> 'UnscopedSession':
        """
        Creates an unscoped session from the given token as returned from the
        ``token`` method of the corresponding :py:class:`UnscopedSession`.
        """
        raise NotImplementedError


class UnscopedSession:
    """
    Class for an authenticated session with a cloud provider. It is unscoped in
    the sense that is not bound to a particular tenancy.
    """
    def token(self) -> str:
        """
        Returns the token for this session.

        The returned token should be consumable by the ``from_token`` method of the
        corresponding :py:class:`Provider`.
        """
        raise NotImplementedError

    def username(self) -> str:
        """
        Returns the username for this session.
        """
        raise NotImplementedError

    def capabilities(self) -> dto.Capabilities:
        """
        Returns an object describing the capabilities of the cloud.
        """
        raise NotImplementedError

    def ssh_public_key(self, key_name: str) -> str:
        """
        Return a named SSH public key.
        """
        raise errors.UnsupportedOperationError(
            "Operation not supported for provider '{}'".format(self.provider_name)
        )

    def update_ssh_public_key(self, key_name: str, public_key: str) -> str:
        """
        Update a stored SSH public key and returns the new SSH key.
        """
        raise errors.UnsupportedOperationError(
            "Operation not supported for provider '{}'".format(self.provider_name)
        )

    def tenancies(self) -> Iterable[dto.Tenancy]:
        """
        Get the tenancies available to the authenticated user.
        """
        raise errors.UnsupportedOperationError(
            "Operation not supported for provider '{}'".format(self.provider_name)
        )

    def scoped_session(self, tenancy: Union[dto.Tenancy, str]) -> 'ScopedSession':
        """
        Get a scoped session for the given tenancy.
        """
        raise errors.UnsupportedOperationError(
            "Operation not supported for provider '{}'".format(self.provider_name)
        )

    def close(self):
        """
        Closes the session and performs any cleanup.
        """
        # This is a NOOP by default

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


class ScopedSession:
    """
    Class for a tenancy-scoped session.
    """
    def quotas(self) -> Iterable[dto.Quota]:
        """
        Returns quota information for the tenancy.

        Quota information for the following resources should always be present:

          * ``cpus``: The vCPUs available to the tenancy.
          * ``ram``: The RAM available to the tenancy.
          * ``external_ips``: The external IPs available to the tenancy.
          * ``storage``: The storage available to the tenancy.

        Some implementations may also include:

          * ``machines``: The number of machines in the tenancy.
          * ``volumes``: The number of volumes in the tenancy.

        The absence of these resources indicates that there is no specific limit.
        """
        raise errors.UnsupportedOperationError(
            "Operation not supported for provider '{}'".format(self.provider_name)
        )

    def images(self) -> Iterable[dto.Image]:
        """
        Lists the images available to the tenancy.
        """
        raise errors.UnsupportedOperationError(
            "Operation not supported for provider '{}'".format(self.provider_name)
        )

    def find_image(self, id: str) -> dto.Image:
        """
        Finds an image by id.
        """
        raise errors.UnsupportedOperationError(
            "Operation not supported for provider '{}'".format(self.provider_name)
        )

    def sizes(self) -> Iterable[dto.Size]:
        """
        Lists the machine sizes available to the tenancy.
        """
        raise errors.UnsupportedOperationError(
            "Operation not supported for provider '{}'".format(self.provider_name)
        )

    def find_size(self, id: str) -> dto.Size:
        """
        Finds a size by id.
        """
        raise errors.UnsupportedOperationError(
            "Operation not supported for provider '{}'".format(self.provider_name)
        )

    def machines(self) -> Iterable[dto.Machine]:
        """
        Lists the machines in the tenancy.
        """
        raise errors.UnsupportedOperationError(
            "Operation not supported for provider '{}'".format(self.provider_name)
        )

    def find_machine(self, id: str) -> dto.Machine:
        """
        Finds a machine by id.
        """
        raise errors.UnsupportedOperationError(
            "Operation not supported for provider '{}'".format(self.provider_name)
        )

    def fetch_logs_for_machine(self, machine: Union[dto.Machine, str]) -> Iterable[str]:
        """
        Returns the log lines for the given machine.
        """
        raise errors.UnsupportedOperationError(
            "Operation not supported for provider '{}'".format(self.provider_name)
        )

    def create_machine(
        self,
        name: str,
        image: Union[dto.Image, str],
        size: Union[dto.Size, str],
        ssh_key: Optional[str] = None,
        metadata: Optional[Mapping[str, str]] = None,
        userdata: Optional[str] = None
    ) -> dto.Machine:
        """
        Create a new machine in the tenancy.
        """
        raise errors.UnsupportedOperationError(
            "Operation not supported for provider '{}'".format(self.provider_name)
        )

    def resize_machine(
        self,
        machine: Union[dto.Machine, str],
        size: Union[dto.Size, str]
    ) -> dto.Machine:
        """
        Change the size of a machine.
        """
        raise errors.UnsupportedOperationError(
            "Operation not supported for provider '{}'".format(self.provider_name)
        )

    def start_machine(self, machine: Union[dto.Machine, str]) -> dto.Machine:
        """
        Start the specified machine.
        """
        raise errors.UnsupportedOperationError(
            "Operation not supported for provider '{}'".format(self.provider_name)
        )

    def stop_machine(self, machine: Union[dto.Machine, str]) -> dto.Machine:
        """
        Stop the specified machine.
        """
        raise errors.UnsupportedOperationError(
            "Operation not supported for provider '{}'".format(self.provider_name)
        )

    def restart_machine(self, machine: Union[dto.Machine, str]) -> dto.Machine:
        """
        Restart the specified machine.
        """
        raise errors.UnsupportedOperationError(
            "Operation not supported for provider '{}'".format(self.provider_name)
        )

    def delete_machine(self, machine: Union[dto.Machine, str]) -> Optional[dto.Machine]:
        """
        Delete the specified machine.
        """
        raise errors.UnsupportedOperationError(
            "Operation not supported for provider '{}'".format(self.provider_name)
        )

    def fetch_firewall_rules_for_machine(
        self,
        machine: Union[dto.Machine, str]
    ) -> Iterable[dto.FirewallGroup]:
        """
        Returns the firewall rules for the machine.
        """
        raise errors.UnsupportedOperationError(
            "Operation not supported for provider '{}'".format(self.provider_name)
        )

    def add_firewall_rule_to_machine(
        self,
        machine: Union[dto.Machine, str],
        # See the DTO for details of the options
        direction: dto.FirewallRuleDirection,
        protocol: dto.FirewallRuleProtocol,
        port: Optional[int] = None,
        remote_cidr: Optional[str] = None
    ) -> Iterable[dto.FirewallGroup]:
        """
        Adds a firewall rule to the specified machine and returns the new set of rules.
        """
        raise errors.UnsupportedOperationError(
            "Operation not supported for provider '{}'".format(self.provider_name)
        )

    def remove_firewall_rule_from_machine(
        self,
        machine: Union[dto.Machine, str],
        firewall_rule: Union[dto.FirewallRule, str]
    ) -> Iterable[dto.FirewallGroup]:
        """
        Removes the specified firewall rule from the machine and returns the new set
        of rules.
        """
        raise errors.UnsupportedOperationError(
            "Operation not supported for provider '{}'".format(self.provider_name)
        )

    def external_ips(self) -> Iterable[dto.ExternalIp]:
        """
        Returns the external IP addresses that are currently allocated to the
        tenancy.
        """
        raise errors.UnsupportedOperationError(
            "Operation not supported for provider '{}'".format(self.provider_name)
        )

    def find_external_ip(self, id: str) -> dto.ExternalIp:
        """
        Finds an external IP by id.
        """
        raise errors.UnsupportedOperationError(
            "Operation not supported for provider '{}'".format(self.provider_name)
        )

    def allocate_external_ip(self) -> dto.ExternalIp:
        """
        Allocates a new external IP address for the tenancy from a pool and returns
        it.
        """
        raise errors.UnsupportedOperationError(
            "Operation not supported for provider '{}'".format(self.provider_name)
        )

    def attach_external_ip(
        self,
        ip: Union[dto.ExternalIp, str],
        machine: Union[dto.Machine, str]
    ) -> dto.ExternalIp:
        """
        Attaches an external IP to a machine.
        """
        raise errors.UnsupportedOperationError(
            "Operation not supported for provider '{}'".format(self.provider_name)
        )

    def detach_external_ip(self, ip: Union[dto.ExternalIp, str]) -> dto.ExternalIp:
        """
        Detaches the given external IP from whichever machine it is currently
        attached to.
        """
        raise errors.UnsupportedOperationError(
            "Operation not supported for provider '{}'".format(self.provider_name)
        )

    def volumes(self) -> Iterable[dto.Volume]:
        """
        Lists the volumes currently available to the tenancy.
        """
        raise errors.UnsupportedOperationError(
            "Operation not supported for provider '{}'".format(self.provider_name)
        )

    def find_volume(self, id: str) -> dto.Volume:
        """
        Finds a volume by id.
        """
        raise errors.UnsupportedOperationError(
            "Operation not supported for provider '{}'".format(self.provider_name)
        )

    def create_volume(self, name: str, size: int) -> dto.Volume:
        """
        Create a new volume in the tenancy.
        """
        raise errors.UnsupportedOperationError(
            "Operation not supported for provider '{}'".format(self.provider_name)
        )

    def delete_volume(self, volume: Union[dto.Volume, str]) -> Optional[dto.Volume]:
        """
        Delete the specified volume.
        """
        raise errors.UnsupportedOperationError(
            "Operation not supported for provider '{}'".format(self.provider_name)
        )

    def attach_volume(
        self,
        volume: Union[dto.Volume, str],
        machine: Union[dto.Machine, str]
    ) -> dto.Volume:
        """
        Attaches the specified volume to the specified machine.
        """
        raise errors.UnsupportedOperationError(
            "Operation not supported for provider '{}'".format(self.provider_name)
        )

    def detach_volume(self, volume: Union[dto.Volume, str]) -> dto.Volume:
        """
        Detaches the specified volume from the machine it is attached to.
        """
        raise errors.UnsupportedOperationError(
            "Operation not supported for provider '{}'".format(self.provider_name)
        )

    def cluster_types(self) -> Iterable[dto.ClusterType]:
        """
        Lists the available cluster types.
        """
        raise errors.UnsupportedOperationError(
            "Operation not supported for provider '{}'".format(self.provider_name)
        )

    def find_cluster_type(self, name: str) -> dto.ClusterType:
        """
        Find a cluster type by name.
        """
        raise errors.UnsupportedOperationError(
            "Operation not supported for provider '{}'".format(self.provider_name)
        )

    def clusters(self) -> Iterable[dto.Cluster]:
        """
        List the clusters that are deployed.
        """
        raise errors.UnsupportedOperationError(
            "Operation not supported for provider '{}'".format(self.provider_name)
        )

    def find_cluster(self, id: str) -> dto.Cluster:
        """
        Find a cluster by id.
        """
        raise errors.UnsupportedOperationError(
            "Operation not supported for provider '{}'".format(self.provider_name)
        )

    def validate_cluster_params(
        self,
        cluster_type: Union[dto.ClusterType, str],
        params: Mapping[str, Any],
        prev_params: Mapping[str, Any] = {}
    ) -> Mapping[str, Any]:
        """
        Validates the given parameter values against the given cluster type.

        If validation fails, :py:class:`~.errors.ValidationError` should be raised.
        """
        if not isinstance(cluster_type, dto.ClusterType):
            cluster_type = self.find_cluster_type(cluster_type)
        validator = validation.build_validator(
            self,
            cluster_type.parameters,
            prev_params
        )
        return validator(params)

    def create_cluster(
        self,
        name: str,
        cluster_type: Union[dto.ClusterType, str],
        params: Mapping[str, Any],
        ssh_key: str
    ) -> dto.Cluster:
        """
        Creates a new cluster with the given name, type and parameters.
        """
        raise errors.UnsupportedOperationError(
            "Operation not supported for provider '{}'".format(self.provider_name)
        )

    def update_cluster(
        self,
        cluster: Union[dto.Cluster, str],
        params: Mapping[str, Any]
    ) -> dto.Cluster:
        """
        Updates an existing cluster with the given parameters.
        """
        raise errors.UnsupportedOperationError(
            "Operation not supported for provider '{}'".format(self.provider_name)
        )

    def patch_cluster(self, cluster: Union[dto.Cluster, str]) -> dto.Cluster:
        """
        Patches an existing cluster.
        """
        raise errors.UnsupportedOperationError(
            "Operation not supported for provider '{}'".format(self.provider_name)
        )

    def delete_cluster(self, cluster: Union[dto.Cluster, str]) -> Optional[dto.Cluster]:
        """
        Deletes an existing cluster.
        """
        raise errors.UnsupportedOperationError(
            "Operation not supported for provider '{}'".format(self.provider_name)
        )

    def close(self):
        """
        Closes the session and performs any cleanup.
        """
        # This is a NOOP by default

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
