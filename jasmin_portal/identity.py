"""
Identity management functionality for the JASMIN cloud portal

We use LDAP for authentication and storage of user information
"""

__author__ = "Matt Pryor"
__copyright__ = "Copyright 2015 UK Science and Technology Facilities Council"


import functools, re

import ldap3
from ldap3.utils.dn import parse_dn
from pyramid import events
from pyramid_ldap3 import get_ldap_connector


def setup(config, settings):
    """
    Given a pyramid configurator and a settings dictionary, configure the app
    for identity management
    """
    # We want to use LDAP
    config.include('pyramid_ldap3')
    
    # Define our LDAP configuration
    config.ldap_setup(
        settings['ldap.server'], bind = settings['ldap.bind_dn'], passwd = settings['ldap.bind_pass']
    )
    config.ldap_set_login_query(
        base_dn = settings['ldap.user_base'],
        filter_tmpl = '(uid=%(login)s)',
        scope = ldap3.SEARCH_SCOPE_SINGLE_LEVEL
    )
    config.ldap_set_groups_query(
        base_dn = settings['ldap.group_base'],
        filter_tmpl = '(&(objectClass=posixGroup)(memberUid=%(userdn)s))',
        scope = ldap3.SEARCH_SCOPE_SINGLE_LEVEL
    )
    
    # Add a couple of useful properties to request
    
    def current_userid(request):
        # Just reifies the authenticated_userid, so that the check is only done once
        return request.authenticated_userid
    
    config.add_request_method(current_userid, reify = True)
    
    def current_org(request):
        # Gets the current organisation for the request
        try:
            return request.matchdict['org'].lower()
        except (AttributeError, KeyError):
            return None
    
    config.add_request_method(current_org, reify = True)
    
    def available_orgs(request):
        # Returns the orgs for the current user
        if request.current_userid:
            return orgs_for_user(request.current_userid, request)
        return []
    
    config.add_request_method(available_orgs, reify = True)
    
    # Inject the org from the current request into route_url and route_path if not overridden
    # Because we need access to the original versions of the functions to defer to, we inject
    # overwrite the functions at request creation time using events
    def overwrite_path_funcs(event):
        def inject_org(request, kw):
            # If org is not present in kw, try to inject it from the request before
            # returning kw
            if 'org' not in kw and request.current_org:
                kw['org'] = request.current_org
            return kw
        
        # Overwrite the route_url and route_path functions with versions that inject the org
        request = event.request
        
        route_url = request.route_url
        request.route_url = lambda route, *args, **kw: route_url(route, *args, **inject_org(request, kw))
        
        route_path = request.route_path
        request.route_path = lambda route, *args, **kw: route_path(route, *args, **inject_org(request, kw))
    
    config.add_subscriber(overwrite_path_funcs, events.NewRequest)
    
    return config


def authenticate_user(request, userid, password):
    """
    Attempt to authenticate the user, and return True if successful, False otherwise
    """
    conn = get_ldap_connector(request)
    return ( conn.authenticate(userid, password) is not None )


@functools.lru_cache(maxsize = 32)
def orgs_for_user(userid, request):
    """
    Returns the organisations that the user with the given user id belongs to
    
    The results are cached for the duration of the request
    """
    conn = get_ldap_connector(request)
    pattern = re.compile(request.registry.settings['ldap.group_pattern'])
    groups = ( parse_dn(dn).pop(0)[1].lower() for dn, _ in conn.user_groups(userid) )
    matches = ( pattern.match(g) for g in groups )
    return [ m.group('org') for m in matches if m ]
