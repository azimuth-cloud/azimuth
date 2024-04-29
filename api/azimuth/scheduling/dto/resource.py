import dataclasses
import typing as t

from ...provider import dto as cloud_dto


@dataclasses.dataclass(frozen = True)
class ResourceSummary:
    """
    Represents a summary of resource.
    """
    #: The number of machines consumed by the platform
    machines: int
    #: The number of volumes consumed by the platform
    volumes: int
    #: The number of external IPs consumed by the platform
    external_ips: int
    #: The number of CPUs consumed by the platform
    cpus: int
    #: The amount of RAM (in MB) consumed by the platform
    ram: int
    #: The amount of storage (in GB) consumed by the platform
    storage: int

    def __post_init__(self):
        assert self.machines >= 0
        assert self.volumes >= 0
        assert self.external_ips >= 0
        assert self.cpus >= 0
        assert self.ram >= 0
        assert self.storage >= 0

    @classmethod
    def none(cls):
        """
        Creates a resource summary that consumes no resources.
        """
        return cls(0, 0, 0, 0, 0, 0)


@dataclasses.dataclass(frozen = True)
class MachineResources:
    """
    Represents the resources for one or more machines.
    """
    #: The number of machines required at this size
    count: int
    #: The size of the machines
    size: cloud_dto.Size

    def __post_init__(self):
        assert self.count > 0


@dataclasses.dataclass(frozen = True)
class VolumeResources:
    """
    Represents the resources for one or more volumes.
    """
    #: The number of volumes required at this size
    count: int
    #: The size of the volumes (in GB)
    size: int

    def __post_init__(self):
        assert self.count > 0
        assert self.size > 0


class PlatformResources:
    """
    Represents the overall resources consumed by a platform.
    """
    def __init__(self):
        # Machine requirements, indexed by size id so we can aggregate
        self._machine_requirements: dict[str, MachineResources] = {}
        self._volume_requirements: list[VolumeResources] = []
        self._external_ips: int = 0

    def machines(self) -> t.Iterable[MachineResources]:
        """
        Returns the machine requirements for the platform.
        """
        return self._machine_requirements.values()
    
    def volumes(self) -> t.Iterable[VolumeResources]:
        """
        Returns the volume requirements for the platform.
        """
        return iter(self._volume_requirements)
    
    def external_ips(self) -> int:
        """
        Returns the number of external IPs required for the platform.
        """
        return self._external_ips
    
    def add_machines(self, count: int, size: cloud_dto.Size):
        """
        Adds a requirement for machines to the platform requirements.
        """
        assert count > 0
        current_req = self._machine_requirements.get(size.id)
        current_count = current_req.count if current_req else 0
        self._machine_requirements[size.id] = MachineResources(
            current_count + count,
            size
        )
    
    def add_volumes(self, count: int, size: int):
        """
        Adds a requirement for volumes to the platform requirements.
        """
        assert count > 0
        assert size > 0
        self._volume_requirements.append(VolumeResources(count, size))

    def add_external_ips(self, count: int):
        """
        Adds a requirement for external IPs to the platform requirements.
        """
        assert count > 0
        self._external_ips = self._external_ips + count
    
    def summarise(self) -> ResourceSummary:
        """
        Returns an overall summary of the platform requirements in raw units.
        """
        return ResourceSummary(
            sum(req.count for req in self._machine_requirements.values()),
            sum(req.count for req in self._volume_requirements),
            self._external_ips,
            sum(
                (req.size.cpus * req.count)
                for req in self._machine_requirements.values()
            ),
            sum(
                (req.size.ram * req.count)
                for req in self._machine_requirements.values()
            ),
            sum(
                (req.size * req.count)
                for req in self._volume_requirements
            )
        )
