"""
This module provides an LDAP implementation of the identity service and integrates
it with Pyramid.
"""

__author__ = "Matt Pryor"
__copyright__ = "Copyright 2015 UK Science and Technology Facilities Council"


from jasmin_portal.ldap import ldap_authenticate, Query, Filter as f
from jasmin_portal.util import getattrs, DeferredIterable

from .dto import User, Organisation


def includeme(config):
    """
    Configures the Pyramid application to use the LDAP identity service.
    
    :param config: Pyramid configurator
    """
    # Include LDAP utilities
    config.include('jasmin_portal.ldap')

    # Add properties to request
    config.add_request_method(IdentityService, name = 'id_service', reify = True)


class IdentityService:
    """
    Service class providing functionality related to ``User``\ s and ``Organisation``\ s.
    
    This implementation uses an LDAP database.
    
    .. note::
    
        An instance of this class can be accessed as a property of the Pyramid
        request object, i.e. ``r = request.id_service``.
       
        This property is reified, so it is only evaluated once per request.
       
    :param request: The Pyramid request
    """
    def __init__(self, request):
        self._request = request

    def __ldap_to_org(self, entry):
        """
        Converts an ldap3 entry object to an Organisation object
        """
        suffix = self._request.registry.settings['ldap.group_suffix']
        # memberUid is not guaranteed to exist by the posixGroup schema (cn is)
        member_uids = getattrs(entry, ['memberUid', 'values'], [])
        # Use a deferred iteable for the members so it is not evaluated until
        # they are used
        return Organisation(
            entry.cn.value.lower().replace(suffix, ''),
            DeferredIterable(lambda: [self.find_user_by_userid(uid) for uid in member_uids])
        )
        
    def __ldap_to_user(self, entry):
        """
        Converts an ldap3 entry object to a User object
        """
        # Due to the object classes used for users, cn, sn and uid are guaranteed to exist
        cn  = entry.cn.value
        sn  = entry.sn.value
        uid = entry.uid.value
        # gn, mail and sshPublicKey may or may not exist
        gn      = getattrs(entry, ['gn', 'value'], None)
        mail    = getattrs(entry, ['mail', 'value'], None)
        ssh_key = getattrs(entry, ['sshPublicKey', 'value'], None)
        # Remove any funny trailing whitespace characters
        if ssh_key:
            ssh_key = ssh_key.strip()
        # Get an iterable for the user's orgs
        # Since we only guarantee iterable, we can just use the Query directly
        suffix = self._request.registry.settings['ldap.group_suffix']
        filter = f('objectClass=posixGroup') &           \
                   f('cn=*{suffix}', suffix = suffix) &  \
                   f('memberUid={uid}', uid = uid)
        orgs = Query(self._request.ldap_connection,
                     self._request.registry.settings['ldap.group_base'],
                     filter,
                     transform = self.__ldap_to_org)
        return User(cn, gn, sn, mail, ssh_key, orgs)
    
    def _find_user_by_filter(self, filter):
        """
        Returns the first user that fulfills the given filter, or ``None`` if one
        does not exist.
        """
        q = Query(self._request.ldap_connection,
                  self._request.registry.settings['ldap.user_base'],
                  filter,
                  transform = self.__ldap_to_user)
        return next(iter(q), None)
    
    def find_user_by_userid(self, userid):
        """
        Returns the user with the given ID if one exists, or ``None`` otherwise.
        
        :param userid: The user ID to find
        :returns: A user object or ``None``
        """
        return self._find_user_by_filter(f('uid={}', userid))
    
    def find_user_by_email(self, email):
        """
        Returns the user with the given email address if one exists, or ``None``
        otherwise.
        
        :param email: The email address to search for
        :returns: A user object or ``None``
        """
        return self._find_user_by_filter(f('mail={}', email))
    
    def authenticate_user(self, userid, passwd):
        """
        Attempts to authenticate a user with the given user ID and password.
        
        :param userid: The user ID to authenticate
        :param passwd: The password to authenticate
        :returns: ``True`` on success, ``False`` on failure
        """
        # Build the DN
        user_dn = 'CN={userid},{base}'.format(
            userid = userid, base = self._request.registry.settings['ldap.user_base']
        )
        return ldap_authenticate(self._request, user_dn, passwd)

    def find_org_by_name(self, name):
        """
        Returns the organisation with the given name if one exists, or ``None`` otherwise.
        
        :param name: The name of the organisation to find
        :returns: An ``Organisation`` object or ``None``
        """
        # Build the filter
        suffix = self._request.registry.settings['ldap.group_suffix']
        filter = f('objectClass=posixGroup') &                           \
                   f('cn={name}{suffix}', name = name, suffix = suffix)
        q = Query(self._request.ldap_connection,
                  self._request.registry.settings['ldap.group_base'],
                  filter,
                  transform = self.__ldap_to_org)
        return next(iter(q), None)
