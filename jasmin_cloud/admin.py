"""
Django admin declarations for the JASMIN Cloud Portal.
"""

from django.contrib import admin

from .models import CloudSession


@admin.register(CloudSession)
class CloudSessionAdmin(admin.ModelAdmin):
    """
    Admin declarations for the :py:class:`~.models.CloudSession` model.
    """
    list_display = ('user', 'session')
    fields = ('user', 'session')
    readonly_fields = ('session', )
