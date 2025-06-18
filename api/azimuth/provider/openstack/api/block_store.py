"""
Module containing service and resource definitions for the OpenStack compute API.
"""

from rackit import EmbeddedResource, Endpoint, RootResource

from .core import ResourceWithDetail, Service, UnmanagedResource


class AbsoluteLimits(UnmanagedResource):
    """
    Represents the absolute limits for a project.
    """
    class Meta:
        aliases = dict(
            total_volume_gigabytes = 'maxTotalVolumeGigabytes',
            total_gigabytes_used = 'totalGigabytesUsed',
            volumes = 'maxTotalVolumes',
            volumes_used = 'totalVolumesUsed'
        )


class Limits(UnmanagedResource):
    """
    Represents the limits for a project.

    This is not a REST-ful resource, so is unmanaged.
    """
    class Meta:
        endpoint = "/limits"

    absolute = EmbeddedResource(AbsoluteLimits)


class Volume(ResourceWithDetail):
    """
    Resource for accessing flavors.
    """
    class Meta:
        endpoint = '/volumes'


class BlockStoreService(Service):
    """
    OpenStack service class for the block store service.
    """
    name = 'block_store'
    catalog_type = 'volumev3'
    path_prefix = '/v3/{project_id}'

    limits = Endpoint(Limits)
    volumes = RootResource(Volume)
