"""
Django models for the ``jasmin_cloud`` app.
"""

from django.conf import settings
from django.db import models

from picklefield.fields import PickledObjectField


class CloudSession(models.Model):
    """
    Model to allow the association of a :py:class:`~.provider.base.UnscopedSession`
    with a user.

    This is done by pickling the session using a PickledObjectField.
    """
    #: The user that owns the session
    user = models.OneToOneField(settings.AUTH_USER_MODEL)
    #: The :py:class:`~.provider.base.UnscopedSession` object
    session = PickledObjectField()
