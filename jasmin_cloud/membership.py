"""
This module provides functionality for managing the organisation memberships of
users of the JASMIN cloud portal.
"""

_author_ = "Matt Pryor"
_copyright_ = "Copyright 2015 UK Science and Technology Facilities Council"

from functools import lru_cache

from jasmin_ldap import Server, Query


def includeme(config):
    """
    Configures the Pyramid application for membership management.

    :param config: Pyramid configurator
    """
    # Add an organisation manager to the request
    def memberships(request):
        return MembershipManager(
            request.registry.settings['ldap.server'],
            request.registry.settings['ldap.group_base'],
            request.registry.settings['ldap.group_suffix'],
            request.registry.settings['ldap.bind_dn'],
            request.registry.settings['ldap.bind_pass']
        )
    config.add_request_method(memberships, reify = True)


class NoSuchOrganisationError(Exception):
    """
    Raised when an organisation name is given that doesn't exist.
    """


class MembershipManager:
    """
    Class for managing organisation memberships of JASMIN users.

    This implementation uses LDAP groups to find relationships between users and
    organisations.

    .. note::

        An instance of this class can be accessed as a property of the Pyramid
        request object, i.e. ``r = request.memberships``.

        This property is reified, so it is only evaluated once per request.

    :param server: The address of the LDAP server
    :param group_base: The DN of the part of the tree to search for groups
    :param group_suffix: The suffix used in LDAP group names
    :param bind_dn: The DN to use when authenticating with the LDAP server
                    (optional - if omitted, an anonymous connection is used, but
                    some functionality may be unavailable)
    :param bind_pass: The password to use when authenticating with the LDAP server
                      (optional - if ``bind_dn`` is not given, this is ignored)
    """
    def __init__(self, server, group_base, group_suffix, bind_dn = None, bind_pass = None):
        self._group_suffix = group_suffix
        # Create a new base query
        self._query = Query(
            Server(server).authenticate(bind_dn, bind_pass), group_base
        ).filter(objectClass = 'posixGroup')
        # We want to cache the results of our methods for the duration of the
        # request
        self.orgs_for_user = lru_cache(maxsize = 16)(self.orgs_for_user)
        self.members_for_org = lru_cache(maxsize = 16)(self.members_for_org)

    def orgs_for_user(self, username):
        """
        Returns a list of organisations for the given user.

        :param username: The username of the user to find organisations for
        :returns: List of organisation names
        """
        # Perform a search to find all the groups under our base which have
        # the correct suffix for which the given username is in the memberUid
        # attribute
        q = self._query.filter(cn__endswith = self._group_suffix)  \
                       .filter(memberUid = username)
        # We want to use the cn with the suffix removed for the organisation name
        return sorted(e['cn'][0].lower().replace(self._group_suffix, '') for e in q)

    def members_for_org(self, organisation):
        """
        Returns a list of usernames of users that belong to the organisation.

        If the organisation doesn't exist, this will raise a
        :py:class:`NoSuchOrganisationError`.

        :param organisation: The organisation name
        :returns: List of usernames
        """
        # Perform a search to find the group whose CN is the organisation with
        # the correct suffix
        q = self._query.filter(cn = organisation + self._group_suffix)
        # If the search result is empty, we want to raise an error
        # Otherwise, we want to return the values in the memberUid attribute
        try:
            return next(iter(q)).get('memberUid', [])
        except StopIteration:
            raise NoSuchOrganisationError('{} is not an organisation'.format(organisation))
