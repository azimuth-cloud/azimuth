import dataclasses
import datetime
import json


@dataclasses.dataclass(frozen = True)
class PlatformSchedule:
    """
    Represents a schedule for a platform.
    """
    #: The end time for the platform
    end_time: datetime.datetime

    def to_json(self) -> str:
        """
        Returns a JSON document representing the schedule.
        """
        # Just use a precision of seconds
        data = { "end_time": self.end_time.isoformat(timespec = "seconds") }
        return json.dumps(data)
    
    @classmethod
    def from_json(cls, document: str) -> 'PlatformSchedule':
        """
        Creates a platform schedule from a JSON representation.
        """
        data = json.loads(document)
        # Parse the end time into a datetime
        end_time = datetime.datetime.fromisoformat(data["end_time"])
        return cls(end_time = end_time)
