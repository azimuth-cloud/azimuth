"""
This module contains generic utilities and helpers used by the JASMIN portal.
"""

__author__ = "Matt Pryor"
__copyright__ = "Copyright 2015 UK Science and Technology Facilities Council"


import os, tempfile, subprocess, re
from functools import reduce
from collections import Iterable


def getattrs(obj, attrs, default):
    """
    Similar to ``getattr``, but allows a list of attribute names to be resolved
    in a chained manner.
    
    If an attribute cannot be resolved at any point in the chain, the default is
    returned.
    
    :param obj: An object to start resolving names from
    :param attrs: List of names to resolve
    :param default: Default value if attribute resolution fails at any stage
    :returns: The value at the end of the chain if resolution is successful,
              otherwise the default
    """
    try:
        return reduce(getattr, attrs, obj)
    except (KeyError, AttributeError):
        return default
    

# Lifted from formencode via validino
_usernameRE = re.compile(r"^[^ \t\n\r@<>()]+$", re.I)
_domainRE = re.compile(r"^[a-z0-9][a-z0-9\.\-_]*\.[a-z]+$", re.I)

def validate_email(email):
    """
    Verifies that the given value is a valid email address.
    
    Returns the value on success, raises ``ValueError`` on failure.
    
    :param email: The value to test
    :returns: The value on success
    """
    try:
        username, domain = email.split('@', 1)
    except ValueError:
        raise ValueError('Value is not a valid email address')
    if not _usernameRE.match(username):
        raise ValueError('Value is not a valid email address')
    if not _domainRE.match(domain):
        raise ValueError('Value is not a valid email address')
    return email
    
    
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
        raise ValueError('SSH key cannot be empty')
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
        raise ValueError('Value is not a valid SSH key')
    return ssh_key
    
    
class DeferredIterable(Iterable):
    """
    Iterable decorator where the creation of the underlying iterable is deferred
    until data is first requested.
    
    :param factory: Callable that creates the underlying iterable. Should take no
                    arguments and return an iterable
    """
    def __init__(self, factory):
        self._factory = factory
        self._underlying = None
        
    def __iter__(self):
        if self._underlying is None:
            self._underlying = self._factory()
            self._factory = None
        return iter(self._underlying)
    