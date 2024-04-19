# Postpone evaluation of annotations to prevent circular dependencies
from __future__ import annotations

import typing as t

from ..cluster_api import dto as capi_dto
from ..cluster_engine import dto as caas_dto
from ..provider import base as cloud_provider
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
        Calculates the resources required to make the specified changes
        to the CaaS cluster.
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
