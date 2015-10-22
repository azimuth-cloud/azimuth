"""
This module contains interfaces that define the operations that the JASMIN portal
requires from cloud services that it connects to, e.g. creating and power-cycling
VMs.

These interfaces should be implemented for each available provider.
"""

__author__ = "Matt Pryor"
__copyright__ = "Copyright 2015 UK Science and Technology Facilities Council"


import abc, enum
from collections import namedtuple

from .exceptions import *


@enum.unique
class MachineStatus(enum.Enum):
    """
    Defines the states that a machine may be in.
    """
    
    """Machine is known to be in an inconsistent state."""
    INCONSISTENT = 'Inconsistent'
    
    """Provisioning of the machine failed."""
    PROVISIONING_FAILED = 'Provisioning Failed'
    
    """Machine is in an unspecified error state."""
    ERROR = 'Error'
    
    """Machine is in the process of being provisioned."""
    PROVISIONING = 'Provisioning...'
    
    """Machine is powered on."""
    POWERED_ON = 'Powered On'
    
    """Machine is waiting for user input."""
    WAITING_FOR_INPUT = 'Waiting for input...'
    
    """Machine is powered off."""
    POWERED_OFF = 'Powered Off'
    
    """Machine is suspended."""
    SUSPENDED = 'Suspended'

    """Machine is in an unknown state."""
    UNKNOWN = 'Unknown'
    
    """Machine is in an unrecognised state."""
    UNRECOGNISED = 'Unrecognised'
    
    def is_on(self):
        """
        Indicates if this status represents a powered on machine.
        
        :returns: True or False
        """
        return self is MachineStatus.POWERED_ON
    
    def is_warning(self):
        """
        Indicates if this status represents a warning that something might be wrong.
        
        :returns: True or False
        """
        return self in [MachineStatus.WAITING_FOR_INPUT,
                        MachineStatus.UNKNOWN,
                        MachineStatus.UNRECOGNISED]
    
    def is_error(self):
        """
        Indicates if this status represents an error.
        
        :returns: True or False
        """
        return self in [MachineStatus.INCONSISTENT,
                        MachineStatus.PROVISIONING_FAILED,
                        MachineStatus.ERROR]


class Image(namedtuple('ImageProps', ['id', 'name', 'description', 'is_public'])):
    """
    Represents an image that can be used to provision a machine.
    
    .. py:attribute:: id
    
        The id of the image.
        
    .. py:attribute:: name
    
        The name of the image.
        
    .. py:attribute:: description
    
        An extended description of the image. This could contain rich formatting.
        
    .. py:attribute:: is_public
    
        Indicates if the image is public or private.
    """


class Machine(namedtuple('MachineProps', ['id', 'name', 'status',
                                          'description', 'created', 'os',
                                          'internal_ip', 'external_ip'])):
    """
    Represents a virtual machine.
    
    .. py:attribute:: id
    
        The id of the virtual machine.
        
    .. py:attribute:: name
    
        The name of the virtual machine.
        
    .. py:attribute:: status
    
        A :py:class:`MachineStatus` object representing the current status of the
        virtual machine. 
        
    .. py:attribute:: description
    
        An extended description of the virtual machine. This could contain rich
        formatting.
    
    .. py:attribute:: created
    
        A ``datetime.datetime`` indicating the time that the virtual machine was
        provisioned.
    
    .. py:attribute:: os
    
        The name of the operating system running on the virtual machine.
    
    .. py:attribute:: internal_ip
    
        An ``ipaddress.IPv4Address`` indicating the IP of the virtual machine on
        the internal network, or ``None`` if the machine is not connected to the
        network.
    
    .. py:attribute:: external_ip
    
        An ``ipaddress.IPv4Address`` indicating the IP of the virtual machine, as
        visible to the outside world, or ``None`` if the machine is not exposed
        to the outside world.
    """

    
class Provider(metaclass = abc.ABCMeta):
    """
    Abstract base for a cloud service provider. 
    """
    
    @abc.abstractmethod
    def new_session(self, username, password):
        """
        Create a new session for the provider using the given credentials.
        
        :param username: The cloud service username
        :param password: The cloud service password
        :returns: The authenticated cloud session
        """
        

