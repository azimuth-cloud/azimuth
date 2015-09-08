"""
Authentication and authorisation helpers for authenticating with vCloud Director
"""

__author__ = "Matt Pryor"
__copyright__ = "Copyright 2015 UK Science and Technology Facilities Council"


from pyramid.security import Allow, Authenticated, DENY_ALL

from jasmin_portal.identity import orgs_for_user


def check_cloud_sessions(userid, request):
    """
    Group finder for the authentication policy
    
    Checks that there is an active cloud session for every org that the user
    belongs to and returns the list of org names
    
    If there is an org without an active session, the user is not authenticated at all
    """
    orgs = orgs_for_user(userid, request)
    for org in orgs:
        try:
            # This line could fail in two ways:
            #   1. Session doesn't exist for org
            #   2. Session has expired
            request.get_cloud_session(org).poll()
        except Exception:
            return None
    return orgs


class RootFactory:
    """
    Provides ACL for use with ACLAuthorizationPolicy
    
    ACL is dynamically generated to only allow access to members of the org in
    the URI
    """
    
    def __init__(self, request):
        self.__org = request.current_org
    
    def __acl__(self):
        # If there is an org in the URI, members of that org are granted the
        # org_view and org_edit priveleges
        if self.__org:
            acl = [(Allow, self.__org, 'org_view'), (Allow, self.__org, 'org_edit')]
        else:
            acl = []
        # All authenticated users are granted the view and edit priveleges
        acl.extend([
            (Allow, Authenticated, 'view'), (Allow, Authenticated, 'edit'), DENY_ALL
        ])
        return acl
