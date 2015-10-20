"""
This module provides functionality for persisting and retrieving cloud sessions
across multiple requests.
"""

__author__ = "Matt Pryor"
__copyright__ = "Copyright 2015 UK Science and Technology Facilities Council"


def includeme(config):
    """
    Configures the Pyramid application for persisting and retrieving cloud sessions.
    
    :param config: Pyramid configurator
    """
    # Add additional methods and properties to request
    config.add_request_method(add_cloud_session)
    config.add_request_method(get_cloud_session)
    config.add_request_method(clear_cloud_sessions)
    config.add_request_method(active_cloud_session, reify = True)
    

_SESSION_KEY = 'cloud'
    
    
def _store(request):
    """
    Returns the cloud_session dictionary from the Pyramid session, creating it if
    it doesn't exist
    """
    if _SESSION_KEY not in request.session:
        request.session[_SESSION_KEY] = {}
    return request.session[_SESSION_KEY]
    
    
def add_cloud_session(request, org, session):
    """
    Adds the given cloud session to the Pyramid session, associated with the given
    organisation.
    
    .. note::
    
        This function should be accessed as a method of the Pyramid request object,
        i.e. ``request.add_cloud_session(org, session)``.
    
    :param request: The Pyramid request
    :param org: The organisation to associate the session with
    """
    _store(request)[org.name] = session
        
    
def get_cloud_session(request, org):
    """
    Retrieves the cloud session associated with the organisation.
    
    .. note::
    
        This function should be accessed as a method of the Pyramid request object,
        i.e. ``session = request.get_cloud_session(org)``.
    
    :param request: The Pyramid request
    :param org: The organisation to get the session for
    :returns: The cloud session, or ``None`` if there is not one
    """
    return _store(request).get(org.name, None)
    

def clear_cloud_sessions(request):
    """
    Closes and clears all cloud sessions associated with the current Pyramid session.
    
    .. note::
    
        This function should be accessed as a method of the Pyramid request object,
        i.e. ``request.clear_cloud_sessions()``.
    
    :param request: The Pyramid request
    """
    store = _store(request)
    for s in store.values():
        s.close()
    store.clear()
            
    
def active_cloud_session(request):
    """
    Retrieves the active cloud session based on the organisation in the request URL.
    
    .. note::
    
        This function should be accessed as a property of the Pyramid request object,
        i.e. ``session = request.active_cloud_session``.
       
        This property is reified, so it is only evaluated once per request.
    
    :param request: The Pyramid request
    :param org: The organisation to get the session for
    :returns: The active cloud session, or ``None`` if there is not one
    """
    return request.get_cloud_session(request.current_org)
