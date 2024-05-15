# Postpone evaluation of annotations to prevent circular dependencies
from __future__ import annotations

import typing as t

from ..cluster_api import dto as capi_dto
from ..cluster_engine import dto as caas_dto
from ..provider import base as cloud_provider, dto as provider_dto
from . import dto


class CaaSClusterCalculator:
    """
    Calculates the resources required for a CaaS cluster.
    """
    def __init__(self, session: cloud_provider.ScopedSession):
        self._session = session

    def calculate(
        self,
        cluster_type: caas_dto.ClusterType,
        parameter_values: dict[str, t.Any]
    ) -> dto.PlatformResources:
        """
        Calculates the resources required to make the specified CaaS cluster.
        """
        resources = dto.PlatformResources()
        for parameter in cluster_type.parameters:
            parameter_value = parameter_values.get(parameter.name)
            if not parameter_value:
                continue
            # Both cloud.size and cloud.volume_size support a count variable option
            # that says how many of the resources will be created
            # If not given, the default is one
            count_parameter = parameter.options.get("count_parameter")
            if count_parameter:
                count = parameter_values.get(count_parameter, 1)
            else:
                count = 1
            if parameter.kind == "cloud.size":
                parameter_value = self._session.find_size(parameter_value)
                resources.add_machines(count, parameter_value)
            elif parameter.kind == "cloud.volume_size":
                resources.add_volumes(count, parameter_value)
            # NOTE(mkjpryor)
            # The cloud.volume and cloud.ip kinds represent resources that have
            # already been allocated, so they do not need to be accounted for
            # in any quota calculations
        return resources


class KubernetesNodeGroupSpec(t.TypedDict):
    """
    Spec for a Kubernetes node group.
    """
    name: str
    machine_size: provider_dto.Size
    autoscale: bool
    count: t.Optional[int]
    min_count: t.Optional[int]
    max_count: t.Optional[int]


class KubernetesClusterCalculator:
    """
    Calculates the resources required for a Kubernetes cluster.
    """
    def __init__(self, session: cloud_provider.ScopedSession):
        self._session = session

    def calculate(
        self,
        template: capi_dto.ClusterTemplate,
        control_plane_size: provider_dto.Size,
        node_groups: t.List[KubernetesNodeGroupSpec],
        monitoring_enabled: bool,
        monitoring_metrics_volume_size: int,
        monitoring_logs_volume_size: int,
        **kwargs
    ) -> dto.PlatformResources:
        """
        Calculates the resources required to make the specified Kubernetes cluster.
        """
        resources = dto.PlatformResources()
        # First, deal with the control plane
        resources.add_machines(template.control_plane_count, control_plane_size)
        if template.etcd_volume_size > 0:
            resources.add_volumes(
                template.control_plane_count,
                template.etcd_volume_size
            )
        if template.control_plane_root_volume_size > 0:
            resources.add_volumes(
                template.control_plane_count,
                template.control_plane_root_volume_size
            )
        # Next, the node groups
        for ng in node_groups:
            # When autoscaling, make sure there is enough space for the max size of the cluster
            ng_count = ng["max_count"] if ng["autoscale"] else ng["count"]
            resources.add_machines(ng_count, ng["machine_size"])
            if template.node_group_root_volume_size > 0:
                resources.add_volumes(ng_count, template.node_group_root_volume_size)
        # Add the monitoring volumes
        # There is always an additional volume of 10GB for alertmanager that isn't customisable
        if monitoring_enabled:
            resources.add_volumes(1, 10)
            resources.add_volumes(1, monitoring_metrics_volume_size)
            resources.add_volumes(1, monitoring_logs_volume_size)
        # NOTE(mkjpryor)
        # The ingress controller IP is pre-allocated, so we don't need to account for it here
        return resources
