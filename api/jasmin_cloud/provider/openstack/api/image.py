"""
Module containing service and resource definitions for the OpenStack image API.
"""

from rackit import RootResource

from .core import Service, Resource, ResourceManager


class ImageManager(ResourceManager):
    """
    Custom manager for resources in the image service.
    """
    def extract_next_url(self, data):
        return data.get('next')


class Image(Resource):
    """
    Resource for accessing images.
    """
    class Meta:
        manager_cls = ImageManager
        endpoint = '/images'
        # The image service returns the image data directly when fetching by id
        resource_key = None


class ImageService(Service):
    """
    OpenStack service class for the image service.
    """
    catalog_type = 'image'
    path_prefix = '/v2'

    images = RootResource(Image)
