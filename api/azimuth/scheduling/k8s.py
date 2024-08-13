import datetime
import typing as t

from . import dto


SCHEDULE_API_VERSION = "scheduling.azimuth.stackhpc.com/v1alpha1"


def create_schedule(
    ekclient,
    name: str,
    owner: t.Dict[str, t.Any],
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
                        "apiVersion": owner["apiVersion"],
                        "kind": owner["kind"],
                        "name": owner["metadata"]["name"],
                        "uid": owner["metadata"]["uid"],
                    },
                ],
            },
            "spec": {
                "ref": {
                    "apiVersion": owner["apiVersion"],
                    "kind": owner["kind"],
                    "name": owner["metadata"]["name"],
                },
                "notAfter": not_after,
            },
        }
    )


def create_lease(
    ekclient,
    name: str,
    owner: t.Dict[str, t.Any],
    cloud_credentials_secret_name: str,
    resources: dto.PlatformResources,
    schedule: t.Optional[dto.PlatformSchedule]
):
    """
    Creates a lease resource for the given Kubernetes object.
    """
    ekresource = ekclient.api(SCHEDULE_API_VERSION).resource("leases")
    if schedule is not None:
        # Convert the start and end times from the schedule to UTC and format them
        end_time_utc = schedule.end_time.astimezone(datetime.timezone.utc)
        ends_at = end_time_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
    else:
        ends_at = None
    _ = ekresource.create(
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
