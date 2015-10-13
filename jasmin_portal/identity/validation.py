"""
This module provides contains validation schemas and custom validators for use
with the identity module. 
"""

__author__ = "Matt Pryor"
__copyright__ = "Copyright 2015 UK Science and Technology Facilities Council"


from types import MappingProxyType

import voluptuous as v

from jasmin_portal.util import validate_email, validate_ssh_key


class ValidationError(Exception):
    """
    Exception that is raised when an exception occurs during validation.
    
    :param errors: A dictionary mapping field names to a list of errors for that
                    field.
    """
    def __init__(self, errors):
        self.__errors = errors
        
    @property
    def errors(self):
        """
        A dictionary where each key is a field name and each value is a list of
        the errors for that field.
        """
        return MappingProxyType(self.__errors)


def __unique_userid(id_service):
    """
    Returns a validation function that uses the given id service to check the
    uniqueness of a username.
    """
    def f(value):
        if id_service.find_user_by_userid(value):
            raise v.Invalid('Username is already in use')
        return value
    return f


def __unique_email(id_service):
    """
    Returns a validation function that uses the given id service to check the
    uniqueness of an email.
    """
    def f(value):
        if id_service.find_user_by_email(value):
            raise v.Invalid('Email address is already in use')
        return value
    return f


def __with_msg(f, msg = None):
    """
    Returns a validation functions that converts ``ValueError``s to
    ``voluptuous.Invalid`` while either overriding the message if given or retaining
    the error message from the value error.
    """
    def g(value):
        try:
            return f(value)
        except ValueError as e:
            raise v.Invalid(msg or str(e))
    return g
        

def validate_user_fields(id_service, fields):
    """
    Validates and converts the given fields against what is expected for a user.
    
    Not all fields required for a user must be present, but unexpected fields are
    an error.
    
    Returns the converted and validated fields on success, raises
    ``voluptuous.Invalid`` on failure.
    
    :param id_service: The id service to use for uniqueness checks
    :param fields: Dictionary of fields to validate
    :returns: The converted, validated fields on success  
    """
    # Build the voluptuous schema we will use to validate
    # IsTrue is used in combination with str to rule out empty strings
    schema = v.Schema({
        'userid' : v.All(
            __with_msg(str),
            v.Match('^[a-zA-Z0-9_]+$', 'Username must use only alphanumeric and _ characters'),
            __unique_userid(id_service)
        ),
        'first_name' : v.All(__with_msg(str), v.IsTrue('First name is required')),
        'surname' : v.All(__with_msg(str), v.IsTrue('Surname is required')),
        'email' : v.All(
            __with_msg(str), __with_msg(validate_email), __unique_email(id_service)
        ),
        'ssh_key' : v.All(
            __with_msg(str), v.IsTrue('SSH key is required'), __with_msg(validate_ssh_key)
        ),
    }, required = False, extra = v.PREVENT_EXTRA)
    # Convert the voluptuous error into our own error class
    try:
        return schema(fields)
    except v.MultipleInvalid as e:
        # Collect the errors for each field before raising our own exception
        errors = {}
        for e in e.errors:
            errors.setdefault(e.path[0], []).append(e.error_message)
        raise ValidationError(errors)
