"""
This module defines data-transfer objects used by providers.
"""

import enum
from collections import namedtuple


class Tenancy(namedtuple('Tenancy', ['id', 'name'])):
    """
    Represents a tenancy/organisation on a cloud provider.

    Attributes:
        id: The id of the tenancy.
        name: The human-readable name of the tenancy.
    """


class Quota(namedtuple('Quota', ['resource', 'units', 'allocated', 'used'])):
    """
    Represents a quota available to a tenancy.

    Attributes:
        resource: The resource that the quota is for.
        units: The units of the quota. For a unit-less quota, use ``None``.
        allocated: The amount of the resource that has been allocated.
        used: The amount of the resource that has been used.
    """


class Image(namedtuple('Image', ['id', 'name', 'is_public', 'nat_allowed', 'size'])):
    """
    Represents an image available to a tenancy.

    Can be combined with a :py:class:`Size` to create a new :py:class:`Machine`.

    Attributes:
        id: The id of the image.
        name: The human-readable name of the image.
        is_public: Indicates if the image is public or private.
        nat_allowed: Indicates if NAT is allowed for machines deployed from the image.
        size: The size of the image (in MB). Can be a float for more precision.
    """


class Size(namedtuple('Size', ['id', 'name', 'cpus', 'ram', 'disk'])):
    """
    Represents a machine size available to a tenancy.

    A size is a specification of the number of virtaul CPUs and RAM available to
    a machine.

    Can be combined with an :py:class:`Image` to create a new :py:class:`Machine`.

    Attributes:
        id: The id of the size.
        name: The human-readable name of the size.
        cpus: The number of CPUs.
        ram: The amount of RAM (in MB).
        disk: The size of the root disk (in GB).
              Can be -1 to indicate no root disk size limit.
    """


class Machine(namedtuple('Machine', ['id', 'name', 'image', 'size',
                                     'status', 'power_state', 'task',
                                     'internal_ip', 'external_ip', 'nat_allowed',
                                     'attached_volumes', 'owner', 'created'])):
    """
    Represents a machine in a tenancy.

    Attributes:
        id: The id of the machine.
        name: The human-readable name of the machine.
        image: The :py:class:`Image` used to deploy the machine.
        size: The :py:class:`Size` size of the machine.
        status: The :py:class:`Status` of the machine.
        power_state: The power state of the machine as a string.
        task: String representation of any task that is currently executing.
        internal_ip: The internal IPv4 address of the machine.
        external_ip: The external IPv4 address of the machine.
        nat_allowed: Indicates if NAT is allowed for the machine.
        attached_volumes: A tuple of :py:class:`Volume`s attached to the machine.
        owner: The username of the user who deployed the machine.
        created: The `datetime` at which the machine was deployed.
    """
    class Status(namedtuple('Status', ['type', 'name', 'details'])):
        """
        Represents a machine status.

        Attributes:
            type: The :py:class:`Type` of the status.
            name: A short string representation of the status.
            details: A string representing any details of the status, e.g. an error.
        """
        @enum.unique
        class Type(enum.Enum):
            """
            Enum representing the possible status types.
            """
            BUILD = 'BUILD'
            ACTIVE = 'ACTIVE'
            ERROR = 'ERROR'
            OTHER = 'OTHER'


class Volume(namedtuple('Volume', ['id', 'machine_id', 'name', 'size', 'device'])):
    """
    Represents a volume attached to a machine.

    Attributes:
        id: The id of the volume.
        machine_id: The id of the machine that the volume is attached to.
        name: The name of the volume.
        size: The size of the volume in GB.
        device: The device that the volume is attached as.
    """


class ExternalIp(namedtuple('ExternalIp', ['external_ip', 'machine_id'])):
    """
    Represents an externally visible IP address.

    Attributes:
        external_ip: The externally visible IP address.
        machine_id: The ID of the machine to which the external IP address is
                    mapped, or ``None`` if it is not mapped.
    """
