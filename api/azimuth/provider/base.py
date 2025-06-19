"""
This module defines the interface for a cloud provider.
"""

import functools
from typing import Any, Iterable, Mapping  # noqa: UP035

from azimuth_auth.session import dto as auth_dto
from azimuth_auth.session import errors as auth_errors
from azimuth_auth.session.base import Session as AuthSession

from ..cluster_engine import dto as clusters_dto
from . import dto, errors


def convert_auth_session_errors(f):
    """
    Decorator that converts errors from the auth session into provider errors.
    """

    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except auth_errors.AuthenticationError as exc:
            raise errors.AuthenticationError(str(exc))
        except auth_errors.PermissionDeniedError as exc:
            raise errors.PermissionDeniedError(str(exc))
        except auth_errors.BadInputError as exc:
            raise errors.BadInputError(str(exc))
        except auth_errors.ObjectNotFoundError as exc:
            raise errors.ObjectNotFoundError(str(exc))
        except auth_errors.InvalidOperationError as exc:
            raise errors.InvalidOperationError(str(exc))
        except auth_errors.CommunicationError as exc:
            raise errors.CommunicationError(str(exc)) from exc
        except auth_errors.Error as exc:
            raise errors.Error(str(exc)) from exc

    return wrapper


class Provider:
    """
    Class for a cloud provider.
    """

    def _from_auth_session(
        self, auth_session: AuthSession, auth_user: auth_dto.User
    ) -> "UnscopedSession":
        """
        Private method that creates an unscoped session from the given auth session and
        user.

        This method should be overridden in subclasses to create unscoped sessions.
        Subclasses can assume that the parent class will handle error conditions.
        """
        raise NotImplementedError

    @convert_auth_session_errors
    def from_auth_session(self, auth_session: AuthSession) -> "UnscopedSession":
        """
        Creates an unscoped session for the given auth session.
        """
        return self._from_auth_session(auth_session, auth_session.user())


