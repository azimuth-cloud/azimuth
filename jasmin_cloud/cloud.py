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
    # Expose a key in the session array as storage for our sessions
    SESSION_KEY = 'cloud'
    def cloud_sessions(request):
        if SESSION_KEY not in request.session:
            request.session[SESSION_KEY] = {}
        return request.session[SESSION_KEY]
    config.add_request_method(cloud_sessions, reify = True)
    
    
_SESSION_KEY = 'cloud'
def cloud_sessions(request):
    """
    Returns the dictionary of cloud sessions for the request.
    
    .. note::
    
        This function should be accessed as a property of the Pyramid request object,
        i.e. ``sessions = request.cloud_sessions``.
       
        This property is reified, so it is only evaluated once per request.
    """
    if _SESSION_KEY not in request.session:
        request.session[_SESSION_KEY] = {}
    return request.session[_SESSION_KEY]
