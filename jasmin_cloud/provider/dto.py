"""
This module defines data-transfer objects used by providers.
"""

import enum
from collections import namedtuple

# WARNING: wrapt must be installed as pure-Python - not as a C extension
# This means that "export WRAPT_EXTENSIONS=false" must be run before pip-installing
import wrapt


class Proxy(wrapt.ObjectProxy):
    """
    Proxy object that is initialised lazily by calling the given thunk with no
    arguments.

    .. warning::

        This class requires ``wrapt`` to be installed as pure-Python, i.e.
        **without** C extensions.

        To do this, run ``export WRAPT_EXTENSIONS=false`` before installing with
        ``pip`` or running ``setup.py``.

    Args:
        thunk: The thunk that produces the proxied object.
        **known_attributes: If some attibutes of the object are already known,
            they can be given as keyword arguments and will not trigger the thunk.
    """
    def __init__(self, thunk, **known_attributes):
        # wrapt treats attributes starting with _self_ specially
        self._self_thunk = thunk
        self._self_known_attributes = known_attributes

    def __getattr__(self, name):
        # If wrapt is compiled with C extensions, this method is not called for
        # the __wrapped__ attribute (not sure why...!)
        # Initialise __wrapped__ the first time it is asked for
        if name == '__wrapped__':
            self.__wrapped__ = self._self_thunk()
            self._self_thunk = None
            return self.__wrapped__
        # If the thunk has not been triggered yet, try the known attributes first
        if self._self_thunk is not None and name in self._self_known_attributes:
            return self._self_known_attributes[name]
        # Otherwise, trigger the thunk
        return super().__getattr__(name)

    @property
    def __class__(self):
        if '__class__' in self._self_known_attributes:
            return self._self_known_attributes['__class__']
        return self.__wrapped__.__class__


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


class Image(namedtuple('Image', ['id', 'name', 'is_public', 'nat_allowed'])):
    """
    Represents an image available to a tenancy.

    Can be combined with a :py:class:`Size` to create a new :py:class:`Machine`.

    Attributes:
        id: The id of the image.
        name: The human-readable name of the image.
        is_public: Indicates if the image is public or private.
        nat_allowed: Indicates if NAT is allowed for machines deployed from the image.
    """


class Size(namedtuple('Size', ['id', 'name', 'cpus', 'ram'])):
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
    """


class Machine(namedtuple('Machine', ['id', 'name', 'image', 'size',
                                     'status', 'power_state', 'task',
                                     'internal_ips', 'external_ips', 'nat_allowed',
                                     'attached_volumes', 'owner', 'created'])):
    """
    Represents a machine in a tenancy.

    Attributes:
        id: The id of the machine.
        name: The human-readable name of the machine.
        image: The :py:class:`Image` used to deploy the machine.
        size: The :py:class:`Size` size of the machine.
        status: The status of the machine as a string.
        power_state: The power state of the machine as a string.
        task: String representation of any task that is currently executing.
        internal_ips: The internal IPv4 addresses of this machine.
        external_ips: The external IPv4 addresses of this machine.
        nat_allowed: Indicates if NAT is allowed for this machine.
        attached_volumes: A tuple of :py:class:`Volume`s attached to this machine.
        owner: The username of the user who deployed the machine.
        created: The `datetime` at which the machine was deployed.
    """


class Volume(namedtuple('Volume', ['id', 'machine', 'name', 'size', 'device'])):
    """
    Represents a volume attached to a machine.

    Attributes:
        id: The id of the volume.
        machine: The :py:class:`~.dto.Machine` that the volume is attached to.
        name: The name of the volume.
        size: The size of the volume in GB.
        device: The device that the volume is attached as.
    """


class ExternalIp(namedtuple('ExternalIp', ['external_ip', 'internal_ip'])):
    """
    Represents an externally visible IP address.

    Attributes:
        external_ip: The externally visible IP address.
        internal_ip: The internally visible IP address to which it maps, or
                     ``None`` if it is not mapped.
    """
