"""
This module provides identity management functionality for the JASMIN cloud portal.
It uses LDAP for authentication and storage of user information.
"""

__author__ = "Matt Pryor"
__copyright__ = "Copyright 2015 UK Science and Technology Facilities Council"


from collections import namedtuple

from pyramid import events

from jasmin_portal.ldap import ldap_authenticate, Query, Filter as f
from jasmin_portal.util import getattrs, DeferredIterable


def includeme(config):
    """
    Configures the Pyramid application for identity management.
    
    :param config: Pyramid configurator
    """
    # Set up the LDAP stuff
    config.include('jasmin_portal.ldap')

    # Add properties to request
    config.add_request_method(IdentityService, name = 'id_service', reify = True)
    config.add_request_method(authenticated_user, reify = True)
    config.add_request_method(unauthenticated_user, reify = True)
    config.add_request_method(current_org, reify = True)
    
    # Inject the org from the current request into route_url and route_path if
    # not overridden
    # Because we need access to the original versions of the functions to defer
    # to, we overwrite the functions at request creation time using events
    def overwrite_path_funcs(event):
        def inject_org(request, kw):
            if 'org' not in kw and request.current_org:
                kw['org'] = request.current_org.name
            return kw
        
        # Overwrite the route_url and route_path functions with versions that inject the org
        request = event.request
        
        route_url = request.route_url
        request.route_url = lambda route, *args, **kw: \
            route_url(route, *args, **inject_org(request, kw))
        
        route_path = request.route_path
        request.route_path = lambda route, *args, **kw: \
            route_path(route, *args, **inject_org(request, kw))
    
    config.add_subscriber(overwrite_path_funcs, events.NewRequest)


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
        
        To avoid evaluating the organisations when they are not required, this is
        only guaranteed to be a ``collections.Iterable``, not a ``list``.
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
        
        To avoid evaluating the members when they are not required, this is only
        guaranteed to be a ``collections.Iterable``, not a ``list``.
    """


def authenticated_user(request):
    """
    Returns a user object based on the ``authenticated_userid`` of the given
    request.
    
    .. note::
    
        This function should be accessed as a property of the Pyramid request object,
        i.e. ``user = request.authenticated_user``.
       
        This property is reified, so it is only evaluated once per request.
       
    :param request: The Pyramid request
    :returns: A user object or ``None``
    """
    if request.authenticated_userid:
        return request.id_service.find_user_by_uid(request.authenticated_userid)
    else:
        return None

    
def unauthenticated_user(request):
    """
    Returns a user object based on the ``unauthenticated_userid`` of the given
    request.
    
    .. note::
    
        This function should be accessed as a property of the Pyramid request object,
        i.e. ``user = request.unauthenticated_user``.
       
        This property is reified, so it is only evaluated once per request.
       
    :param request: The Pyramid request
    :returns: A user object or ``None``
    """
    if request.unauthenticated_userid:
        return request.id_service.find_user_by_uid(request.unauthenticated_userid)
    else:
        return None

    
def current_org(request):
    """
    Returns an organisation object based on the organisation name in the URL of
    the given request.
    
    .. note::
    
        This function should be accessed as a property of the Pyramid request object,
        i.e. ``org = request.current_org``.
       
        This property is reified, so it is only evaluated once per request.
       
    :param request: The Pyramid request
    :returns: An organisation object or ``None``
    """
    try:
        return request.id_service.find_org_by_name(request.matchdict['org'].lower())
    except (AttributeError, KeyError, TypeError):
        return None
    
    
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
            DeferredIterable(lambda: [self.find_user_by_uid(uid) for uid in member_uids])
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
    
    def find_user_by_uid(self, uid):
        """
        Returns the user with the given ID if one exists, or ``None`` otherwise.
        
        :param request: The Pyramid request
        :param userid: The user ID to find
        :returns: A user object or ``None``
        """
        q = Query(self._request.ldap_connection,
                  self._request.registry.settings['ldap.user_base'],
                  f('cn={uid}', uid = uid),
                  transform = self.__ldap_to_user)
        return next(iter(q), None)
    
    def authenticate_user(self, uid, passwd):
        """
        Attempts to authenticate a user with the given user ID and password.
        
        :param uid: The user ID to authenticate
        :param passwd: The password to authenticate
        :returns: ``True`` on success, ``False`` on failure
        """
        # Build the DN
        user_dn = 'CN={uid},{base}'.format(
            uid = uid, base = self._request.registry.settings['ldap.user_base']
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
    