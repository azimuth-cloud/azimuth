"""
This module configures the Pyramid authentication and authorisation systems for
the cloud portal, and adds some useful properties to the request.
"""

__author__ = "Matt Pryor"
__copyright__ = "Copyright 2015 UK Science and Technology Facilities Council"

from pyramid.authentication import AuthTktAuthenticationPolicy
from pyramid.authorization import ACLAuthorizationPolicy
from pyramid.security import Allow, Authenticated, DENY_ALL
from pyramid import events

from jasmin_ldap import Server, Query, AuthenticationError

from .cloudservices import CloudServiceError


def includeme(config):
    """
    Configures the Pyramid application for authentication and authorization.

    :param config: Pyramid configurator
    """
    settings = config.get_settings()

    # We want to use token based authentication, with a check on the cloud sessions
    config.set_authentication_policy(AuthTktAuthenticationPolicy(
        settings['auth.secret'], hashalg = 'sha512', callback = _check_cloud_sessions
    ))
    # We use a basic ACL policy for authorisation
    config.set_authorization_policy(ACLAuthorizationPolicy())
    config.set_root_factory(RootFactory)

    # Add a user manager to the request
    def users(request):
        return UserManager(
            request.registry.settings['ldap.server'],
            request.registry.settings['ldap.user_base'],
            request.registry.settings['ldap.bind_dn'],
            request.registry.settings['ldap.bind_pass']
        )
    config.add_request_method(users, reify = True)

    # Make (un)authenticated_user properties available on the request object that
    # return a JASMIN user object
    config.add_request_method(authenticated_user, reify = True)

    # Make the current organisation name available as a property of the request
    config.add_request_method(current_org, reify = True)

    # Inject the org from the current request into route_url and route_path if
    # not overridden
    # Because we need access to the original versions of the functions to defer
    # to, we overwrite the functions at request creation time using events
    def overwrite_path_funcs(event):
        def inject_org(request, kw):
            if 'org' not in kw and request.current_org:
                kw['org'] = request.current_org
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


class UserManager:
    """
    Class for managing JASMIN users in LDAP.

    .. note::

        An instance of this class can be accessed as a property of the Pyramid
        request object, i.e. ``r = request.users``.

        This property is reified, so it is only evaluated once per request.

    :param server: The address of the LDAP server
    :param user_base: The DN of the part of the tree to search for entries
    :param bind_dn: The DN to use when authenticating with the LDAP server
                    (optional - if omitted, an anonymous connection is used, but
                    some functionality may be unavailable)
    :param bind_pass: The password to use when authenticating with the LDAP server
                      (optional - if ``bind_dn`` is not given, this is ignored)
    """
    def __init__(self, server, user_base, bind_dn = None, bind_pass = None):
        self._user_base = user_base
        self._server = Server(server)
        # Create a base query
        self._query = Query(
            self._server.authenticate(bind_dn, bind_pass), user_base
        ).filter(objectClass = 'posixAccount')

    def authenticate(self, username, password):
        """
        Attempts to authenticate a user with the given username and password.

        Returns ``True`` if authentication is successful, ``False`` otherwise.

        :param username: The username to authenticate
        :param password: The password to authenticate
        :returns: ``True`` on success, ``False`` on failure.
        """
        user_dn = 'cn={},{}'.format(username, self._user_base)
        try:
            # Try to authenticate with the server as the user
            self._server.authenticate(user_dn, password).close()
            return True
        except AuthenticationError:
            return False

    def find_by_username(self, username):
        """
        Returns the user with the given username, or ``None`` if none exists.

        :param username: The username to search for
        :returns: Dictionary of user details, or ``None``
        """
        user = self._query.filter(cn = username).one()
        if user:
            return {
                'username' : user['cn'][0],
                'full_name' : '{} {}'.format(
                    next(iter(user.get('givenName', [])), ''), user['sn'][0]
                ).strip(),
                'email' : next(iter(user.get('mail', [])), ''),
                'ssh_key' : next(iter(user.get('sshPublicKey', [])), ''),
            }
        else:
            return None


def authenticated_user(request):
    """
    Returns a ``jasmin_auth.User`` based on the ``authenticated_userid`` of the
    given request.

    .. note::

        This function should be accessed as a property of the Pyramid request object,
        i.e. ``user = request.authenticated_user``.

        This property is reified, so it is only evaluated once per request.

    :param request: The Pyramid request
    :returns: A ``jasmin_auth.User`` or ``None``
    """
    if request.authenticated_userid:
        return request.users.find_by_username(request.authenticated_userid)
    else:
        return None


def current_org(request):
    """
    Returns the organisation name in the URL of the given request, or ``None`` if
    we are not on an organisation-specific URL.

    .. note::

        This function should be accessed as a property of the Pyramid request object,
        i.e. ``org = request.current_org``.

        This property is reified, so it is only evaluated once per request.

    :param request: The Pyramid request
    :returns: The organisation name or ``None``
    """
    try:
        return request.matchdict['org'].lower()
    except (TypeError, AttributeError, KeyError):
        return None


def _check_cloud_sessions(userid, request):
    """
    Group finder for use with the Pyramid ``AuthTktAuthenticationPolicy``.

    Returns the list of organisation names to which the current user has access.

    To do this, we use ``request.cloud_sessions``, and assume it contains a session
    per organisation for which the user has access.

    If any session that was successfully opened has timed out, we treat the user
    as completely unauthenticated, and force them to log in again.
    """
    # First, make sure we can find a user with the given userid
    if not request.users.find_by_username(userid):
        return None
    # Get the user's orgs
    orgs = request.memberships.orgs_for_user(userid)
    # Get the orgs for which we have sessions
    session_orgs = request.cloud_sessions.has_sessions_for()
    # If the two differ, force the user to log in again so that we can log them
    # in to any new orgs and make sure they are NOT logged in to any that they
    # can no longer access
    if set(orgs).symmetric_difference(session_orgs):
        return None
    # Bail if any sessions that were successfully started have now timed out
    for org in orgs:
        # If this raises, the session was never successfully started
        try:
            session = request.cloud_sessions.get_session(org)
        except CloudServiceError:
            continue
        # If this raises, the session has timed out
        try:
            session.poll()
        except CloudServiceError:
            return None
    return orgs


class RootFactory:
    """
    Provides the ACL for use with the Pyramid ``ACLAuthorizationPolicy``

    The ACL is dynamically generated based on the current request so that only
    members of the organisation in the URL are granted access to
    organisation-specific pages.
    """

    def __init__(self, request):
        # If there is an org in the URI, members of that org are granted the
        # org_view and org_edit privileges
        if request.current_org:
            self.__acl__ = [(Allow, request.current_org, 'org_view'),
                            (Allow, request.current_org, 'org_edit')]
        else:
            self.__acl__ = []
        # All authenticated users are granted the view and edit privileges
        self.__acl__.extend([(Allow, Authenticated, 'view'),
                             (Allow, Authenticated, 'edit'),
                             DENY_ALL])
