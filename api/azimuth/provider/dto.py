"""
This module defines data-transfer objects used by providers.
"""

import enum
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Capabilities:
    """
    Represents the capabilities of the cloud.
    """

    #: Indicates if the cloud supports volumes
    supports_volumes: bool = False

    #: Indicates if machines are enabled for the cloud
    supports_machines: bool = True

    #: Indicates if kubernetes is enabled for the cloud
    supports_kubernetes: bool = True

    #: Indicates if kubernetes apps are enabled for the cloud
    supports_apps: bool = True


@dataclass(frozen=True)
class Tenancy:
    """
    Represents a tenancy/organisation on a cloud provider.
    """

    #: The ID of the tenancy
    id: str
    #: The human-readable name of the tenancy
    name: str


@dataclass(frozen=True)
class Credential:
    """
    Represents a credential for interacting with a cloud.
    """

    #: The credential type
    type: str
    #: The credential data
    data: dict


@dataclass(frozen=True)
class Quota:
    """
    Represents a quota available to a tenancy.
    """

    #: The resource that the quota is for
    resource: str
    #: The human-readable label for the quota
    label: str
    #: The units of the quota. For a unit-less quota, use ``None``.
    units: str | None
    #: The amount of the resource that has been allocated
    allocated: int
    #: The amount of the resource that has been used
    used: int
    #: Indicates if this is a quota for Coral credits, as opposed to
    #: an Openstack resource
    is_coral_quota: bool = False


@dataclass(frozen=True)
class Image:
    """
    Represents an image available to a tenancy.

    Can be combined with a :py:class:`Size` to create a new :py:class:`Machine`.
    """

    #: The id of the image
    id: str
    #: The human-readable name of the image
    name: str
    #: Indicates if the image is public or private
    is_public: bool
    #: The size of the image in MB
    size: float
    #: The metadata associated with the image
    metadata: Mapping[str, str]


@dataclass(frozen=True)
class Size:
    """
    Represents a machine size available to a tenancy.

    A size is a specification of the number of virtual CPUs and RAM available to
    a machine.

    Can be combined with an :py:class:`Image` to create a new :py:class:`Machine`.
    """

    #: The id of the size
    id: str
    #: The human-readable name of the size
    name: str
    #: The description of the size
    description: str | None
    #: The number of CPUs
    cpus: int
    #: The amount of RAM in MB
    ram: int
    #: The size of the root disk in GB
    disk: int
    #: The size of the ephemeral disk in GB
    ephemeral_disk: int
    #: Any additional properties of the size
    additional_properties: Mapping[str, str]
    #: The sort index of the size in the UI
    sort_idx: int = 0


@enum.unique
class MachineStatusType(enum.Enum):
    """
    Enum representing the possible status types.
    """

    BUILD = "BUILD"
    ACTIVE = "ACTIVE"
    ERROR = "ERROR"
    OTHER = "OTHER"


@dataclass(frozen=True)
class MachineStatus:
    """
    Represents a machine status.
    """

    #: The type of the status
    type: MachineStatusType
    #: A short string representation of the status
    name: str
    #: A more details description of the status, e.g. an error
    details: str | None


@dataclass(frozen=True)
class Machine:
    """
    Represents a machine in a tenancy.
    """

    #: The id of the machine
    id: str
    #: The human-readable name of the machine
    name: str
    #: The ID of the image used to deploy the machine
    image_id: str
    #: The ID of the size of the machine
    size_id: str
    #: The status of the machine
    status: MachineStatus
    #: The power state of the machine
    power_state: str
    #: String representation of any task that is currently executing
    task: str | None
    #: The internal IPv4 address of the machine
    internal_ip: str | None
    #: The external IPv4 address of the machine
    external_ip: str | None
    #: Tuple of ids of attached volumes for the machine
    attached_volume_ids: Sequence[str]
    #: The metadata associated with the machine
    metadata: Mapping[str, str]
    #: The id or username of the user who deployed the machine
    owner: str
    #: The datetime at which the machine was deployed
    created: datetime


class FirewallRuleDirection(enum.Enum):
    """
    Enum representing the possible directions for a firewall rule.
    """

    INBOUND = "INBOUND"
    OUTBOUND = "OUTBOUND"
    # Add ingress and egress as aliases for inbound and outbound
    INGRESS = "INBOUND"
    EGRESS = "OUTBOUND"


@enum.unique
class FirewallRuleProtocol(enum.Enum):
    """
    Enum representing the possible protocols for a firewall rule.
    """

    ANY = "ANY"
    ICMP = "ICMP"
    UDP = "UDP"
    TCP = "TCP"

    def requires_port(self):
        """
        Indicates if the protocol requires a port or not.
        """
        return self in {self.__class__.UDP, self.__class__.TCP}


@dataclass(frozen=True)
class FirewallRule:
    """
    Represents a firewall rule applying to a host.
    """

    #: The id of the firewall rule
    id: str
    #: The direction for the firewall rule
    direction: FirewallRuleDirection
    #: The protocol for the firewall rule
    protocol: FirewallRuleProtocol
    #: The port range matched by the firewall rule, if applicable
    port_range: tuple[int, int] | None = None
    #: The remote CIDR matched by the firewall rule, if applicable
    remote_cidr: str | None = None
    #: The name of the remote firewall group matched by the firewall rule, if applicable
    remote_group: str | None = None


@dataclass(frozen=True)
class FirewallGroup:
    """
    Represents a group in the firewall.

    This means a group in two senses - a set of rules and a set of hosts that
    have the group applied.
    """

    #: The name of the firewall group
    name: str
    #: The rules for the firewall group
    rules: Sequence[FirewallRule]
    #: Indicates if the rules in the group are editable
    #: Generally, this will only be the case for the instance-level rules
    editable: bool = False


@enum.unique
class VolumeStatus(enum.Enum):
    """
    Enum representing the possible volume statuses.
    """

    CREATING = "CREATING"
    AVAILABLE = "AVAILABLE"
    ATTACHING = "ATTACHING"
    DETACHING = "DETACHING"
    IN_USE = "IN_USE"
    DELETING = "DELETING"
    ERROR = "ERROR"
    OTHER = "OTHER"


@dataclass(frozen=True)
class Volume:
    """
    Represents a volume attached to a machine.
    """

    #: The id of the volume
    id: str
    #: The name of the volume
    name: str
    #: The status of the volume
    status: VolumeStatus
    #: The size of the volume in GB
    size: int
    #: The id of the machine the volume is attached to, or None if the volume is not
    #: attached
    machine_id: str | None
    #: The device that the volume is attached on, or None if the volume is not attached
    device: str | None


@dataclass(frozen=True)
class ExternalIp:
    """
    Represents an externally visible IP address.
    """

    #: The id of the external IP
    id: str
    #: The externally visible IP address
    external_ip: str
    #: Indicates if the floating IP is available
    available: bool
    #: The ID of the machine to which the external IP address is mapped,
    #: or None if it is not mapped
    machine_id: str | None
