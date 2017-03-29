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
        raise errors.UnsupportedOperationError


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
        raise errors.UnsupportedOperationError

    def scoped_session(self, tenancy):
        """
        Get a scoped session for the given tenancy.

        Args:
            tenancy: The tenancy to get a scoped session for. Can be a tenancy id
                or a :py:class:`~.dto.Tenancy` object.

        Returns:
            A :py:class:`~ScopedSession` for the tenancy.
        """
        raise errors.UnsupportedOperationError


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
            A dictionary of :py:class:`~.dto.Quota` objects indexed by resource.
        """
        raise errors.UnsupportedOperationError

    def images(self):
        """
        Lists the images available to the tenancy.

        Returns:
            An iterable of :py:class:`~.dto.Image` objects.
        """
        raise errors.UnsupportedOperationError

    def find_image(self, id):
        """
        Finds an image by id.

        Args:
            id: The id of the image to find.

        Returns:
            An :py:class:`~.dto.Image` object.
        """
        raise errors.UnsupportedOperationError

    def sizes(self):
        """
        Lists the machine sizes available to the tenancy.

        Returns:
            An iterable of :py:class:`~.dto.Size` objects.
        """
        raise errors.UnsupportedOperationError

    def find_size(self, id):
        """
        Finds a size by id.

        Args:
            id: The id of the size to find.

        Returns:
            A :py:class:`~.dto.Size` object.
        """
        raise errors.UnsupportedOperationError

    def machines(self):
        """
        Lists the machines in the tenancy.

        Returns:
            An iterable of :py:class:`~.dto.Machine`s.
        """
        raise errors.UnsupportedOperationError

    def find_machine(self, id):
        """
        Finds a machine by id.

        Args:
            id: The id of the machine to find.

        Returns:
            A :py:class:`~.dto.Machine` object.
        """
        raise errors.UnsupportedOperationError

    def create_machine(self, name, image, size):
        """
        Create a new machine in the tenancy.

        Args:
            name: The name of the machine.
            image: The image to use. Can be an image id or a :py:class:`~.dto.Image`.
            size: The size to use. Can be a size id or a :py:class:`~.dto.Size`.

        Returns:
            The created machine as a :py:class:`~.dto.Machine`.
        """
        raise errors.UnsupportedOperationError

    def resize_machine(self, machine, size):
        """
        Change the size of a machine.

        Args:
            machine: The machine. Can be a machine id or a :py:class:`~.dto.Machine`.
            size: The size to use. Can be a size id or a :py:class:`~.dto.Size`.

        Returns:
            ``True`` on success (should raise on failure).
        """
        raise errors.UnsupportedOperationError

    def start_machine(self, machine):
        """
        Start the specified machine.

        Args:
            machine: The machine. Can be a machine id or a :py:class:`~.dto.Machine`.

        Returns:
            ``True`` on success (should raise on failure).
        """
        raise errors.UnsupportedOperationError

    def stop_machine(self, machine):
        """
        Stop the specified machine.

        Args:
            machine: The machine. Can be a machine id or a :py:class:`~.dto.Machine`.

        Returns:
            ``True`` on success (should raise on failure).
        """
        raise errors.UnsupportedOperationError

    def restart_machine(self, machine):
        """
        Restart the specified machine.

        Args:
            machine: The machine. Can be a machine id or a :py:class:`~.dto.Machine`.

        Returns:
            ``True`` on success (should raise on failure).
        """
        raise errors.UnsupportedOperationError

    def delete_machine(self, machine):
        """
        Delete the specified machine.

        Args:
            machine: The machine. Can be a machine id or a :py:class:`~.dto.Machine`.

        Returns:
            ``True`` on success (should raise on failure).
        """
        raise errors.UnsupportedOperationError

    def available_external_ips(self):
        """
        Returns an iterable of external IP addresses that are already allocated
        to the tenancy but *not* attached to a machine.

        Returns:
            An iterable of IP addresses.
        """
        raise errors.UnsupportedOperationError

    def allocate_external_ip(self, machine):
        """
        Allocates a new external IP address from a pool and attaches it to the
        machine (on platforms that support it).

        Args:
            machine: The machine. Can be a machine id or a :py:class:`~.dto.Machine`.

        Returns:
            ``True`` on success (should raise on failure).
        """
        raise errors.UnsupportedOperationError

    def attach_external_ip(self, machine, ip):
        """
        Attaches an external IP to a machine.

        ``ip`` should be one of the available IPs returned by :py:meth:`available_external_ips`.

        Args:
            machine: The machine. Can be a machine id or a :py:class:`~.dto.Machine`.
            ip: The IP address to attach.

        Returns:
            ``True`` on success (should raise on failure).
        """
        raise errors.UnsupportedOperationError

    def detach_external_ips(self, machine):
        """
        Detaches all the external IPs from the given machine.

        Args:
            machine: The machine. Can be a machine id or a :py:class:`~.dto.Machine`.

        Returns:
            ``True`` on success (should raise on failure).
        """
        raise errors.UnsupportedOperationError

    def attach_volume(self, machine, size):
        """
        Attaches an additional volume of the given size to the given machine.

        Args:
            machine: The machine. Can be a machine id or a :py:class:`~.dto.Machine`.
            size: The size of the volume to attach in GB.

        Returns:
            ``True`` on success (should raise on failure).
        """
        raise errors.UnsupportedOperationError

    def detach_volume(self, machine, volume):
        """
        Detaches the given volume from the machine and destroys it.

        Args:
            machine: The machine. Can be a machine id or a :py:class:`~.dto.Machine`.
            volume: The volume to detach. Can be a volume id or a :py:class:`~.dto.Volume`.

        Returns:
            ``True`` on success (should raise on failure).
        """
        raise errors.UnsupportedOperationError
