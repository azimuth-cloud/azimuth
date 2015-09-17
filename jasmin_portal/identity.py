"""
This module provides identity management functionality for the JASMIN cloud portal.
It uses LDAP for authentication and storage of user information.
"""

__author__ = "Matt Pryor"
__copyright__ = "Copyright 2015 UK Science and Technology Facilities Council"


import functools, collections

from pyramid import events

from jasmin_portal import ldap as jldap
from jasmin_portal.ldap import ldap_authenticate, Filter as f
from jasmin_portal.util import getattrs, DeferredIterable


def setup(config, settings):
    """
    Configures the Pyramid application for catalogue management.
    
    :param config: Pyramid configurator
    :param settings: Settings array passed to Pyramid main function
    :returns: The updated configurator
    """
    
    # Set up the LDAP stuff
    config = jldap.setup(config, settings)

    # Add properties to request    
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
    
    return config


class User(collections.namedtuple(
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
    
    
class Organisation(collections.namedtuple('Organisation', ['name', 'members'])):
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
        return find_by_userid(request, request.authenticated_userid)
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
        return find_by_userid(request, request.unauthenticated_userid)
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
        return org_from_name(request, request.matchdict['org'].lower())
    except (AttributeError, KeyError, TypeError):
        return None


def authenticate_user(request, userid, password):
    """
    Attempts to authenticate a user with the given user ID and password.
    
    Returns the user on success or ``None`` on failure.
    
    :param request: The Pyramid request
    :param userid: The user ID to authenticate
    :param password: The password to authenticate using
    :returns: A user object or ``None``
    """
    # Build the DN
    user_dn = 'CN={uid},{base}'.format(uid = userid,
                                       base = request.registry.settings['ldap.user_base'])
    if ldap_authenticate(request, user_dn, password):
        return find_by_userid(request, userid)
    else:
        return None


@functools.lru_cache(maxsize = 32)
def find_by_userid(request, userid):
    """
    Returns the user with the given ID if one exists, or ``None`` otherwise.
    
    Results from this function are cached for a given request/ID combination, so
    any queries should only be evaluated once per request for a given user ID.
    
    :param request: The Pyramid request
    :param userid: The user ID to find
    :returns: A user object or ``None``
    """
    def to_user(entry):
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
        return User(cn, gn, sn, mail, ssh_key, orgs_for_userid(request, uid))
    
    q = jldap.Query(request.ldap_connection,
                    request.registry.settings['ldap.user_base'],
                    f('cn={userid}', userid = userid),
                    transform = to_user)
    return next(iter(q), None)


def _entry_to_org(request, entry):
    """
    Converts an ldap3 entry object to an organisation object
    """
    suffix = request.registry.settings['ldap.group_suffix']
    # memberUid is not guaranteed to exist by the posixGroup schema (cn is)
    member_uids = getattrs(entry, ['memberUid', 'values'], [])
    # Use a generator expression for the members so it is not evaluated until
    # they are required
    return Organisation(
        entry.cn.value.lower().replace(suffix, ''),
        DeferredIterable(lambda: [find_by_userid(request, uid) for uid in member_uids])
    )


@functools.lru_cache(maxsize = 32)
def org_from_name(request, name):
    """
    Returns the organisation with the given name if one exists, or ``None`` otherwise.
    
    Results from this function are cached for a given request/name combination, so
    any queries should only be evaluated once per request for a given name.
    
    :param request: The Pyramid request
    :param name: The name of the organisation to find
    :returns: An organisation object or ``None``
    """
    # Build the filter
    suffix = request.registry.settings['ldap.group_suffix']
    filter = f('objectClass=posixGroup') &                           \
               f('cn={name}{suffix}', name = name, suffix = suffix)
    q = jldap.Query(request.ldap_connection,
                    request.registry.settings['ldap.group_base'],
                    filter,
                    transform = lambda e: _entry_to_org(request, e))
    return next(iter(q), None)
    

@functools.lru_cache(maxsize = 32)
def orgs_for_userid(request, userid):
    """
    Returns an iterable of the organisations for the userid.
    
    Results from this function are cached for a given request/ID combination, so
    any queries should only be evaluated once per request for a given user ID.
    
    :param request: The Pyramid request
    :param userid: The ID of the user to find organisations for
    :returns: An iterable of organisations
    """
    # Build the filter
    suffix = request.registry.settings['ldap.group_suffix']
    filter = f('objectClass=posixGroup') &           \
               f('cn=*{suffix}', suffix = suffix) &  \
               f('memberUid={uid}', uid = userid)
    return jldap.Query(request.ldap_connection,
                       request.registry.settings['ldap.group_base'],
                       filter,
                       transform = lambda e: _entry_to_org(request, e))
    