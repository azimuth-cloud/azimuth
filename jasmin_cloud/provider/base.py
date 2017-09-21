"""
This module defines the interface for a cloud provider.
"""

from . import errors


class Provider:
    """
    Class for a cloud provider.
    """
    def authenticate(self, username, password):
        """
        Creates a new unscoped session for this provider using the given credentials.

        Args:
            username: The username to authenticate with.
            password: The password to authenticate with.

        Returns:
            An :py:class:`UnscopedSession` for the user.
        """
        raise errors.UnsupportedOperationError(
            "Operation not supported for provider '{}'".format(self.provider_name)
        )


class UnscopedSession:
    """
    Class for an authenticated session with a cloud provider. It is unscoped in
    the sense that is not bound to a particular tenancy.

    Implementations should be serialisable using pickle.
    """
    def tenancies(self):
        """
        Get the tenancies available to the authenticated user.

        Returns:
            An iterable of :py:class:`~.dto.Tenancy` objects.
        """
        raise errors.UnsupportedOperationError(
            "Operation not supported for provider '{}'".format(self.provider_name)
        )

    def scoped_session(self, tenancy):
        """
        Get a scoped session for the given tenancy.

        Args:
            tenancy: The tenancy to get a scoped session for. Can be a tenancy id
                or a :py:class:`~.dto.Tenancy` object.

        Returns:
            A :py:class:`~ScopedSession` for the tenancy.
        """
        raise errors.UnsupportedOperationError(
            "Operation not supported for provider '{}'".format(self.provider_name)
        )


