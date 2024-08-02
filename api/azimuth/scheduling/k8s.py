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


def create_lease(
        ekclient,
        name: str,
        k8s_obj: t.Dict[str, t.Any],
        schedule: dto.PlatformSchedule,
        flavor_id_counts: t.Dict[str, int],
        cloud_credentials_secret_name: str,
):
    """
    Creates a lease resource for the given Kubernetes object.
    """
    ekresource = ekclient.api(SCHEDULE_API_VERSION).resource("leases")
    # Convert the start and end times from the lease to UTC and format them
    end_time_utc = schedule.end_time.astimezone(datetime.timezone.utc)
    ends_at = end_time_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
    _ = ekresource.create(
        {
            "metadata": {
                "name": name,
                # ensure we delete the lease
                # when the cluster is deleted
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
                "cloudCredentialsSecretName": cloud_credentials_secret_name,
                "endsAt": ends_at,
                "resources": {
                    "virtualMachines": [
                        {
                            "flavorId": flavor,
                            "count": count,
                        }
                        for flavor, count in flavor_id_counts.items()
                    ]
                }
            },
        }
    )
