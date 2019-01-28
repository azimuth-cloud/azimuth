"""
Module implementing an LDAP key store.
"""

from jasmin_ldap import ServerPool, Connection, Query

from .base import KeyStore


class LdapKeyStore(KeyStore):
    """
    Key store implementation that locates keys in LDAP records.

    Args:
        primary: The hostname of the LDAP primary server.
        base_dn: The base DN to search for users.
        replicas: List of hostnames of LDAP read-only replicas.
        user: The DN to use to connect.
        password: The password to use to connect.
    """
    def __init__(self, primary, base_dn, replicas = [], user = '', password = ''):
        # Just store the parameters for the connection. We will create the
        # connection when required.
        self.primary = primary
        self.replicas = replicas
        self.user = user
        self.password = password
        self.base_dn = base_dn

    def get_key(self, username):
        """
        See :py:meth:`.base.KeyStore.get_key`.
        """
        connection = Connection.create(
            ServerPool(self.primary, self.replicas),
            user = self.user, password = self.password
        )
        with connection:
            query = Query(connection, self.base_dn)
            return next(
                iter(query.filter(cn = username).one().get('sshPublicKey', [])),
                None
            )