class ScopedSession:
    """
    Class for a tenancy-scoped session.
    """
    def quotas(self):
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

        Returns:
            An iterable of :py:class:`~.dto.Quota` objects.
        """
        raise errors.UnsupportedOperationError(
            "Operation not supported for provider '{}'".format(self.provider_name)
        )

    def images(self):
        """
        Lists the images available to the tenancy.

        Returns:
            An iterable of :py:class:`~.dto.Image` objects.
        """
        raise errors.UnsupportedOperationError(
            "Operation not supported for provider '{}'".format(self.provider_name)
        )

    def find_image(self, id):
        """
        Finds an image by id.

        Args:
            id: The id of the image to find.

        Returns:
            An :py:class:`~.dto.Image` object.
        """
        raise errors.UnsupportedOperationError(
            "Operation not supported for provider '{}'".format(self.provider_name)
        )

    def sizes(self):
        """
        Lists the machine sizes available to the tenancy.

        Returns:
            An iterable of :py:class:`~.dto.Size` objects.
        """
        raise errors.UnsupportedOperationError(
            "Operation not supported for provider '{}'".format(self.provider_name)
        )

    def find_size(self, id):
        """
        Finds a size by id.

        Args:
            id: The id of the size to find.

        Returns:
            A :py:class:`~.dto.Size` object.
        """
        raise errors.UnsupportedOperationError(
            "Operation not supported for provider '{}'".format(self.provider_name)
        )

    def machines(self):
        """
        Lists the machines in the tenancy.

        Returns:
            An iterable of :py:class:`~.dto.Machine`\ s.
        """
        raise errors.UnsupportedOperationError(
            "Operation not supported for provider '{}'".format(self.provider_name)
        )

    def find_machine(self, id):
        """
        Finds a machine by id.

        Args:
            id: The id of the machine to find.

        Returns:
            A :py:class:`~.dto.Machine` object.
        """
        raise errors.UnsupportedOperationError(
            "Operation not supported for provider '{}'".format(self.provider_name)
        )

    def create_machine(self, name, image, size, ssh_key):
        """
        Create a new machine in the tenancy.

        Args:
            name: The name of the machine.
            image: The image to use. Can be an image id or a :py:class:`~.dto.Image`.
            size: The size to use. Can be a size id or a :py:class:`~.dto.Size`.
            ssh_key: The SSH key to inject into the machine.

        Returns:
            The created :py:class:`~.dto.Machine`.
        """
        raise errors.UnsupportedOperationError(
            "Operation not supported for provider '{}'".format(self.provider_name)
        )

    def resize_machine(self, machine, size):
        """
        Change the size of a machine.

        Args:
            machine: The machine. Can be a machine id or a :py:class:`~.dto.Machine`.
            size: The size to use. Can be a size id or a :py:class:`~.dto.Size`.

        Returns:
            The updated :py:class:`~.dto.Machine`.
        """
        raise errors.UnsupportedOperationError(
            "Operation not supported for provider '{}'".format(self.provider_name)
        )

    def start_machine(self, machine):
        """
        Start the specified machine.

        Args:
            machine: The machine. Can be a machine id or a :py:class:`~.dto.Machine`.

        Returns:
            The updated :py:class:`~.dto.Machine`.
        """
        raise errors.UnsupportedOperationError(
            "Operation not supported for provider '{}'".format(self.provider_name)
        )

    def stop_machine(self, machine):
        """
        Stop the specified machine.

        Args:
            machine: The machine. Can be a machine id or a :py:class:`~.dto.Machine`.

        Returns:
            The updated :py:class:`~.dto.Machine`.
        """
        raise errors.UnsupportedOperationError(
            "Operation not supported for provider '{}'".format(self.provider_name)
        )

    def restart_machine(self, machine):
        """
        Restart the specified machine.

        Args:
            machine: The machine. Can be a machine id or a :py:class:`~.dto.Machine`.

        Returns:
            The updated :py:class:`~.dto.Machine`.
        """
        raise errors.UnsupportedOperationError(
            "Operation not supported for provider '{}'".format(self.provider_name)
        )

    def delete_machine(self, machine):
        """
        Delete the specified machine.

        Args:
            machine: The machine. Can be a machine id or a :py:class:`~.dto.Machine`.

        Returns:
            The updated :py:class:`~.dto.Machine` if it has transitioned to a
            deleting status, or ``None`` if it has already been deleted.
        """
        raise errors.UnsupportedOperationError(
            "Operation not supported for provider '{}'".format(self.provider_name)
        )

    def external_ips(self):
        """
        Returns the external IP addresses that are currently allocated to the
        tenancy.

        Returns:
            An iterable of :py:class:`~.dto.ExternalIp`\ s.
        """
        raise errors.UnsupportedOperationError(
            "Operation not supported for provider '{}'".format(self.provider_name)
        )

    def find_external_ip(self, ip):
        """
        Finds external IP details by IP address.

        Returns:
            A :py:class:`~.dto.ExternalIp` object.
        """
        raise errors.UnsupportedOperationError(
            "Operation not supported for provider '{}'".format(self.provider_name)
        )

    def allocate_external_ip(self):
        """
        Allocates a new external IP address for the tenancy from a pool and returns
        it.

        Returns:
            The allocated :py:class:`~.dto.ExternalIp` (should raise on failure).
        """
        raise errors.UnsupportedOperationError(
            "Operation not supported for provider '{}'".format(self.provider_name)
        )

    def attach_external_ip(self, ip, machine):
        """
        Attaches an external IP to a machine.

        Args:
            ip: The IP address to attach. Can be an external IP address as a string
                or a :py:class:`~.dto.ExternalIp`.
            machine: The machine. Can be a machine id or a :py:class:`~.dto.Machine`.

        Returns:
            The updated :py:class:`~.dto.ExternalIp` object (should raise on failure).
        """
        raise errors.UnsupportedOperationError(
            "Operation not supported for provider '{}'".format(self.provider_name)
        )

    def detach_external_ip(self, ip):
        """
        Detaches the given external IP from whichever machine it is currently
        attached to.

        Args:
            ip: The IP address to detach. Can be an external IP address as a string
                or a :py:class:`~.dto.ExternalIp`.

        Returns:
            The updated :py:class:`~.dto.ExternalIp` object (should raise on failure).
        """
        raise errors.UnsupportedOperationError(
            "Operation not supported for provider '{}'".format(self.provider_name)
        )

    def volumes(self):
        """
        Lists the volumes currently available to the tenancy.

        Returns:
            An iterable of :py:class:`~.dto.Volume`\ s.
        """
        raise errors.UnsupportedOperationError(
            "Operation not supported for provider '{}'".format(self.provider_name)
        )

    def find_volume(self, id):
        """
        Finds a volume by id.

        Args:
            id: The id of the volume to find.

        Returns:
            A :py:class:`~.dto.Volume` object.
        """
        raise errors.UnsupportedOperationError(
            "Operation not supported for provider '{}'".format(self.provider_name)
        )

    def create_volume(self, name, size):
        """
        Create a new volume in the tenancy.

        Args:
            name: The name of the volume.
            size: The size of the volume in GB.

        Returns:
            A :py:class:`~.dto.Volume` object.
        """
        raise errors.UnsupportedOperationError(
            "Operation not supported for provider '{}'".format(self.provider_name)
        )

    def delete_volume(self, volume):
        """
        Delete the specified volume.

        Args:
            volume: The volume to delete. Can be a volume id or a :py:class:`~.dto.Volume`.

        Returns:
            The updated :py:class:`~.dto.Volume` if it has transitioned to a
            deleting status, or ``None`` if it has already been deleted.
        """
        raise errors.UnsupportedOperationError(
            "Operation not supported for provider '{}'".format(self.provider_name)
        )

    def attach_volume(self, volume, machine):
        """
        Attaches the specified volume to the specified machine.

        Args:
            volume: The volume to attach. Can be a volume id or a :py:class:`~.dto.Volume`.
            machine: The machine. Can be a machine id or a :py:class:`~.dto.Machine`.

        Returns:
            The updated :py:class:`~.dto.Volume`.
        """
        raise errors.UnsupportedOperationError(
            "Operation not supported for provider '{}'".format(self.provider_name)
        )

    def detach_volume(self, volume):
        """
        Detaches the specified volume from the machine it is attached to.

        Args:
            volume: The volume to detach. Can be a volume id or a :py:class:`~.dto.Volume`.

        Returns:
            The updated :py:class:`~.dto.Volume`.
        """
        raise errors.UnsupportedOperationError(
            "Operation not supported for provider '{}'".format(self.provider_name)
        )
