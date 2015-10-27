"""
This module contains generic utilities and helpers used by the JASMIN portal.
"""

__author__ = "Matt Pryor"
__copyright__ = "Copyright 2015 UK Science and Technology Facilities Council"


import os, tempfile, subprocess, uuid

from sqlalchemy import types
from sqlalchemy.dialects import postgresql


def validate_ssh_key(ssh_key):
    """
    Verifies that the given value is a valid SSH key.
    
    Returns the key on success, raises ``ValueError`` on failure.
    
    :param ssh_key: The value to test
    :returns: The key on success
    """
    # Strip whitespace and raise an error if that results in an empty value
    ssh_key = ssh_key.strip()
    if not ssh_key:
        raise ValueError('Not a valid SSH key')
    # Check that the SSH key is valid using ssh-keygen
    fd, temp = tempfile.mkstemp()
    with os.fdopen(fd, mode = 'w') as f:
        f.write(ssh_key)
    try:
        # We don't really care about the content of stdout/err
        # We just care if the command succeeded or not...
        subprocess.check_call(
            'ssh-keygen -l -f {}'.format(temp), shell = True,
            stdout = subprocess.DEVNULL, stderr = subprocess.DEVNULL
        )
    except subprocess.CalledProcessError:
        raise ValueError('Not a valid SSH key')
    return ssh_key


class UUIDType(types.TypeDecorator):
    """
    Column type for SQLAlchemy that marshals ``uuid.UUID`` objects.
    
    Uses native ``UUID`` type when it exists (i.e. PostgreSQL), falling back on
    ``CHAR(32)``. 
    """
    #: The underlying SQLAlchemy type
    impl = types.CHAR
    #: The underlying Python type
    python_type = uuid.UUID
    
    def load_dialect_impl(self, dialect):
        """
        Loads the underlying implementation for a dialect.
        """
        if dialect.name == 'postgresql':
            # Use the native UUID type
            return dialect.type_descriptor(postgresql.UUID())
        else:
            # Fallback to CHAR
            return dialect.type_descriptor(types.CHAR(32))

    def process_bind_param(self, value, dialect):
        """
        Process a value received as a bind parameter (i.e. Python -> db).
        """
        if value is None:
            return value
        # Make sure we have a UUID instance
        if not isinstance(value, uuid.UUID):
            try:
                value = uuid.UUID(value)
            except (TypeError, ValueError):
                value = uuid.UUID(bytes=value)
        # For postgresql, just return the string representation
        if dialect.name == 'postgresql':
            return str(value)
        # Otherwise, return the hex value
        return value.hex

    def process_result_value(self, value, dialect):
        """
        Process a value from the database (i.e. db -> Python).
        """
        if value is None:
            return value
        # If the driver has already converted the uuid, we're all good
        if isinstance(value, uuid.UUID):
            return value
        # Otherwise, convert from a string
        return uuid.UUID(value)
