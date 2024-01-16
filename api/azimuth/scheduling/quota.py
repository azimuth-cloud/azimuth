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
        resources: dto.PlatformResources
    ) -> tuple[bool, t.Iterable[dto.ProjectedQuota]]:
        """
        Runs a quota check for the given platform resources and returns a tuple
        of (bool, new quotas) where the bool indicates if the platform fits in the
        available space and the new quotas represent the new state of the quotas
        if the platform was provisioned.
        """
        summary = resources.summarise()
        projected_quotas = []
        fits = True
        for quota in self._session.quotas():
            delta = getattr(summary, quota.resource, 0)
            projected_quota = dto.ProjectedQuota(
                quota.resource,
                quota.label,
                quota.units,
                quota.allocated,
                quota.used,
                delta,
                quota.used + delta
            )
            projected_quotas.append(projected_quota)
            if (
                projected_quota.allocated >= 0 and
                projected_quota.projected > projected_quota.allocated
            ):
                fits = False
        return fits, projected_quotas
