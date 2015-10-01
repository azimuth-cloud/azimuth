"""
This module contains helpers for the Pyramid authentication and authorisation systems.
"""

__author__ = "Matt Pryor"
__copyright__ = "Copyright 2015 UK Science and Technology Facilities Council"


from pyramid.authentication import AuthTktAuthenticationPolicy
from pyramid.authorization import ACLAuthorizationPolicy
from pyramid.security import Allow, Authenticated, DENY_ALL


def includeme(config):
    """
    Configures the Pyramid application for authentication and authorization.
    
    :param config: Pyramid configurator
    """
    settings = config.get_settings()
    # We want to use token based authentication, with a check on the cloud sessions
    config.set_authentication_policy(AuthTktAuthenticationPolicy(
        settings['auth.secret'], hashalg = 'sha512', callback = check_cloud_sessions
    ))
    # We use a basic ACL policy for authorisation
    config.set_authorization_policy(ACLAuthorizationPolicy())
    config.set_root_factory(RootFactory)


def check_cloud_sessions(userid, request):
    """
    Group finder for use with the Pyramid ``AuthTktAuthenticationPolicy``.
    
    Checks that there is an active cloud session for every organisation that the
    logged-in user belongs to and returns the list of organisation names.
    
    If there is an organisation without an active session, the user is not
    authenticated at all (i.e. if the cloud session for one organisation times out,
    it is assumed that they have all timed out).
    
    :param userid: The user ID to authenticate for
    :param request: The Pyramid request
    :returns: A list of organisation names for which the user has access, or
              ``None`` if the user is not authenticated
    """
    # Use the unauthenticated user, since this function is used in the calculation
    # of authenticated_userid
    if not request.unauthenticated_user:
        return None
    orgs = request.unauthenticated_user.organisations
    for org in orgs:
        try:
            # This line could fail in two ways:
            #   1. Session doesn't exist for org
            #   2. Session has expired
            request.get_cloud_session(org).poll()
        except Exception:
            return None
    return [o.name for o in orgs]


class RootFactory:
    """
    Provides the ACL for use with the Pyramid ``ACLAuthorizationPolicy``
    
    The ACL is dynamically generated based on the current request only members
    of the organisation in the URI are granted access to organisation-specific
    pages.
    """
    
    def __init__(self, request):
        try:
            self.__org = request.current_org.name
        except AttributeError:
            self.__org = None
    
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
