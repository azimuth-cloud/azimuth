"""
This module defines data-transfer objects used by providers.
"""

from dataclasses import dataclass
from datetime import datetime
import enum
import io
import json
import re
from typing import Any, Mapping, Optional, Sequence

import yaml
import requests


@dataclass(frozen = True)
class Tenancy:
    """
    Represents a tenancy/organisation on a cloud provider.
    """
    #: The ID of the tenancy
    id: str
    #: The human-readable name of the tenancy
    name: str


@dataclass(frozen = True)
class Quota:
    """
    Represents a quota available to a tenancy.
    """
    #: The resource that the quota is for
    resource: str
    #: The units of the quota. For a unit-less quota, use ``None``.
    units: Optional[str]
    #: The amount of the resource that has been allocated
    allocated: int
    #: The amount of the resource that has been used
    used: int


@dataclass(frozen = True)
class Image:
    """
    Represents an image available to a tenancy.

    Can be combined with a :py:class:`Size` to create a new :py:class:`Machine`.
    """
    #: The id of the image
    id: str
    #: The VM-type of the image
    #: When a machine is provisioned using the image, this is passed to the machine
    #: as metadata allowing it to configure itself if required
    vm_type: str
    #: The human-readable name of the image
    name: str
    #: Indicates if the image is public or private
    is_public: bool
    #: Indicates if NAT is allowed for machines deployed from the image
    nat_allowed: bool
    #: The size of the image in MB
    size: float


@dataclass(frozen = True)
class Size:
    """
    Represents a machine size available to a tenancy.

    A size is a specification of the number of virtaul CPUs and RAM available to
    a machine.

    Can be combined with an :py:class:`Image` to create a new :py:class:`Machine`.
    """
    #: The id of the size
    id: str
    #: The human-readable name of the size
    name: str
    #: The number of CPUs
    cpus: int
    #: The amount of RAM in MB
    ram: int
    #: The size of the image's disk in GB
    #: Can be -1 to indicate no root disk size limit
    disk: int


@enum.unique
class MachineStatusType(enum.Enum):
    """
    Enum representing the possible status types.
    """
    BUILD = 'BUILD'
    ACTIVE = 'ACTIVE'
    ERROR = 'ERROR'
    OTHER = 'OTHER'


@dataclass(frozen = True)
class MachineStatus:
    """
    Represents a machine status.
    """
    #: The type of the status
    type: MachineStatusType
    #: A short string representation of the status
    name: str
    #: A more details description of the status, e.g. an error
    details: Optional[str]


@dataclass(frozen = True)
class Machine:
    """
    Represents a machine in a tenancy.
    """
    #: The id of the machine
    id: str
    #: The human-readable name of the machine
    name: str
    #: The image used to deploy the machine
    image: Image
    #: The the size of the machine
    size: Size
    #: The status of the machine
    status: MachineStatus
    #: The power state of the machine
    power_state: str
    #: String representation of any task that is currently executing
    task: Optional[str]
    #: The internal IPv4 address of the machine
    internal_ip: Optional[str]
    #: The external IPv4 address of the machine
    external_ip: Optional[str]
    #: Indicates if NAT is allowed for the machine
    nat_allowed: bool
    #: Tuple of ids of attached volumes for the machine
    attached_volume_ids: Sequence[str]
    #: The id or username of the user who deployed the machine
    owner: str
    #: The datetime at which the machine was deployed
    created: datetime


@enum.unique
class VolumeStatus(enum.Enum):
    """
    Enum representing the possible volume statuses.
    """
    CREATING  = 'CREATING'
    AVAILABLE = 'AVAILABLE'
    ATTACHING = 'ATTACHING'
    DETACHING = 'DETACHING'
    IN_USE    = 'IN_USE'
    DELETING  = 'DELETING'
    ERROR     = 'ERROR'
    OTHER     = 'OTHER'


@dataclass(frozen = True)
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
    #: The id of the machine the volume is attached to, or None if the volume is not attached
    machine_id: Optional[str]
    #: The device that the volume is attached on, or None if the volume is not attached
    device: Optional[str]


