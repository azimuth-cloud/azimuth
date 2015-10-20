"""
This module provides some generic LDAP utilities and LDAP integration with Pyramid
used by the JASMIN portal.
"""

__author__ = "Matt Pryor"
__copyright__ = "Copyright 2015 UK Science and Technology Facilities Council"


from collections.abc import Iterable
import ldap3
import ldap3.utils


def includeme(config):
    """
    Configures the Pyramid application for LDAP access.
    
    :param config: Pyramid configurator
    """
    def ldap_connection(request):
        return LDAPConnection(request.registry.settings)
    config.add_request_method(ldap_connection, reify = True)
    
    
class LDAPConnection:
    """
    Class representing an LDAP connection and the operations that can be performed.
    
    .. note::
    
        An instance of this class can be accessed as a property of the Pyramid
        request object, i.e. ``r = request.ldap_connection``.
       
        This property is reified, so it is only evaluated once per request.
        
    :param settings: The settings dictionary
    """
    def __init__(self, settings):
        self._settings = settings
        # The underlying ldap3 connection is opened the first time it is requested
        self._conn = None

    def authenticate(self, user_dn, password):
        """
        Attempts to authenticate the user with the given DN and password with the
        LDAP database specified by the settings given in the constructor.
        
        :param user_dn: The DN of the user to authenticate
        :param password: The password to use for authentication
        :returns: ``True`` on success, ``False`` on failure
        """
        try:
            ldap3.Connection(
                self._settings['ldap.server'],
                user = user_dn, password = password,
                auto_bind = ldap3.AUTO_BIND_TLS_BEFORE_BIND,
                raise_exceptions = True
            ).unbind()
            return True
        except ldap3.LDAPOperationResult:
            # If the operation fails, treat that as an auth failure
            return False

    def __connection(self):
        """
        Returns an open connection to the LDAP database, creating it if it is
        not already open.
        """
        if self._conn is None:
            self._conn = ldap3.Connection(
                self._settings['ldap.server'],
                user = self._settings['ldap.bind_dn'],
                password = self._settings['ldap.bind_pass'],
                auto_bind = ldap3.AUTO_BIND_TLS_BEFORE_BIND,
                raise_exceptions = True
            )
        return self._conn
    
    def create_query(self, base_dn, filter, transform = lambda x: x):
        """create_query(base_dn, filter, transform = lambda x: x)
    
        Creates a new :py:class:`Query` using this connection.
        
        :param base_dn: DN to use as the base for the LDAP search
        :param filter: :py:class:`Filter` to use for the search
        :param transform: Transform function to use
        :returns: A :py:class:`Query` object
        """
        return Query(self.__connection(), base_dn, filter, transform)
    
    def update_entry(self, dn, attributes):
        """
        Uses this connection to update the entry with the given DN with the given
        attributes.
        
        Attributes should be a mapping of field name to an iterable (usually a list)
        of values.
        
        :param dn: The DN of the entry to update
        :param attributes: The new values of the attributes
        :returns: ``True`` on success
        """
        # Make sure the correct operation is applied
        return self.__connection().modify(
            dn, { k : (ldap3.MODIFY_REPLACE, v) for k, v in attributes.items() }
        )


class Filter:
    """
    Represents a filter for an LDAP search query.
    
    Filter expressions are created by specifying a filter string with placeholders
    where arguments should be inserted. Under the hood, this uses ``str.format``,
    except that the argument values will be properly escaped before insertion.
    
    Filter strings should be given **without** leading or trailing parentheses.
    
    Some simple documentation for filter strings can be found on the
    `CentOS website <https://www.centos.org/docs/5/html/CDS/ag/8.0/Finding_Directory_Entries-LDAP_Search_Filters.html>`_.
    
    Examples:
    
    ::
    
        # Import Filter with a shorter name to facilitate query construction
        from jasmin_cloud.ldap import Filter as f
       
        # Exact match
        f('uid={}', 'bob')
        f('uid={uid}', uid = 'bob')
       
        # Substring match
        f('cn=*{dept}*', dept = 'Computing')
       
        # Presence of attribute
        f('email=*')
    
    Rather than using the cumbersome prefix syntax for compound filters, e.g.
    ``(&(uid=bob)(|(!(email=*))(gn=*))``, filter expressions can be combined using
    the operators ``&`` (AND), ``|`` (OR) and ``~`` (NOT).
    
    For example, the above expression could be written as:
    
    ::
    
        f('uid={}', 'bob') & ( ~f('email=*') | f('gn=*') )
    """
    __char_map = { '*': '\\2A', '(': '\\28', ')': '\\29', '\\': '\\5C', '\0': '\\00' }
    
    def __init__(self, filter_str, *args, **kwargs):
        if args or kwargs:
            # Escape the arguments for use in LDAP filters
            args_e = [ self.__escape_filter_param(v) for v in args ]
            kwargs_e = { k: self.__escape_filter_param(v) for k, v in kwargs.items() }
            # Interpolate the filter string the escaped values
            self._filter_str = filter_str.format(*args_e, **kwargs_e)
        else:
            self._filter_str = filter_str
        self._filter_str = '(' + self._filter_str + ')'
    
    def __escape_filter_param(self, value):
        """
        Escapes a parameter value for use in an LDAP filter.
        """
        if isinstance(value, bytes):
            return ldap3.utils.conv.escape_bytes(value)
        else:
            if not isinstance(value, str):
                value = str(value)
            return ''.join(self.__char_map.get(c, c) for c in value)
        
    def __repr__(self):
        """
        Returns the filter string for this filter
        """
        return self._filter_str
        
    def __and__(self, other):
        """
        Combines this filter and the given filter using AND
        """
        return Filter('&{0}{1}'.format(self, other))
    
    def __or__(self, other):
        """
        Combines this filter and the given filter using OR
        """
        return Filter('|{0}{1}'.format(self, other))
    
    def __invert__(self):
        """
        Inverts this filter using NOT
        """
        return Filter('!{0}'.format(self))


class Query(Iterable):
    """Query(conn, base_dn, filter, transform = lambda x: x)
    
    Represents an LDAP search query.
    
    The query can be iterated over directly, but is not executed until the first
    time that data is requested. The query result is then cached in memory and
    used for future iterations unless ``execute`` is called again.
    
    By default, the items returned on iteration will be mappings of field names
    to arrays of values. However, a transform function can be applied - this
    function should take a field-to-values mapping and return another object,
    which will then be returned during iteration.
    
    :param conn: ``ldap3.Connection`` to use
    :param base_dn: DN to use as the base for the LDAP search
    :param filter: Filter to use for the search
    :param transform: Transform function to use
    """
    def __init__(self, conn, base_dn, filter, transform = lambda x: x):
        self._conn = conn
        self._base_dn = base_dn
        self._filter = filter
        self._transform = transform
        self._results = None
        
    def __map(self, entry):
        """
        Takes an LDAP entry, extracts the attributes and dn and applies the transform.
        """
        return self._transform(dict(entry['attributes'], dn = entry['dn']))
    
    def execute(self):
        """
        Executes the query (or re-executes if it has already been executed).
        
        :returns: ``self``
        """
        self._conn.search(self._base_dn, str(self._filter),
                          search_scope = ldap3.SEARCH_SCOPE_SINGLE_LEVEL,
                          attributes = ldap3.ALL_ATTRIBUTES)
        self._results = list(map(self.__map, self._conn.response or []))
        return self
    
    def __iter__(self):
        if self._results is None:
            self.execute()
        yield from self._results
    