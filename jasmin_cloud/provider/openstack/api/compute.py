"""
Module containing service and resource definitions for the OpenStack compute API.
"""

from rackit import RootResource, NestedResource, EmbeddedResource, Endpoint

from .core import (
    Service,
    UnmanagedResource,
    Resource,
    ResourceWithDetail
)
from .image import Image


class Flavor(ResourceWithDetail):
    """
    Resource for accessing flavors.
    """
    class Meta:
        endpoint = '/flavors'
        aliases = dict(
            is_disabled = 'OS-FLV-DISABLED:disabled'
        )


class Keypair(Resource):
    """
    Resource for a keypair.
    """
    class Meta:
        endpoint = '/os-keypairs'
        resource_list_key = 'keypairs'
        primary_key_field = 'name'


class VolumeAttachment(Resource):
    """
    Resource for a nested resource.
    """
    class Meta:
        endpoint = "/os-volume_attachments"
        resource_list_key = "volumeAttachments"
        resource_key = "volumeAttachment"
        aliases = dict(
            server_id = 'serverId',
            volume_id = 'volumeId'
        )


class Server(ResourceWithDetail):
    """
    Resource for a server.
    """
    class Meta:
        endpoint = '/servers'
        aliases = dict(
            image_id = 'imageRef',
            flavor_id = 'flavorRef',
            task_state = 'OS-EXT-STS:task_state',
            power_state = 'OS-EXT-STS:power_state',
            attached_volumes = 'os-extended-volumes:volumes_attached'
        )
        defaults = dict(
            fault = dict
        )

    flavor = EmbeddedResource(Flavor)
    image = EmbeddedResource(Image)
    volume_attachments = NestedResource(VolumeAttachment)

    def start(self):
        self._action('action', { 'os-start': None })

    def stop(self):
        self._action('action', { 'os-stop': None })

    def reboot(self, reboot_type):
        self._action('action', { 'reboot': { 'type': reboot_type } })


class AbsoluteLimits(UnmanagedResource):
    """
    Represents the absolute limits for a project.
    """
    class Meta:
        aliases = dict(
            total_cores = 'maxTotalCores',
            total_cores_used = 'totalCoresUsed',
            total_ram = 'maxTotalRAMSize',
            total_ram_used = 'totalRAMUsed',
            instances = 'maxTotalInstances',
            instances_used = 'totalInstancesUsed'
        )


class Limits(UnmanagedResource):
    """
    Represents the limits for a project.

    This is not a REST-ful resource, so is unmanaged.
    """
    class Meta:
        endpoint = "/limits"

    absolute = EmbeddedResource(AbsoluteLimits)


class ComputeService(Service):
    """
    OpenStack service class for the compute service.
    """
    catalog_type = 'compute'
    path_prefix = '/v2.1'

    flavors = RootResource(Flavor)
    keypairs = RootResource(Keypair)
    servers = RootResource(Server)
    limits = Endpoint(Limits)