class UnscopedSession:
    """
    Base class for an authenticated session with a cloud provider. It is unscoped in
    the sense that is not bound to a particular tenancy.

    By default, an unscoped session wraps an auth session, with only creation of the
    scoped session from the credential provided by the auth session being overridden.
    """

    def __init__(self, auth_session: AuthSession, auth_user: auth_dto.User):
        self.auth_session = auth_session
        self.auth_user = auth_user

    @convert_auth_session_errors
    def token(self) -> str:
        """
        Returns the token for this session.

        The returned token should be consumable by the ``from_token`` method of the
        corresponding :py:class:`Provider`.
        """
        return self.auth_session.token()

    def user_id(self) -> str:
        """
        Returns the user ID for this session.
        """
        return self.auth_user.id

    def username(self) -> str:
        """
        Returns the username for this session.
        """
        return self.auth_user.username

    def user_email(self) -> str | None:
        """
        Returns the email for the user who started the session.
        """
        return self.auth_user.email

    @convert_auth_session_errors
    def ssh_public_key(self) -> str:
        """
        Return the current SSH public key for the authenticated user.
        """
        return self.auth_session.ssh_public_key()

    @convert_auth_session_errors
    def update_ssh_public_key(self, public_key: str) -> str:
        """
        Update the stored SSH public key for the authenticated user and returns the new
        SSH key.
        """
        return self.auth_session.update_ssh_public_key(public_key)

    @convert_auth_session_errors
    def tenancies(self) -> Iterable[dto.Tenancy]:
        """
        Get the tenancies available to the authenticated user.
        """
        # Convert the tenancies from the auth DTO to the provider DTO
        return [dto.Tenancy(t.id, t.name) for t in self.auth_session.tenancies()]

    def _scoped_session(
        self, auth_user: auth_dto.User, tenancy: dto.Tenancy, credential_data: Any
    ) -> "ScopedSession":
        """
        Private method that creates a scoped session for the given tenancy.

        This method should be overridden in subclasses to create scoped sessions.
        Subclasses can assume that the parent class will handle error conditions.
        """
        raise NotImplementedError

    @convert_auth_session_errors
    def scoped_session(self, tenancy: dto.Tenancy | str) -> "ScopedSession":
        """
        Get a scoped session for the given tenancy.
        """
        # Make sure we have a tenancy object
        if not isinstance(tenancy, dto.Tenancy):
            try:
                tenancy = next(t for t in self.tenancies() if t.id == tenancy)
            except StopIteration:
                raise errors.ObjectNotFoundError(
                    f"Could not find tenancy with ID {tenancy}."
                )
        # Get the credential from the auth session
        credential = self.auth_session.credential(tenancy.id)
        # Verify that the provider matches this provider
        if credential.provider != self.provider_name:
            raise errors.InvalidOperationError("credential is for a different provider")
        return self._scoped_session(self.auth_user, tenancy, credential.data)

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

    def __init__(self, auth_user: auth_dto.User, tenancy: dto.Tenancy):
        self._auth_user = auth_user
        self._tenancy = tenancy

    def user_id(self) -> str:
        """
        Returns the username for this session.
        """
        return self._auth_user.id

    def username(self) -> str:
        """
        Returns the username for this session.
        """
        return self._auth_user.username

    def tenancy(self) -> dto.Tenancy:
        """
        Returns the tenancy for this session.
        """
        return self._tenancy

    def capabilities(self) -> dto.Capabilities:
        """
        Returns an object describing the capabilities available in the tenancy.
        """
        raise NotImplementedError

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
            f"Operation not supported for provider '{self.provider_name}'"
        )

    def images(self) -> Iterable[dto.Image]:
        """
        Lists the images available to the tenancy.
        """
        raise errors.UnsupportedOperationError(
            f"Operation not supported for provider '{self.provider_name}'"
        )

    def find_image(self, id: str) -> dto.Image:  # noqa: A002
        """
        Finds an image by id.
        """
        raise errors.UnsupportedOperationError(
            f"Operation not supported for provider '{self.provider_name}'"
        )

    def sizes(self) -> Iterable[dto.Size]:
        """
        Lists the machine sizes available to the tenancy.
        """
        raise errors.UnsupportedOperationError(
            f"Operation not supported for provider '{self.provider_name}'"
        )

    def find_size(self, id: str) -> dto.Size:  # noqa: A002
        """
        Finds a size by id.
        """
        raise errors.UnsupportedOperationError(
            f"Operation not supported for provider '{self.provider_name}'"
        )

    def machines(self) -> Iterable[dto.Machine]:
        """
        Lists the machines in the tenancy.
        """
        raise errors.UnsupportedOperationError(
            f"Operation not supported for provider '{self.provider_name}'"
        )

    def find_machine(self, id: str) -> dto.Machine:  # noqa: A002
        """
        Finds a machine by id.
        """
        raise errors.UnsupportedOperationError(
            f"Operation not supported for provider '{self.provider_name}'"
        )

    def fetch_logs_for_machine(self, machine: dto.Machine | str) -> Iterable[str]:
        """
        Returns the log lines for the given machine.
        """
        raise errors.UnsupportedOperationError(
            f"Operation not supported for provider '{self.provider_name}'"
        )

    def create_machine(
        self,
        name: str,
        image: dto.Image | str,
        size: dto.Size | str,
        ssh_key: str | None = None,
        metadata: Mapping[str, str] | None = None,
        userdata: str | None = None,
    ) -> dto.Machine:
        """
        Create a new machine in the tenancy.
        """
        raise errors.UnsupportedOperationError(
            f"Operation not supported for provider '{self.provider_name}'"
        )

    def resize_machine(
        self, machine: dto.Machine | str, size: dto.Size | str
    ) -> dto.Machine:
        """
        Change the size of a machine.
        """
        raise errors.UnsupportedOperationError(
            f"Operation not supported for provider '{self.provider_name}'"
        )

    def start_machine(self, machine: dto.Machine | str) -> dto.Machine:
        """
        Start the specified machine.
        """
        raise errors.UnsupportedOperationError(
            f"Operation not supported for provider '{self.provider_name}'"
        )

    def stop_machine(self, machine: dto.Machine | str) -> dto.Machine:
        """
        Stop the specified machine.
        """
        raise errors.UnsupportedOperationError(
            f"Operation not supported for provider '{self.provider_name}'"
        )

    def restart_machine(self, machine: dto.Machine | str) -> dto.Machine:
        """
        Restart the specified machine.
        """
        raise errors.UnsupportedOperationError(
            f"Operation not supported for provider '{self.provider_name}'"
        )

    def delete_machine(self, machine: dto.Machine | str) -> dto.Machine | None:
        """
        Delete the specified machine.
        """
        raise errors.UnsupportedOperationError(
            f"Operation not supported for provider '{self.provider_name}'"
        )

    def fetch_firewall_rules_for_machine(
        self, machine: dto.Machine | str
    ) -> Iterable[dto.FirewallGroup]:
        """
        Returns the firewall rules for the machine.
        """
        raise errors.UnsupportedOperationError(
            f"Operation not supported for provider '{self.provider_name}'"
        )

    def add_firewall_rule_to_machine(
        self,
        machine: dto.Machine | str,
        # See the DTO for details of the options
        direction: dto.FirewallRuleDirection,
        protocol: dto.FirewallRuleProtocol,
        port: int | None = None,
        remote_cidr: str | None = None,
    ) -> Iterable[dto.FirewallGroup]:
        """
        Adds a firewall rule to the specified machine and returns the new set of rules.
        """
        raise errors.UnsupportedOperationError(
            f"Operation not supported for provider '{self.provider_name}'"
        )

    def remove_firewall_rule_from_machine(
        self, machine: dto.Machine | str, firewall_rule: dto.FirewallRule | str
    ) -> Iterable[dto.FirewallGroup]:
        """
        Removes the specified firewall rule from the machine and returns the new set
        of rules.
        """
        raise errors.UnsupportedOperationError(
            f"Operation not supported for provider '{self.provider_name}'"
        )

    def external_ips(self) -> Iterable[dto.ExternalIp]:
        """
        Returns the external IP addresses that are currently allocated to the
        tenancy.
        """
        raise errors.UnsupportedOperationError(
            f"Operation not supported for provider '{self.provider_name}'"
        )

    def find_external_ip(self, id: str) -> dto.ExternalIp:  # noqa: A002
        """
        Finds an external IP by id.
        """
        raise errors.UnsupportedOperationError(
            f"Operation not supported for provider '{self.provider_name}'"
        )

    def find_external_ip_by_ip_address(self, ip_address: str):
        """
        Finds an external IP by the IP address.
        """
        raise errors.UnsupportedOperationError(
            f"Operation not supported for provider '{self.provider_name}'"
        )

    def allocate_external_ip(self) -> dto.ExternalIp:
        """
        Allocates a new external IP address for the tenancy from a pool and returns
        it.
        """
        raise errors.UnsupportedOperationError(
            f"Operation not supported for provider '{self.provider_name}'"
        )

    def attach_external_ip(
        self, ip: dto.ExternalIp | str, machine: dto.Machine | str
    ) -> dto.ExternalIp:
        """
        Attaches an external IP to a machine.
        """
        raise errors.UnsupportedOperationError(
            f"Operation not supported for provider '{self.provider_name}'"
        )

    def detach_external_ip(self, ip: dto.ExternalIp | str) -> dto.ExternalIp:
        """
        Detaches the given external IP from whichever machine it is currently
        attached to.
        """
        raise errors.UnsupportedOperationError(
            f"Operation not supported for provider '{self.provider_name}'"
        )

    def volumes(self) -> Iterable[dto.Volume]:
        """
        Lists the volumes currently available to the tenancy.
        """
        raise errors.UnsupportedOperationError(
            f"Operation not supported for provider '{self.provider_name}'"
        )

    def find_volume(self, id: str) -> dto.Volume:  # noqa: A002
        """
        Finds a volume by id.
        """
        raise errors.UnsupportedOperationError(
            f"Operation not supported for provider '{self.provider_name}'"
        )

    def create_volume(self, name: str, size: int) -> dto.Volume:
        """
        Create a new volume in the tenancy.
        """
        raise errors.UnsupportedOperationError(
            f"Operation not supported for provider '{self.provider_name}'"
        )

    def delete_volume(self, volume: dto.Volume | str) -> dto.Volume | None:
        """
        Delete the specified volume.
        """
        raise errors.UnsupportedOperationError(
            f"Operation not supported for provider '{self.provider_name}'"
        )

    def attach_volume(
        self, volume: dto.Volume | str, machine: dto.Machine | str
    ) -> dto.Volume:
        """
        Attaches the specified volume to the specified machine.
        """
        raise errors.UnsupportedOperationError(
            f"Operation not supported for provider '{self.provider_name}'"
        )

    def detach_volume(self, volume: dto.Volume | str) -> dto.Volume:
        """
        Detaches the specified volume from the machine it is attached to.
        """
        raise errors.UnsupportedOperationError(
            f"Operation not supported for provider '{self.provider_name}'"
        )

    def cloud_credential(self, name: str, description: str) -> dto.Credential:
        """
        Returns a credential with the given name for interacting with the cloud.
        """
        raise errors.UnsupportedOperationError(
            f"Operation not supported for provider '{self.provider_name}'"
        )

    def cluster_parameters(self) -> Mapping[str, Any]:
        """
        Returns any additional cluster parameters required for cloud infrastructure.
        """
        return {}

    def cluster_modify(self, cluster: clusters_dto.Cluster) -> clusters_dto.Cluster:
        """
        Modifies the cluster with cloud-specific information, e.g. removing injected
        parameters, converting error messages.
        """
        return cluster

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
