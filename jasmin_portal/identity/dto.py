"""
This module provides data transfer objects returned by the identity module.
"""

__author__ = "Matt Pryor"
__copyright__ = "Copyright 2015 UK Science and Technology Facilities Council"


from collections import namedtuple


class User(namedtuple(
            'User', ['userid', 'first_name', 'surname', 'email', 'ssh_key', 'organisations'])):
    """
    Represents a user in the system. Properties are *read-only*.
    
    .. py:attribute:: userid
        
        The ID of the user. This is used as the username for the portal.
        
    .. py:attribute:: first_name
    
        The first name of the user.
        
    .. py:attribute:: surname
    
        The surname of the user.
        
    .. py:attribute:: email
    
        The email address of the user.
        
    .. py:attribute:: ssh_key
    
        The SSH public key of the user.
        
    .. py:attribute:: organisations
    
        An iterable of organisations for the user.
    """
    @property
    def full_name(self):
        """
        The full name of the user
        """
        return '{} {}'.format(self.first_name or '', self.surname or '').strip()
    
    def belongs_to(self, org):
        """
        Tests if the user belongs to the given organisation.
        
        :param org: The organisation to test for membership of
        :returns: True if this user belongs to the organisation, False otherwise
        """
        return any(o.name == org.name for o in self.organisations)
    
    
class Organisation(namedtuple('Organisation', ['name', 'members'])):
    """
    Represents an organisation in the system. Properties are *read-only*.
    
    .. py:attribute:: name
    
        The name of the organisation.
        
    .. py:attribute:: members
    
        An iterable of members of the organisation.
    """
