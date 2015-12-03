"""
This module defines the exceptions that can be raised by cloud operations.

A lot of the time, errors will be raised with a :py:class:`ProviderSpecificError`
as the cause, i.e. using the ``raise ... from ...`` syntax.
"""

__author__ = "Matt Pryor"
__copyright__ = "Copyright 2015 UK Science and Technology Facilities Council"


class CloudServiceError(RuntimeError):
    """Base class for all errors raised by cloud services."""
    
class ProviderConnectionError(CloudServiceError):
    """Raised if a provider cannot be connected to."""
    
class ProviderUnavailableError(CloudServiceError):
    """Raised when a provider connects but reports an error."""
    
class ProviderSpecificError(CloudServiceError):
    """Base class for provider specific errors."""
    
class ImplementationError(CloudServiceError):
    """Raised when an error occurs in the implementation or the implementation
       issues a bad request."""
    
class AuthenticationError(CloudServiceError):
    """Raised when authentication with a provider fails."""
    
class PermissionsError(CloudServiceError):
    """Raised when a session has insufficient permissions to perform an action."""
    
class NoSuchResourceError(CloudServiceError):
    """Raised when a resource is requested that does not exist."""
    
class BadRequestError(CloudServiceError):
    """Raised when a badly formatted request is made to the cloud service."""
    
class BadConfigurationError(CloudServiceError):
    """Raised when the cloud service is configured in a way that the portal cannot use."""
    
class DuplicateNameError(CloudServiceError):
    """Raised when a name conflicts with a resource that already exists."""
    
class InvalidActionError(CloudServiceError):
    """Raised when an action is invalid given the current state of an entity."""
    
class ImageCreateError(CloudServiceError):
    """Raised when an error occurs while creating a new image."""
    
class ImageDeleteError(CloudServiceError):
    """Raised when an error occurs while deleting an image."""
    
class ProvisioningError(CloudServiceError):
    """Raised when an error occurs during provisioning."""
    
class NetworkingError(CloudServiceError):
    """Raised when an error occurs while performing a networking operation."""
    
class PowerActionError(CloudServiceError):
    """Raised when an error occurs while performing a power action on a VM."""
    
class ResourceAllocationError(CloudServiceError):
    """Raised when an error occurs while allocating resources to a VM"""
    
class TaskFailedError(CloudServiceError):
    """Raised when a long running task fails."""
    
class TaskCancelledError(TaskFailedError):
    """Raised when a task fails due to being cancelled by a user."""
    
class TaskAbortedError(TaskFailedError):
    """Raised when a task fails due to being aborted by an administrator."""
    