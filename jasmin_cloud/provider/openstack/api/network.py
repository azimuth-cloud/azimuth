"""
Module containing service and resource definitions for the OpenStack compute API.
"""

from rackit import Endpoint, RootResource

from .core import Service, UnmanagedResource, ResourceManager, Resource


class Quotas(UnmanagedResource):
    """
    Represents the quotas for a project.

    This is not a REST-ful resource, so is unmanaged.
    """
    class Meta:
        endpoint = "/quotas/{project_id}"
        resource_key = "quota"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Interpolate the project id into the path
        self._path = self._path.format(
            project_id = self._connection.session.auth.project_id
        )


class NetworkResourceManager(ResourceManager):
    """
    Custom resource manager for networking resources.

    Handles scoping list queries to the current project.
    """
    def all(self, **params):
        project_id = self.connection.session.auth.project_id
        if project_id:
            params.update(project_id = project_id)
        return super().all(**params)


class NetworkResource(Resource):
    """
    Base class for networking resources.
    """
    class Meta:
        manager_cls = NetworkResourceManager


class FloatingIp(NetworkResource):
    """
    Represents a floating IP.
    """
    class Meta:
        endpoint = "/floatingips"


class Port(NetworkResource):
    """
    Represents a port.
    """
    class Meta:
        endpoint = "/ports"


class Network(NetworkResource):
    """
    Represents a network.
    """
    class Meta:
        endpoint = "/networks"

    def _update_tags(self, tags):
        """
        Update the tags associated with a network.
        """
        conn = self._manager.connection
        conn.api_put("{}/tags".format(self._path), json = dict(tags = tags))


class Subnet(NetworkResource):
    """
    Represents a subnet.
    """
    class Meta:
        endpoint = "/subnets"


class Router(NetworkResource):
    """
    Represents a router.
    """
    class Meta:
        endpoint = "/routers"


class NetworkService(Service):
    """
    OpenStack service class for the network service.
    """
    catalog_type = 'network'
    path_prefix = '/v2.0'
    error_keys = ('NeutronError', 'message')

    quotas = Endpoint(Quotas)
    floatingips = RootResource(FloatingIp)
    ports = RootResource(Port)
    networks = RootResource(Network)
    subnets = RootResource(Subnet)
    routers = RootResource(Router)
