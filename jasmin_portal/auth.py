"""
Authentication and authorisation helpers for authenticating with vCloud Director
"""

__author__ = "Matt Pryor"
__copyright__ = "Copyright 2015 UK Science and Technology Facilities Council"


import pickle

from pyramid.request import Request
from pyramid.security import Allow, Authenticated, DENY_ALL

from jasmin_portal.cloudservices import CloudServiceError


class RequestFactory(Request):
    """
    Custom request factory that adds a vcd_session property to the base request
    
    It also handles pickling and unpickling the vCD session from the session
    object
    """
    
    _SESSION_KEY = 'vcloud'
    
    def _get_vcd_session(self):
        # Lazily reconstruct the vcd session from the session attribute
        if not hasattr(self, '__vcd_session'):
            if self._SESSION_KEY in self.session:
                self.__vcd_session = pickle.loads(self.session[self._SESSION_KEY])
            else:
                self.__vcd_session = None
        return self.__vcd_session
    
    def _set_vcd_session(self, session):
        self.__vcd_session = session
        # When the vcd session is set, we store its representation in the session
        if session is not None:
            self.session[self._SESSION_KEY] = pickle.dumps(session)
        # If the vcd session is being set to None, remove any keys from the session
        elif self._SESSION_KEY in self.session:
            del self.session[self._SESSION_KEY]     
    
    vcd_session = property(_get_vcd_session, _set_vcd_session)


def check_session(user_id, request):
    """
    Checks if there is a vCD session available and whether it is still active
    
    This is used as a group finder for an auth tkt policy, so returns None
    if there is no vCD session or the vCD session has expired and [] if
    the vCD session is active
    """
    # We want to make sure appropriate messages are displayed to the user
    # if a vCD session is not available
    try:
        if request.vcd_session is None:
            return None
        if not request.vcd_session.is_active():
            request.vcd_session = None
            return None
        else:
            return []
    except CloudServiceError as e:
        request.session.flash(str(e), 'error')
        return None


class RootFactory:
    """
    Provides ACL for use with ACLAuthorizationPolicy
    """
    
    # Authenticated users are granted view and edit permissions on every route
    __acl__ = [
        (Allow, Authenticated, 'view'),
        (Allow, Authenticated, 'edit'),
        DENY_ALL,
    ]
    
    def __init__(self, request):
        pass
