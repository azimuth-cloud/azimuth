"""
Module that provides functionality for persisting cloud sessions across requests
"""

__author__ = "Matt Pryor"
__copyright__ = "Copyright 2015 UK Science and Technology Facilities Council"


def setup(config, settings):
    """
    Given a pyramid configurator and a settings dictionary, configure the cloud
    integration for the app
    """
    # Add additional methods and properties to request
    
    SESSION_KEY = 'cloud'
    
    def _store(request):
        # Returns the cloud_session dictionary from the Pyramid session, creating
        # it if it doesn't exist
        if SESSION_KEY not in request.session:
            request.session[SESSION_KEY] = {}
        return request.session[SESSION_KEY]
    
    def add_cloud_session(request, org, session):
        # Adds the given cloud session to the Pyramid session, associated with
        # the given org
        _store(request)[org] = session
        
    def get_cloud_session(request, org):
        # Returns the cloud session associated with the org, or None if none exists
        return _store(request).get(org, None)
    
    def clear_cloud_sessions(request):
        # Closes and clears all cloud sessions associated with the current
        # Pyramid session
        store = _store(request)
        for s in store.values():
            s.close()
        store.clear()
            
    def active_cloud_session(request):
        # Returns the active cloud session based on the org in the URI, or
        # None if one does not exist
        return request.get_cloud_session(request.current_org)
            
    config.add_request_method(add_cloud_session)
    config.add_request_method(get_cloud_session)
    config.add_request_method(clear_cloud_sessions)
    config.add_request_method(active_cloud_session, reify = True)
    
    return config
