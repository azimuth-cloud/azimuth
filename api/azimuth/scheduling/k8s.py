import datetime
import typing as t

from . import dto

SCHEDULE_API_VERSION = "scheduling.azimuth.stackhpc.com/v1alpha1"


def leases_available(ekclient):
    """
    Returns True if leases are available on the target cluster, False otherwise.
    """
    try:
        _ = ekclient.api(SCHEDULE_API_VERSION).resource("leases")
    except ValueError:
        return False
    else:
        return True


def create_scheduling_resources(
    ekclient,
    name: str,
    owner: dict[str, t.Any],
    cloud_credentials_secret_name: str,
    resources: dto.PlatformResources,
    schedule: dto.PlatformSchedule | None
):
    """
    Creates scheduling resources for the given Kubernetes object.
    """
    # Get the formatted time from the schedule object
    if schedule is not None:
        # Convert the start and end times from the schedule to UTC and format them
        end_time_utc = schedule.end_time.astimezone(datetime.timezone.utc)
        ends_at = end_time_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
    else:
        ends_at = None
    # Try to get the leases resource from the schedule API
    ekapi = ekclient.api(SCHEDULE_API_VERSION)
    try:
        ekleases = ekapi.resource("leases")
    except ValueError:
        # If the lease CRD does not exist, fall back to the previous behaviour
        # I.e. create a schedule object if a schedule is set, do nothing otherwise
        if ends_at is not None:
            ekschedules = ekclient.api(SCHEDULE_API_VERSION).resource("schedules")
            _ = ekschedules.create(
                {
                    "metadata": {
                        "name": name,
                        "labels": {"app.kubernetes.io/managed-by": "azimuth"},
                        "ownerReferences": [
                            {
                                "apiVersion": owner["apiVersion"],
                                "kind": owner["kind"],
                                "name": owner["metadata"]["name"],
                                "uid": owner["metadata"]["uid"],
                                "blockOwnerDeletion": True,
                            },
                        ],
                    },
                    "spec": {
                        "ref": {
                            "apiVersion": owner["apiVersion"],
                            "kind": owner["kind"],
                            "name": owner["metadata"]["name"],
                        },
                        "notAfter": ends_at,
                    },
                }
            )
    else:
        _ = ekleases.create(
            {
                "metadata": {
                    "name": name,
                    "labels": {"app.kubernetes.io/managed-by": "azimuth"},
                    # ensure we delete the lease when the cluster is deleted
                    "ownerReferences": [
                        {
                            "apiVersion": owner["apiVersion"],
                            "kind": owner["kind"],
                            "name": owner["metadata"]["name"],
                            "uid": owner["metadata"]["uid"],
                            "blockOwnerDeletion": True,
                        },
                    ],
                },
                "spec": {
                    "cloudCredentialsSecretName": cloud_credentials_secret_name,
                    "endsAt": ends_at,
                    "resources": {
                        "machines": [
                            {
                                "sizeId": req.size.id,
                                "count": req.count
                            }
                            for req in resources.machines()
                        ],
                    },
                },
            }
        )