class Session(metaclass = abc.ABCMeta):
    """
    Abstract base class for an authenticated session with a cloud provider,
    providing functionality required by the JASMIN portal.
    
    Session implementations **must** be serialisable using ``pickle``.
    
    Sessions can also be used as context managers, e.g.:
    
    ::
    
        p = VCloudProvider("https://vcloud.myexample.com/api")
        with p.new_session("user@org", "pass") as s:
            m = s.provision_machine(...)
            s.start_machine(m.id)
    """
    
    def __enter__(self):
        """
        Context manager entry point - just returns self
        """
        return self
    
    def __exit__(self, exc_type, exc_value, traceback):
        """
        Context manager exit point - just calls close and lets exceptions propagate
        """
        self.close()
        
    def __del__(self):
        """
        Destructor - called when the object is about to be destroyed.
        
        Just calls ``close`` to ensure that the session has been closed.
        """
        self.close()
        
    @abc.abstractmethod
    def poll(self):
        """
        Tests whether the session is authenticated and active.
        
        :returns: True on success
        """
    
    @abc.abstractmethod
    def list_images(self):
        """
        Get the images available to this session.
        
        :returns: A list of ``Image`` objects
        """
        
    @abc.abstractmethod
    def get_image(self, image_id):
        """
        Get image details for an id.
        
        :param image_id: The id of the image
        :returns: An ``Image`` or ``None``
        """
        
    @abc.abstractmethod
    def image_from_machine(self, machine_id, name, description):
        """
        Creates a redeployable image using the given machine as a template.
        
        :param machine_id: The id of the machine to use as a template
        :param name: The name of the new image
        :param description: An extended description for the new image
        :returns: The new ``Image``
        """
        
    @abc.abstractmethod
    def delete_image(self, image_id):
        """
        Deletes the image with the given id.
        
        :param image_id: The id of the image to delete
        :returns: True on success (raises on failure)
        """
        
    @abc.abstractmethod
    def count_machines(self):
        """
        Get the number of machines available to this session.
        
        :returns: The number of machines
        """
        
    @abc.abstractmethod
    def list_machines(self):
        """
        Get the machines available to this session.
        
        :returns: A list of ``Machine`` objects
        """
        
    @abc.abstractmethod
    def get_machine(self, machine_id):
        """
        Gets machine details for an id.
        
        :param machine_id: The id of the machine
        :returns: A ``Machine`` or ``None``
        """
        
    @abc.abstractmethod
    def provision_machine(self, image_id, name, description, ssh_key):
        """
        Provisions a new machine using the specified image and returns it.
        
        Root (or admin) access will be granted to the holder of the private key
        corresponding to the given SSH public key.
        
        :param image_id: The id of the image to use
        :param name: The name for the provisioned machine
        :param description: An extended description of the machine
        :param ssh_key: The SSH public key for root access
        :returns: A ``Machine`` for the provisioned machine
        """
        
    @abc.abstractmethod
    def expose_machine(self, machine_id):
        """
        Sets NAT and firewall rules as appropriate to expose the virtual machine
        externally for all protocols with a specific IP address.
        
        Returns the machine on success.
        
        :param machine_id: The id of the machine to expose
        :returns: The updated ``Machine``
        """
        
    @abc.abstractmethod
    def unexpose_machine(self, machine_id):
        """
        Removes all NAT and firewall rules associated specifically with the 
        virtual machine.
        
        Returns the machine on success.
        
        :param machine_id: The id of the machine to unexpose
        :returns: The updated ``Machine``
        """
        
    @abc.abstractmethod
    def start_machine(self, machine_id):
        """
        Powers up the specified virtual machine.
        
        :param machine_id: The id of the machine to power up
        """
        
    @abc.abstractmethod
    def stop_machine(self, machine_id):
        """
        Stops the specified virtual machine.
        
        :param machine_id: The id of the machine to power down
        """
        
    @abc.abstractmethod
    def restart_machine(self, machine_id):
        """
        Power cycles the specified virtual machine.
        
        :param machine_id: The id of the machine to restart
        """
        
    @abc.abstractmethod
    def destroy_machine(self, machine_id):
        """
        Completely powers down the specified virtual machine and ensures all
        resources associated with the machine are freed.
        
        :param machine_id: The id of the machine to destroy
        """
        
    @abc.abstractmethod
    def delete_machine(self, machine_id):
        """
        Deletes the specified virtual machine completely.
        
        :param machine_id: The id of the machine to delete
        """
        
    @abc.abstractmethod
    def close(self):
        """
        Closes the session and frees any resources.
        
        Should avoid throwing any exceptions, and just do the best it can.
        """
    