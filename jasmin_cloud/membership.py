"""
This module provides functionality for managing the organisation memberships of
users of the JASMIN cloud portal.
"""

__author__ = "Matt Pryor"
__copyright__ = "Copyright 2015 UK Science and Technology Facilities Council"

from functools import lru_cache
import ldap3
import ldap3.utils


def includeme(config):
    """
    Configures the Pyramid application for membership management.
    
    :param config: Pyramid configurator
    """
    # Add an organisation manager to the request
    def memberships(request):
        return MembershipManager(
            request.registry.settings['ldap.server'],
            request.registry.settings['ldap.group_base'],
            request.registry.settings['ldap.group_suffix'],
            request.registry.settings['ldap.bind_dn'],
            request.registry.settings['ldap.bind_pass']
        )
    config.add_request_method(memberships, reify = True)
    
    
class LDAPError(Exception):
    """
    Raised when an unexpected LDAP error occurs.
    
    It will always be raised with the underlying
    `ldap3 exception <https://ldap3.readthedocs.org/exceptions.html>`_ as its cause
    using the ``raise ... from ...`` syntax.
    """
    

class NoSuchOrganisationError(Exception):
    """
    Raised when an organisation name is given that doesn't exist.
    """
    
    
_char_map = { '*': '\\2A', '(': '\\28', ')': '\\29', '\\': '\\5C', '\0': '\\00' }
def _escape(value):
    """
    Escapes a parameter value for use in an LDAP filter.
    """
    if isinstance(value, bytes):
        return ldap3.utils.conv.escape_bytes(value)
    else:
        if not isinstance(value, str):
            value = str(value)
        return ''.join(_char_map.get(c, c) for c in value)

    
class MembershipManager:
    """
    Class for managing organisation memberships of JASMIN users.
    
    This implementation uses LDAP groups to find relationships between users and
    organisations.
    
    .. note::
    
        An instance of this class can be accessed as a property of the Pyramid
        request object, i.e. ``r = request.memberships``.
       
        This property is reified, so it is only evaluated once per request.
        
    :param server: The address of the LDAP server
    :param group_base: The DN of the part of the tree to search for groups
    :param group_suffix: The suffix used in LDAP group names
    :param bind_dn: The DN to use when authenticating with the LDAP server
                    (optional - if omitted, an anonymous connection is used, but
                    some functionality may be unavailable)
    :param bind_pass: The password to use when authenticating with the LDAP server
                      (optional - if ``bind_dn`` is not given, this is ignored)
    """
    def __init__(self, server, group_base, group_suffix, bind_dn = None, bind_pass = None):
        self.__group_base = group_base
        self.__group_suffix = group_suffix
        # Create a new connection
        try:
            self.__conn = ldap3.Connection(
                server, user = bind_dn, password = bind_pass,
                auto_bind = ldap3.AUTO_BIND_TLS_BEFORE_BIND, raise_exceptions = True
            )
        except ldap3.LDAPException as e:
            raise LDAPError('Error opening LDAP connection') from e
        # We want to cache the results of our methods for the duration of the
        # request
        self.orgs_for_user = lru_cache(maxsize = 16)(self.orgs_for_user)
        self.members_for_org = lru_cache(maxsize = 16)(self.members_for_org)
    
    def orgs_for_user(self, username):
        """
        Returns a list of organisations for the given user.
        
        :param username: The username of the user to find organisations for
        :returns: List of organisation names
        """
        try:
            # Perform a search to find all the groups under our base which have
            # the correct suffix for which the given username is in the memberUid
            # attribute
            self.__conn.search(
                self.__group_base,
                '(&(objectClass=posixGroup)(cn=*{})(memberUid={}))'.format(
                    _escape(self.__group_suffix), _escape(username)
                ),
                search_scope = ldap3.SEARCH_SCOPE_SINGLE_LEVEL,
                attributes = ldap3.ALL_ATTRIBUTES
            )
        except ldap3.LDAPException as e:
            raise LDAPError('Error while searching') from e
        # We want to use the cn for the organisation name
        cns = (e['attributes']['cn'][0].lower() for e in (self.__conn.response or []))
        # We want to remove the suffix
        return sorted([cn.replace(self.__group_suffix, '') for cn in cns])
        
    def members_for_org(self, organisation):
        """
        Returns a list of usernames of users that belong to the organisation.
        
        If the organisation doesn't exist, this will raise a
        :py:class:`NoSuchOrganisationError`.
        
        :param organisation: The organisation name
        :returns: List of usernames
        """
        try:
            # Perform a search to find the group whose CN is the organisation with
            # the correct suffix 
            self.__conn.search(
                self.__group_base,
                '(&(objectClass=posixGroup)(cn={}{}))'.format(_escape(organisation),
                                                              _escape(self.__group_suffix)),
                search_scope = ldap3.SEARCH_SCOPE_SINGLE_LEVEL,
                attributes = ldap3.ALL_ATTRIBUTES
            )
        except ldap3.LDAPException as e:
            raise LDAPError('Error while searching') from e
        # If the search result is empty, we want to raise an error
        # Otherwise, we want to return the values in the memberUid attribute
        try:
            return next(iter(self.__conn.response or []))['attributes'].get('memberUid', [])
        except (StopIteration, KeyError):
            raise NoSuchOrganisationError('{} is not an organisation'.format(organisation))
