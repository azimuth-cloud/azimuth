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
    config.add_request_method(ldap_connection, reify = True)


def ldap_authenticate(request, user_dn, password):
    """
    Attempts to authenticate the user with the given DN and password with the
    LDAP database specified by the request settings.
    
    :param request: The Pyramid request
    :param user_dn: The DN of the user to authenticate
    :param password: The password to use for authentication
    :returns: ``True`` on success, ``False`` on failure
    """
    try:
        ldap3.Connection(request.registry.settings['ldap.server'],
                         user = user_dn, password = password,
                         auto_bind = ldap3.AUTO_BIND_TLS_BEFORE_BIND,
                         raise_exceptions = True).unbind()
        return True
    except ldap3.LDAPOperationResult:
        # If the operation fails, treat that as an auth failure
        return False


def ldap_connection(request):
    """
    Opens a connection to the LDAP database specified by the request settings.
    
    .. note::
    
        This function should be accessed as a property of the Pyramid request object,
        i.e. ``conn = request.ldap_connection``.
       
        This property is reified, so there is only one LDAP connection per request.
       
    :param request: The Pyramid request
    :returns: An LDAP connection
    :rtype: ``ldap3.Connection``
    """
    return ldap3.Connection(request.registry.settings['ldap.server'],
                            user = request.registry.settings['ldap.bind_dn'],
                            password = request.registry.settings['ldap.bind_pass'],
                            auto_bind = ldap3.AUTO_BIND_TLS_BEFORE_BIND,
                            raise_exceptions = True)


_char_map = { '*': '\\2A', '(': '\\28', ')': '\\29', '\\': '\\5C', '\0': '\\00' }
def _escape_filter_param(value):
    """
    Escapes a parameter value for use in an LDAP filter.
    """
    if isinstance(value, bytes):
        return ldap3.utils.conv.escape_bytes(value)
    else:
        if not isinstance(value, str):
            value = str(value)
        return ''.join(_char_map.get(c, c) for c in value)
    
    
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
        from jasmin_portal.ldap import Filter as f
       
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
    def __init__(self, filter_str, *args, **kwargs):
        if args or kwargs:
            # Escape the arguments for use in LDAP filters
            args_e = [ _escape_filter_param(v) for v in args ]
            kwargs_e = { k: _escape_filter_param(v) for k, v in kwargs.items() }
            # Interpolate the filter string the escaped values
            self._filter_str = filter_str.format(*args_e, **kwargs_e)
        else:
            self._filter_str = filter_str
        self._filter_str = '(' + self._filter_str + ')'
        
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
    """Query(conn, base_dn, filter, scope = ldap3.SEARCH_SCOPE_SINGLE_LEVEL, attrs = ldap3.ALL_ATTRIBUTES, transform = lambda x: x)
    
    Represents an LDAP search query.
    
    The query can be iterated over directly, but is not executed until the first
    time that data is requested. The query result is then cached in memory and
    used for future iterations unless ``execute`` is called again.
    
    By default, the items returned on iteration will be
    `ldap3 Entry objects <https://ldap3.readthedocs.org/abstraction.html#entry>`_.
    However, a transform function can be applied - this function should take
    an ldap3 Entry and return another object, which will then be returned during
    iteration.
    
    :param conn: ``ldap3.Connection`` to use
    :param base_dn: DN to use as the base for the LDAP search
    :param filter: Filter to use for the search
    :param scope: Scope for the search (see
                  `the ldap3 docs <https://ldap3.readthedocs.org/searches.html>`_
                  for allowed values)
    :param attrs: Attributes to return during the search (see
                  `the ldap3 docs <https://ldap3.readthedocs.org/searches.html>`_
                  for allowed values)
    :param transform: Transform function to use
    """
    def __init__(self, conn, base_dn, filter, 
                       scope = ldap3.SEARCH_SCOPE_SINGLE_LEVEL,
                       attrs = ldap3.ALL_ATTRIBUTES,
                       transform = lambda x: x):
        self._conn = conn
        self._base_dn = base_dn
        self._filter = filter
        self._scope = scope
        self._attrs = attrs
        self._transform = transform
        self._results = None
    
    def execute(self):
        """
        Executes the query (or re-executes if it has already been executed).
        
        :returns: ``self``
        """
        self._conn.search(self._base_dn, str(self._filter),
                          search_scope = self._scope, attributes = self._attrs)
        self._results = list(map(self._transform, self._conn.entries or []))
        return self
    
    def __iter__(self):
        if self._results is None:
            self.execute()
        yield from self._results
    