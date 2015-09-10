"""
Identity management functionality for the JASMIN cloud portal

We use LDAP for authentication and storage of user information
"""

__author__ = "Matt Pryor"
__copyright__ = "Copyright 2015 UK Science and Technology Facilities Council"


import functools, re, collections

from pyramid import events

from jasmin_portal import ldap as jldap
from jasmin_portal.ldap import Filter as f


def setup(config, settings):
    """
    Given a pyramid configurator and a settings dictionary, configure the app
    for identity management
    """
    
    # Set up the LDAP stuff
    config = jldap.setup(config, settings)

    # Add a couple of useful properties to request
    
    def authenticated_user(request):
        # Returns a user object based on the authenticated_userid
        if request.authenticated_userid:
            return find_by_userid(request, request.authenticated_userid)
        else:
            return None
    
    def unauthenticated_user(request):
        # Returns a user object based on the unauthenticated_userid
        if request.unauthenticated_userid:
            return find_by_userid(request, request.unauthenticated_userid)
        else:
            return None
    
    def current_org(request):
        # Gets the current organisation for the request
        try:
            return org_from_name(request, request.matchdict['org'].lower())
        except (AttributeError, KeyError):
            return None
    
    config.add_request_method(authenticated_user, reify = True)
    config.add_request_method(unauthenticated_user, reify = True)
    config.add_request_method(current_org, reify = True)
    

    # Inject the org from the current request into route_url and route_path if not overridden
    # Because we need access to the original versions of the functions to defer to, we inject
    # overwrite the functions at request creation time using events
    def overwrite_path_funcs(event):
        def inject_org(request, kw):
            if 'org' not in kw and request.current_org:
                kw['org'] = request.current_org.name
            return kw
        
        # Overwrite the route_url and route_path functions with versions that inject the org
        request = event.request
        
        route_url = request.route_url
        request.route_url = lambda route, *args, **kw: route_url(route, *args, **inject_org(request, kw))
        
        route_path = request.route_path
        request.route_path = lambda route, *args, **kw: route_path(route, *args, **inject_org(request, kw))
    
    config.add_subscriber(overwrite_path_funcs, events.NewRequest)
    
    return config


class User(collections.namedtuple(
            'UserAttrs', ['userid', 'name', 'email', 'ssh_public_key', 'organisations'])):
    """
    Represents a user in the system
    """
    def belongs_to(self, org):
        """
        Returns True if the user belongs to the org, False otherwise
        """
        return any(o.name == org.name for o in self.organisations)
    
    
Organisation = collections.namedtuple('Organisation', ['name', 'members'])
Organisation.__doc__ = """Represents an organisation in the system"""


def authenticate_user(request, userid, password):
    """
    Attempts to authenticate the user with the LDAP database
    
    Returns the user on success or None on failure
    """
    # Build the DN
    user_dn = 'CN={uid},{base}'.format(uid = userid,
                                       base = request.registry.settings['ldap.user_base'])
    if request.ldap_authenticate(user_dn, password):
        return find_by_userid(request, userid)
    else:
        return None


@functools.lru_cache(maxsize = 32)
def find_by_userid(request, userid):
    """
    Returns the user with the given userid, or None if the userid does not exist
    """
    def to_user(entry):
        return User(
            entry.cn.value,
            entry.sn.value,
            entry.mail.value,
            entry.sshPublicKey.value,
            orgs_for_userid(request, entry.uid.value)
        )
    
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
    # Use a generator expression for the members so it is not evaluated until
    # they are required
    return Organisation(
        entry.cn.value.lower().replace(suffix, ''),
        ( find_by_userid(request, uid) for uid in entry.memberUid.values )
    )


@functools.lru_cache(maxsize = 32)
def org_from_name(request, name):
    """
    Returns the organisation with the given name, or None if none exists
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
    Returns an iterable of the organisations for the userid
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
    