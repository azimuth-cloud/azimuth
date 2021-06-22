"""
Module containing service and resource definitions for the OpenStack compute API.
"""

from rackit import RootResource, RelatedResource

from .core import Service, Resource
from .orchestration import Stack


class ContainerInfraResource(Resource):
    """
    Base class for resources in the container infrastructure management service.
    """
    class Meta:
        primary_key_field = 'uuid'
        resource_key = None


class ClusterTemplate(ContainerInfraResource):
    """
    Resource for COE cluster templates.
    """
    class Meta:
        endpoint = '/clustertemplates'


class Cluster(ContainerInfraResource):
    """
    Resource for COE clusters.
    """
    class Meta:
        endpoint = "/clusters"
        # The list endpoint does not include all the cluster attributes
        list_partial = True

    cluster_template = RelatedResource(ClusterTemplate, 'cluster_template_id')
    stack = RelatedResource(Stack, 'stack_id')


class ContainerInfraService(Service):
    """
    OpenStack service class for the container infrastructure management service.
    """
    name = 'coe'
    catalog_type = 'container-infra'
    path_prefix = '/v1'

    cluster_templates = RootResource(ClusterTemplate)
    clusters = RootResource(Cluster)
