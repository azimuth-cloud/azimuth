import datetime
import typing as t

from . import dto


SCHEDULE_API_VERSION = "scheduling.azimuth.stackhpc.com/v1alpha1"


def create_schedule(
    ekclient,
    name: str,
    k8s_obj: t.Dict[str, t.Any],
    schedule: dto.PlatformSchedule
):
    """
    Creates a schedule resource for the given Kubernetes object.
    """
    ekresource = ekclient.api(SCHEDULE_API_VERSION).resource("schedules")
    # We don't currently support the start time from the schedule
    # Convert the end time from the schedule to UTC and format it
    end_time_utc = schedule.end_time.astimezone(datetime.timezone.utc)
    not_after = end_time_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
    _ = ekresource.create(
        {
            "metadata": {
                "name": name,
                "ownerReferences": [
                    {
                        "apiVersion": k8s_obj["apiVersion"],
                        "kind": k8s_obj["kind"],
                        "name": k8s_obj["metadata"]["name"],
                        "uid": k8s_obj["metadata"]["uid"],
                    },
                ],
            },
            "spec": {
                "ref": {
                    "apiVersion": k8s_obj["apiVersion"],
                    "kind": k8s_obj["kind"],
                    "name": k8s_obj["metadata"]["name"],
                },
                "notAfter": not_after,
            },
        }
    )
