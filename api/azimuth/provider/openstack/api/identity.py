"""
Module containing service and resource definitions for the OpenStack compute API.
"""

from rackit import RootResource, NestedResource

from .core import (
    Service,
    Resource,
    ResourceManager
)


class IdentityResourceManager(ResourceManager):
    """
    Custom manager for resources in the identity service.
    """
    def extract_next_url(self, data):
        return data.get('links', {}).get('next')


class IdentityResource(Resource):
    """
    Custom resource class for identity resources.
    """
    class Meta:
        manager_cls = IdentityResourceManager


class ApplicationCredential(IdentityResource):
    """
    Resource for accessing application credentials.
    """
    class Meta:
        endpoint = '/application_credentials'


class User(IdentityResource):
    """
    Resource for accessing users.
    """
    class Meta:
        endpoint = '/users'

    application_credentials = NestedResource(ApplicationCredential)


class IdentityService(Service):
    """
    OpenStack service class for the identity service.
    """
    catalog_type = 'identity'
    path_prefix = '/v3'

    users = RootResource(User)

    @property
    def current_user(self):
        return self.users.get(self.session.auth.user_id)
