"""
Module containing service and resource definitions for the OpenStack compute API.
"""

from rackit import Endpoint, RootResource

from .core import Service, UnmanagedResource, Resource


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


class FloatingIp(Resource):
    """
    Represents a floating IP.
    """
    class Meta:
        endpoint = "/floatingips"


class Port(Resource):
    """
    Represents a port.
    """
    class Meta:
        endpoint = "/ports"


class Network(Resource):
    """
    Represents a network.
    """
    class Meta:
        endpoint = "/networks"


class Router(Resource):
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
    routers = RootResource(Router)
