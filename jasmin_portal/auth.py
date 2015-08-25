"""
Authentication and authorisation helpers for authenticating with vCloud Director
"""

__author__ = "Matt Pryor"
__copyright__ = "Copyright 2015 UK Science and Technology Facilities Council"


import pickle

from pyramid.request import Request
from pyramid.security import Allow, DENY_ALL

from jasmin_portal.cloudservices import CloudServiceError


class RequestFactory(Request):
    """
    Custom request factory that:
    
      1. Adds a vcd_session property representing the current vCD session, and
         handles pickling and unpickling the vCD session from the session object
      2. Overrides route_url and route_path to insert the org from the current
         request, unless overridden
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
    
    def route_url(self, route_name, *elements, **kw):
        if 'org' not in kw:
            try:
                kw['org'] = self.matchdict.get('org')
            except (AttributeError, KeyError):
                pass
        return super().route_url(route_name, *elements, **kw)
    
    def route_path(self, route_name, *elements, **kw):
        if 'org' not in kw:
            try:
                kw['org'] = self.matchdict.get('org')
            except (AttributeError, KeyError):
                pass
        return super().route_path(route_name, *elements, **kw)


def check_session(user_id, request):
    """
    Checks if there is a vCD session available and whether it is still active
    
    This is used as a group finder for an auth tkt policy, so returns None
    if there is no vCD session or the vCD session has expired
    If the vCD session is active, it returns a list containing the org from the
    username
    """
    try:
        if request.vcd_session is None:
            return None
        if not request.vcd_session.is_active():
            request.vcd_session = None
            return None
        else:
            return [user_id.split('@').pop().lower()]
    except CloudServiceError as e:
        request.session.flash(str(e), 'error')
        return None


class RootFactory:
    """
    Provides ACL for use with ACLAuthorizationPolicy
    
    ACL is dynamically generated to only allow access to members of the org in
    the URI
    """
    
    def __init__(self, request):
        try:
            self.__org = request.matchdict.get('org').lower()
        except (AttributeError, KeyError):
            self.__org = None
    
    # Authenticated users are granted view and edit permissions on every route
    def __acl__(self):
        if self.__org:
            acl = [(Allow, self.__org, 'view'), (Allow, self.__org, 'edit')]
        else:
            acl = []
        acl.append(DENY_ALL)
        return acl
