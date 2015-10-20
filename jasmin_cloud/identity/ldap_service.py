"""
This module provides an LDAP implementation of the identity service and integrates
it with Pyramid.
"""

__author__ = "Matt Pryor"
__copyright__ = "Copyright 2015 UK Science and Technology Facilities Council"


from ..ldap import Filter as f
from ..util import first, DeferredIterable

from .dto import User, Organisation
from .validation import validate_user_fields


def includeme(config):
    """
    Configures the Pyramid application to use the LDAP identity service.
    
    :param config: Pyramid configurator
    """
    # Include LDAP utilities
    config.include('jasmin_cloud.ldap')

    # Add properties to request
    def id_service(request):
        return IdentityService(request.ldap_connection, request.registry.settings)
    config.add_request_method(id_service, reify = True)


class IdentityService:
    """
    Service class providing functionality related to ``User``\ s and ``Organisation``\ s.
    
    This implementation uses an LDAP database.
    
    .. note::
    
        An instance of this class can be accessed as a property of the Pyramid
        request object, i.e. ``r = request.id_service``.
       
        This property is reified, so it is only evaluated once per request.
       
    :param connection: The :py:class:`jasmin_cloud.ldap.LDAPConnection` to use
    :param settings: The settings dictionary
    """
    def __init__(self, connection, settings):
        self._conn = connection
        self._settings = settings

    def __ldap_to_org(self, entry):
        """
        Converts an ldap entry object to an Organisation object
        """
        suffix = self._settings['ldap.group_suffix']
        # memberUid is not guaranteed to exist by the posixGroup schema
        member_uids = entry.get('memberUid', [])
        # Use a deferred iterable for the members so it is not evaluated until
        # they are used
        return Organisation(
            # cn is guaranteed to exist
            entry['cn'][0].lower().replace(suffix, ''),
            DeferredIterable(lambda: [self.find_user_by_userid(uid) for uid in member_uids])
        )
        
    def __ldap_to_user(self, entry):
        """
        Converts an ldap entry object to a User object
        """
        # Due to the object classes used for users, cn, sn and uid are guaranteed to exist
        cn  = entry['cn'][0]
        sn  = entry['sn'][0]
        uid = entry['uid'][0]
        # First name could be available as gn or givenName, or not at all
        gn = first(entry.get('gn', entry.get('givenName', [])), None)
        # mail and sshPublicKey may or may not exist
        mail    = first(entry.get('mail', []), None)
        ssh_key = first(entry.get('sshPublicKey', []), None)
        # Remove any funny trailing whitespace characters
        if ssh_key:
            ssh_key = ssh_key.strip()
        # Get an iterable for the user's orgs
        # Since we only guarantee iterable, we can just use the Query directly
        suffix = self._settings['ldap.group_suffix']
        filter = f('objectClass=posixGroup') &           \
                   f('cn=*{suffix}', suffix = suffix) &  \
                   f('memberUid={uid}', uid = uid)
        orgs = self._conn.create_query(
            self._settings['ldap.group_base'],
            filter, transform = self.__ldap_to_org
        )
        return User(cn, gn, sn, mail, ssh_key, orgs)
    
    def _find_user_by_filter(self, filter):
        """
        Returns the first user that fulfills the given filter, or ``None`` if one
        does not exist.
        """
        q = self._conn.create_query(
            self._settings['ldap.user_base'],
            filter, transform = self.__ldap_to_user
        )
        return next(iter(q), None)
    
    def find_user_by_userid(self, userid):
        """
        Returns the user with the given ID if one exists, or ``None`` otherwise.
        
        :param userid: The user ID to find
        :returns: A user object or ``None``
        """
        return self._find_user_by_filter(f('uid={}', userid))
    
    def find_user_by_email(self, email):
        """
        Returns the user with the given email address if one exists, or ``None``
        otherwise.
        
        :param email: The email address to search for
        :returns: A user object or ``None``
        """
        return self._find_user_by_filter(f('mail={}', email))
    
    def authenticate_user(self, userid, passwd):
        """
        Attempts to authenticate a user with the given user ID and password.
        
        :param userid: The user ID to authenticate
        :param passwd: The password to authenticate
        :returns: ``True`` on success, ``False`` on failure
        """
        # Build the DN
        user_dn = 'CN={userid},{base}'.format(
            userid = userid, base = self._settings['ldap.user_base']
        )
        return self._conn.authenticate(user_dn, passwd)
    
    def create_user(self, userid, passwd, first_name, surname, email, ssh_key):
        """
        Creates a new user with the given properties.
        
        Returns the created user on success. Any failures should result in an
        exception being raised.
        
        The given properties are validated first, which could result in a
        :py:class:`.validation.ValidationError` being raised containing details
        of the errors.
        
        :param userid: The user ID for the new user
        :param passwd: The password for the new user
        :param first_name: The given name of the new user
        :param surname: The surname of the new user
        :param email: The email address of the new user
        :param ssh_key: The SSH public key of the new user
        :returns: The created user
        """
        raise NotImplementedError
        
    def update_user(self, user, first_name, surname, email, ssh_key):
        """
        Updates an existing user with the given properties.
        
        ``user`` can be the user ID of the user to update or a ``User`` object
        representing the user to update.
        
        Returns the updated user on success. Any failures should result in an exception
        being raised.
        
        The given properties are validated first, which could result in a
        :py:class:`.validation.ValidationError` being raised containing details
        of the errors.
        
        :param user: A user object or the user ID for the user to update
        :param first_name: The updated given name
        :param surname: The updated surname
        :param email: The updated email address
        :param ssh_key: The updated SSH public key
        :returns: The updated user
        """
        # If we haven't got a user object, get one
        if not isinstance(user, User):
            user = self.find_user_by_userid(user)
        if not user:
            raise ValueError('Given user does not exist')
        # Remove leading and trailing whitespace from the SSH key first
        ssh_key = ssh_key.strip()
        # We only validate dirty fields
        dirty = {}
        if user.first_name != first_name:
            dirty['first_name'] = first_name
        if user.surname != surname:
            dirty['surname'] = surname
        if user.email != email:
            dirty['email'] = email
        if user.ssh_key != ssh_key:
            dirty['ssh_key'] = ssh_key
        # If there are no dirty fields, there is nothing to do
        if not dirty:
            return user
        # Validation raises an exception on failure
        validated = validate_user_fields(self, dirty)
        # Get the dn of the entry to modify
        dn = 'CN={},{}'.format(user.userid, self._settings['ldap.user_base'])
        # Build the actual LDAP changes from the user data
        changes = {}
        first_name = validated.get('first_name', first_name)
        surname = validated.get('surname', surname)
        changes['gn'] = (first_name, )
        changes['sn'] = (surname, )
        changes['gecos'] = ("{} {}".format(first_name, surname), )
        changes['mail'] = (validated.get('email', email), )
        changes['sshPublicKey'] = (validated.get('ssh_key', ssh_key), )
        # Apply the changes
        self._conn.update_entry(dn, changes)
        return user._replace(**validated)

    def find_org_by_name(self, name):
        """
        Returns the organisation with the given name if one exists, or ``None`` otherwise.
        
        :param name: The name of the organisation to find
        :returns: An ``Organisation`` object or ``None``
        """
        # Build the filter
        suffix = self._settings['ldap.group_suffix']
        filter = f('objectClass=posixGroup') &                           \
                   f('cn={name}{suffix}', name = name, suffix = suffix)
        q = self._conn.create_query(
            self._settings['ldap.group_base'],
            filter, transform = self.__ldap_to_org
        )
        return next(iter(q), None)
