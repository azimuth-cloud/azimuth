"""
This module provides identity management functionality for the JASMIN cloud portal.
It uses LDAP for authentication and storage of user information.
"""

__author__ = "Matt Pryor"
__copyright__ = "Copyright 2015 UK Science and Technology Facilities Council"


from pyramid import events


def includeme(config):
    """
    Configures the Pyramid application for identity management.
    
    :param config: Pyramid configurator
    """
    # Include the identity service
    config.include('jasmin_portal.identity.ldap_service')

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
        return request.id_service.find_user_by_userid(request.authenticated_userid)
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
        return request.id_service.find_user_by_userid(request.unauthenticated_userid)
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
