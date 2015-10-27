"""
This module contains generic utilities and helpers used by the JASMIN portal.
"""

__author__ = "Matt Pryor"
__copyright__ = "Copyright 2015 UK Science and Technology Facilities Council"


import os, tempfile, subprocess


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
