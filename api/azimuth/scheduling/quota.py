# Postpone evaluation of annotations to prevent circular dependencies
from __future__ import annotations

import typing as t

from ..provider import base as cloud_provider
from . import dto


class QuotaChecker:
    """
    Checks platform resource requirements against quota.
    """

    def __init__(self, session: cloud_provider.ScopedSession):
        self._session = session

    def check(
        self,
        future_resources: dto.PlatformResources,
        current_resources: dto.PlatformResources | None = None,
    ) -> tuple[bool, t.Iterable[dto.ProjectedQuota]]:
        """
        Runs a quota check for the given platform resources and returns a tuple
        of (fits, projected_quotas) where "fits" indicates if the changes to the
        platform fit in the remaining quotas and projected_quotas represents the
        new state of the quotas if the changes were applied.
        """
        # Summarise the current and future resource consumption of the platform
        future_summary = future_resources.summarise()
        if current_resources is not None:
            current_summary = current_resources.summarise()
        else:
            current_summary = dto.ResourceSummary.none()
        # Check whether the delta fits within the remaining quota
        projected_quotas = []
        fits = True
        for quota in self._session.quotas():
            future = getattr(future_summary, quota.resource, 0)
            current = getattr(current_summary, quota.resource, 0)
            delta = future - current
            projected_quota = dto.ProjectedQuota(
                quota.resource,
                quota.label,
                quota.units,
                quota.allocated,
                quota.used,
                delta,
                quota.used + delta,
            )
            projected_quotas.append(projected_quota)
            if (
                projected_quota.allocated >= 0
                and projected_quota.projected > projected_quota.allocated
            ):
                fits = False
        return fits, projected_quotas
