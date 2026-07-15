import datetime as dt

from ..settings import cloud_settings


def lifetime_from_annotations(annotations: dict[str, str]) -> dt.timedelta | None:
    if lifetime_hours := annotations.get(
        "scheduling.azimuth.stackhpc.com/max-duration-hours", False
    ):
        return dt.timedelta(hours=int(lifetime_hours))
    return None


def check_max_platform_duration(platform_data, max_lifetime: dt.timedelta) -> bool:
    """Validate that the requested lifetime of the cluster is within policy."""
    # If scheduling is disabled, or cluster has no max life, this is always OK.
    if max_lifetime is None or not cloud_settings.SCHEDULING.ENABLED:
        return True
    end_time = platform_data["schedule"].end_time
    now = dt.datetime.now(tz=dt.timezone.utc)
    duration = end_time - now
    if duration < max_lifetime:
        return True
    else:
        return False
