import dataclasses
import typing as t


@dataclasses.dataclass(frozen = True)
class ProjectedQuota:
    """
    Represents a projected quota after a change.
    """
    #: The resource that the quota is for
    resource: str
    #: The human-readable label for the quota resource
    label: str
    #: The units of the quota. For a unit-less quota, use ``None``.
    units: t.Optional[str]
    #: The amount of the resource that has been allocated
    allocated: int
    #: The current amount of resource being consumed
    current: int
    #: The delta that will result from the change
    delta: int
    #: The projected consumption after the change
    projected: int
