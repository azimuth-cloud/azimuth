"""
Generic ldap functionality and integration with Pyramid
"""

__author__ = "Matt Pryor"
__copyright__ = "Copyright 2015 UK Science and Technology Facilities Council"


from collections.abc import Iterable
import ldap3
import ldap3.utils


def setup(config, settings):
    """
    Given a pyramid configurator and a settings dictionary, configure LDAP
    access for the app
    
    This method exposes an `ldap_connection` property on the request, which is
    an `ldap3.Connection` object that is opened when first requested and kept
    open for the duration of the request
    """
    
    def ldap_authenticate(request, user_dn, password):
        # Attempts to authenticate the user with the given dn and password
        # Returns true on success, false otherwise
        try:
            ldap3.Connection(request.registry.settings['ldap.server'],
                             user = user_dn, password = password,
                             auto_bind = ldap3.AUTO_BIND_TLS_BEFORE_BIND,
                             raise_exceptions = True).unbind()
            return True
        except ldap3.LDAPOperationResult:
            # If the operation fails, treat that as an auth failure
            return False
        
    config.add_request_method(ldap_authenticate)
            
    
    def ldap_connection(request):
        # Opens an LDAP connection for the request using the specified settings
        return ldap3.Connection(request.registry.settings['ldap.server'],
                                user = request.registry.settings['ldap.bind_dn'],
                                password = request.registry.settings['ldap.bind_pass'],
                                auto_bind = ldap3.AUTO_BIND_TLS_BEFORE_BIND,
                                raise_exceptions = True)
    
    config.add_request_method(ldap_connection, reify = True)
    
    return config


_char_map = { '*': '\\2A', '(': '\\28', ')': '\\29', '\\': '\\5C', '\0': '\\00' }

def escape_filter_param(value):
    """
    Escapes a parameter value for use in an LDAP filter
    """
    if isinstance(value, bytes):
        return ldap3.utils.conv.escape_bytes(value)
    else:
        if not isinstance(value, str):
            value = str(value)
        return ''.join(_char_map.get(c, c) for c in value)
    
    
class Filter:
    """
    Class representing a filter for an LDAP search query 
    """
    def __init__(self, filter_str, **params):
        # Interpolate the string with escaped parameter values
        if params:
            escaped = { k: escape_filter_param(v) for k, v in params.items() }
            self._filter_str = filter_str.format(**escaped)
        else:
            self._filter_str = filter_str
        self._filter_str = '(' + self._filter_str + ')'
        
    def __repr__(self):
        """
        Returns the filter string for this filter
        """
        return self._filter_str
        
    def __and__(self, filter):
        """
        Combines this filter and the given filter using AND
        """
        return Filter('&{0}{1}'.format(self, filter))
    
    def __or__(self, filter):
        """
        Combines this filter and the given filter using OR
        """
        return Filter('|{0}{1}'.format(self, filter))
    
    def __invert__(self):
        """
        Inverts this filter using NOT
        """
        return Filter('!{0}'.format(self))


class Query(Iterable):
    """
    Lazy LDAP search query that can be iterated directly
    
    The query is not executed until the first time that data is requested
    The result is then cached in memory until execute is called again
    
    A callback can be used to transform the values as they are emitted
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
        Executes the query (or re-executes if it has already been executed) and returns self
        """
        self._conn.search(self._base_dn, str(self._filter),
                          search_scope = self._scope, attributes = self._attrs)
        self._results = self._conn.entries
        return self
    
    def __iter__(self):
        if self._results is None:
            self.execute()
        for result in self._results:
            yield self._transform(result)
    