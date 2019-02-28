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


class Image(namedtuple('Image', ['id', 'vm_type', 'name',
                                 'is_public', 'nat_allowed', 'size'])):
    """
    Represents an image available to a tenancy.

    Can be combined with a :py:class:`Size` to create a new :py:class:`Machine`.

    Attributes:
        id: The id of the image.
        vm_type: The VM-type of the image. When a machine is provisioned using
                 the image this is passed to the machine, allowing it to configure
                 itself appropriately.
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
        disk: The size of the image's disk (in GB).
              Can be -1 to indicate no root disk size limit.
    """


class Machine(namedtuple('Machine', ['id', 'name', 'image', 'size',
                                     'status', 'power_state', 'task',
                                     'internal_ip', 'external_ip', 'nat_allowed',
                                     'attached_volume_ids', 'owner', 'created'])):
    """
    Represents a machine in a tenancy.

    Attributes:
        id: The id of the machine.
        name: The human-readable name of the machine.
        image: The image used to deploy the machine.
        size: The the size of the machine.
        status: The :py:class:`Status` of the machine.
        power_state: The power state of the machine as a string.
        task: String representation of any task that is currently executing.
        internal_ip: The internal IPv4 address of the machine.
        external_ip: The external IPv4 address of the machine.
        nat_allowed: Indicates if NAT is allowed for the machine.
        attached_volume_ids: A tuple of ids of attached volumes for the machine.
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


class Volume(namedtuple('Volume', ['id', 'name', 'status',
                                   'size', 'machine_id', 'device'])):
    """
    Represents a volume attached to a machine.

    Attributes:
        id: The id of the volume.
        name: The name of the volume.
        status: The :py:class:`Status` of the volume.
        size: The size of the volume in GB.
        machine_id: The id of the machine the volume is attached to, or ``None``
                    if the volume is not attached.
        device: The device that the volume is attached on, or ``None`` if the
                volume is not attached.
    """
    @enum.unique
    class Status(enum.Enum):
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


class ExternalIp(namedtuple('ExternalIp', ['external_ip', 'machine_id'])):
    """
    Represents an externally visible IP address.

    Attributes:
        external_ip: The externally visible IP address.
        machine_id: The ID of the machine to which the external IP address is
                    mapped, or ``None`` if it is not mapped.
    """


class ClusterType(namedtuple('ClusterType', ['name',
                                             'label',
                                             'description',
                                             'parameters'])):
    """
    Represents a cluster type.

    Attributes:
        name: The name of the cluster type.
        label: A human-readable label for the cluster type.
        description: A description of the cluster type.
        parameters: A tuple of :py:class:`Parameter`s for the cluster type.
    """
    class Parameter(namedtuple('Parameter', ['name', 'label', 'description',
                                             'kind', 'options',
                                             'immutable',
                                             'required',
                                             'default'])):
        """
        Represents a parameter required by a cluster type.

        Attributes:
            name: The name of the parameter.
            label: A human-readable label for the parameter.
            description: A description of the parameter.
            kind: The kind of the parameter.
            options: A dictionary of kind-specific options for the parameter.
            immutable: Indicates if the option is immutable, i.e. cannot be
                       updated.
            required: Indicates if the parameter is required.
            default: A default value for the parameter.
        """

    @classmethod
    def from_dict(cls, cluster_type_spec):
        """
        Returns a new cluster type from the given dictionary specification.

        Args:
            cluster_type_spec: The cluster type specification as a ``dict``.

        Returns:
            A :py:class:`ClusterType`.
        """
        return cls(
            cluster_type_spec['name'],
            cluster_type_spec.get('label', cluster_type_spec['name']),
            cluster_type_spec.get('description'),
            tuple(
                cls.Parameter(
                    param['name'],
                    param.get('label', param['name']),
                    param.get('description'),
                    param['kind'],
                    param.get('options', {}),
                    param.get('immutable', False),
                    param.get('required', True),
                    param.get('default', None)
                )
                for param in cluster_type_spec.get('parameters', [])
            )
        )

    @classmethod
    def from_json(cls, path):
        """
        Returns a new cluster type from the given JSON file.

        Args:
            path: Path to a JSON file.

        Returns:
            A :py:class:`ClusterType`.
        """
        import json
        with open(path) as fh:
            return cls.from_dict(json.load(fh))

    @classmethod
    def from_yaml(cls, path):
        """
        Returns a new cluster type from the given YAML file.

        Args:
            path: Path to a YAML file.

        Returns:
            A :py:class:`ClusterType`.
        """
        import yaml
        with open(path) as fh:
            return cls.from_dict(yaml.safe_load(fh))


class Cluster(namedtuple('Cluster', ['id', 'name', 'cluster_type',
                                     'status', 'parameter_values',
                                     'created', 'updated', 'patched'])):
    """
    Represents a cluster.

    Attributes:
        id: The id of the cluster.
        name: The name of the cluster.
        cluster_type: The name of the :py:class:`ClusterType` of the cluster.
        status: The :py:class:`Status` of the cluster.
        parameter_values: Dictionary containing the current parameter values.
        created: The `datetime` at which the cluster was created.
        updated: The `datetime` at which the cluster was updated.
        patched: The `datetime` at which the cluster was last patched.
    """
    @enum.unique
    class Status(enum.Enum):
        """
        Enum for the possible cluster statuses.
        """
        CONFIGURING = 'CONFIGURING'
        READY = 'READY'
        DELETING = 'DELETING'
        ERROR = 'ERROR'
