"""
Module containing service and resource definitions for the OpenStack image API.
"""

from rackit import RootResource

from .core import Resource, Service


class Stack(Resource):
    """
    Resource for accessing stacks.
    """

    class Meta:
        endpoint = "/stacks"


class OrchestrationService(Service):
    """
    OpenStack service class for the orchestration service.
    """

    catalog_type = "orchestration"
    path_prefix = "/v1/{project_id}"

    stacks = RootResource(Stack)
