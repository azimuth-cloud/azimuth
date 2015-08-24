"""
This module defines an interface for defining access to cloud services required by
the portal, e.g. creating and power-cycling VMs
"""

__author__ = "Matt Pryor"
__copyright__ = "Copyright 2015 UK Science and Technology Facilities Council"


import abc, enum
from collections import namedtuple


class CloudServiceError(RuntimeError):
    """Base class for errors thrown by cloud services"""
    
class ProviderConnectionError(CloudServiceError):
    """Thrown if a provider cannot be connected to"""
    
class ProviderUnavailableError(CloudServiceError):
    """Thrown when a provider connects but reports an error"""
    
class ImplementationError(CloudServiceError):
    """Thrown when an error occurs in the implementation or the implementation
       issues a bad request"""
    
class AuthenticationError(CloudServiceError):
    """Thrown when authentication with a provider fails"""
    
class PermissionsError(CloudServiceError):
    """Thrown when a session has insufficient permissions to perform an action"""
    
class NoSuchResourceError(CloudServiceError):
    """Thrown when a resource is requested that does not exist"""
    
class BadRequestError(CloudServiceError):
    """Thrown when a badly formatted request is made to the cloud service"""
    
class DuplicateNameError(CloudServiceError):
    """Thrown when a name conflicts with a resource that already exists"""
    
class InvalidActionError(CloudServiceError):
    """Thrown when an action is invalid given the current state of an entity"""
    
class ProvisioningError(CloudServiceError):
    """Thrown when an error occurs during provisioning"""
    
class NetworkingError(CloudServiceError):
    """Thrown when an error occurs while performing a networking operation"""
    
class PowerActionError(CloudServiceError):
    """Thrown when an error occurs while performing a power action on a VM"""


###############################################################################
###############################################################################


class Provider(metaclass = abc.ABCMeta):
    """
    Class representing a cloud services provider 
    """
    @abc.abstractmethod
    def new_session(self, username, password):
        """
        Create a new session for the provider using the given credentials
        """
        

###############################################################################
###############################################################################


@enum.unique
class MachineStatus(enum.Enum):
    """
    Defines the states that a machine may be in
    """
    # Machine is known to be in an inconsistent state
    INCONSISTENT        = 'Inconsistent'
    # Provisioning of the machine failed
    PROVISIONING_FAILED = 'Provisioning Failed'
    # Machine is in some other unusable state
    ERROR               = 'Error'
    # Machine is in the process of being provisioned
    PROVISIONING        = 'Provisioning...'
    # Machine is on
    POWERED_ON          = 'Powered On'
    # Machine is waiting for user input
    WAITING_FOR_INPUT   = 'Waiting for input...'
    # Machine is off
    POWERED_OFF         = 'Powered Off'
    # Machine is suspended
    SUSPENDED           = 'Suspended'
    # We don't know the machine's status
    UNKNOWN             = 'Unknown'
    # Machine reported a state, but we don't recognise it
    UNRECOGNISED        = 'Unrecognised'
    
    def is_on(self):
        return self is MachineStatus.POWERED_ON
    
    def is_warning(self):
        return self in [MachineStatus.WAITING_FOR_INPUT,
                        MachineStatus.UNKNOWN,
                        MachineStatus.UNRECOGNISED]
    
    def is_error(self):
        return self in [MachineStatus.INCONSISTENT,
                        MachineStatus.PROVISIONING_FAILED,
                        MachineStatus.ERROR]

# Value objects for entities that can be returned by a session
Image = namedtuple('Image', ['id', 'name', 'description'])
Machine = namedtuple('Machine',  ['id', 'name', 'status', 'description',
                                  'created', 'os', 'internal_ip', 'external_ip'])

    
class Session(metaclass = abc.ABCMeta):
    """
    Class representing a session with a cloud provider, providing functionality
    
    Sessions should be picklable
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
        
    @abc.abstractmethod
    def is_active(self):
        """
        Checks if the session is still active
        """
    
    @abc.abstractmethod
    def list_images(self):
        """
        Returns a list of images available to the current session
        """
        
    @abc.abstractmethod
    def list_machines(self):
        """
        Returns a list of the machine available to the current session
        """
        
    @abc.abstractmethod
    def get_image(self, image_id):
        """
        Gets image details for an id, or None if the image doesn't exist
        """
        
    @abc.abstractmethod
    def get_machine(self, machine_id):
        """
        Gets machine details for an id, or None if the machine doesn't exist
        """
        
    @abc.abstractmethod
    def provision_machine(self, image_id, name, description, ssh_key):
        """
        Provisions an instance of the specified image with the given name and
        description
        
        The given ssh public key will be granted root access
        
        Returns the provisioned machine on success
        """
        
    @abc.abstractmethod
    def expose(self, machine_id):
        """
        Sets NAT and firewall rules as appropriate to expose the machine
        externally for all protocols with a specific IP
        
        Returns the machine on success
        """
        
    @abc.abstractmethod
    def unexpose(self, machine_id):
        """
        Removes all NAT and firewall rules associated specifically with the machine
        
        Returns the machine on success
        """
        
    @abc.abstractmethod
    def start_machine(self, machine_id):
        """
        Powers up the specified machine
        """
        
    @abc.abstractmethod
    def stop_machine(self, machine_id):
        """
        Stops the specified machine
        """
        
    @abc.abstractmethod
    def restart_machine(self, machine_id):
        """
        Power cycles the specified machine
        """
        
    @abc.abstractmethod
    def destroy_machine(self, machine_id):
        """
        Completely powers down the specified machine and ensures all resources
        associated with the machine are freed
        """
        
    @abc.abstractmethod
    def delete_machine(self, machine_id):
        """
        Deletes the specified machine completely
        """
        
    @abc.abstractmethod
    def close(self):
        """
        Closes the session
        """
    