@dataclass(frozen = True)
class ExternalIp:
    """
    Represents an externally visible IP address.
    """
    #: The id of the external IP
    id: str
    #: The externally visible IP address
    external_ip: str
    #: The ID of the machine to which the external IP address is mapped,
    #: or None if it is not mapped
    machine_id: Optional[str]


@dataclass(frozen = True)
class ClusterParameter:
    """
    Represents a parameter required by a cluster type.
    """
    #: The name of the parameter
    name: str
    #: A human-readable label for the parameter
    label: str
    #: A description of the parameter
    description: str
    #: The kind of the parameter
    kind: str
    #: A dictionary of kind-specific options for the parameter
    options: Mapping[str, Any]
    #: Indicates if the option is immutable, i.e. cannot be updated
    immutable: bool
    #: Indicates if the parameter is required
    required: bool
    #: A default value for the parameter
    default: Any


@dataclass(frozen = True)
class ClusterType:
    """
    Represents a cluster type.
    """
    #: The name of the cluster type
    name: str
    #: A human-readable label for the cluster type
    label: str
    #: A description of the cluster type
    description: str
    #: The URL or data URI of the logo for the cluster type
    logo: str
    #: A tuple of parameters for the cluster type
    parameters: Sequence[ClusterParameter]

    @classmethod
    def from_dict(cls, name, spec):
        """
        Returns a new cluster type from the given dictionary specification.

        Args:
            spec: The cluster type specification as a ``dict``.

        Returns:
            A :py:class:`ClusterType`.
        """
        return cls(
            name,
            spec.get('label', name),
            spec.get('description'),
            spec.get('logo'),
            tuple(
                ClusterParameter(
                    param['name'],
                    param.get('label', param['name']),
                    param.get('description'),
                    param['kind'],
                    param.get('options', {}),
                    param.get('immutable', False),
                    param.get('required', True),
                    param.get('default', None)
                )
                for param in spec.get('parameters', [])
            )
        )

    @classmethod
    def _open(cls, path):
        if re.match(r'https?://', path):
            response = requests.get(path)
            response.raise_for_status()
            return io.StringIO(response.text)
        else:
            return open(path)

    @classmethod
    def from_json(cls, name, path):
        """
        Returns a new cluster type from the given JSON file.

        Args:
            name: The name of the cluster type.
            path: Path to or URL of a JSON specification file.

        Returns:
            A :py:class:`ClusterType`.
        """
        with cls._open(path) as fh:
            return cls.from_dict(name, json.load(fh))

    @classmethod
    def from_yaml(cls, name, path):
        """
        Returns a new cluster type from the given YAML file.

        Args:
            name: The name of the cluster type.
            path: Path to or URL of a YAML specification file.

        Returns:
            A :py:class:`ClusterType`.
        """
        with cls._open(path) as fh:
            return cls.from_dict(name, yaml.safe_load(fh))


@enum.unique
class ClusterStatus(enum.Enum):
    """
    Enum for the possible cluster statuses.
    """
    CONFIGURING = 'CONFIGURING'
    READY = 'READY'
    DELETING = 'DELETING'
    ERROR = 'ERROR'


@dataclass(frozen = True)
class Cluster:
    """
    Represents a cluster.
    """
    #: The id of the cluster
    id: str
    #: The name of the cluster
    name: str
    #: The name of the cluster type of the cluster
    cluster_type: str
    #: The status of the cluster
    status: ClusterStatus
    #: Description of the currently executing task, or None if no task is executing
    task: Optional[str]
    #: Description of the error that occured, or None if there is no error
    error_message: Optional[str]
    #: Dictionary containing the current parameter values
    parameter_values: Mapping[str, Any]
    #: A tuple of tags describing the cluster
    tags: Sequence[str]
    #: The datetime at which the cluster was created
    created: datetime
    #: The datetime at which the cluster was updated
    updated: datetime
    #: The datetime at which the cluster was last patched
    patched: datetime
