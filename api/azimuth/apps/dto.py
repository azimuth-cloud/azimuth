import dataclasses
import datetime
import typing as t

from azimuth.scheduling import dto as scheduling_dto  # noqa: F401


@dataclasses.dataclass(frozen=True)
class Chart:
    """
    Represents a Helm chart to use for an app.
    """

    #: The repository for the chart for the app
    repo: str
    #: The name of the chart for the app
    name: str


@dataclasses.dataclass(frozen=True)
class Version:
    """
    Represents a version of an app.
    """

    #: The name of the version
    name: str
    #: The JSON schema to use to validate the values
    values_schema: dict[str, t.Any]
    #: The UI schema to use when rendering the form for the values
    ui_schema: dict[str, t.Any]


@dataclasses.dataclass(frozen=True)
class AppTemplate:
    """
    Represents a template for an app on a Kubernetes cluster.
    """

    #: The id of the app template
    id: str
    #: A human-readable label for the app template
    label: str
    #: The URL of the logo to use for the app template
    logo: str
    #: A brief description of the app template
    description: str
    #: The Helm chart to use for the app template
    chart: Chart
    #: The default values for the app template
    default_values: dict[str, t.Any]
    #: The available versions for the app template
    #: These should always be sorted from latest to oldest
    versions: list[Version]


@dataclasses.dataclass(frozen=True)
class Service:
    """
    Represents a service available on a cluster or app.
    """

    #: The name of the service
    name: str
    #: The human-readable label for the service
    label: str
    #: The FQDN for the service
    fqdn: str
    #: The URL of an ico for the service
    icon_url: str | None


@dataclasses.dataclass(frozen=True)
class App:
    """
    Represents an app on a Kubernetes cluster.
    """

    #: The id of the app
    id: str
    #: The human-readable name of the app
    name: str
    #: The id of the Kubernetes cluster that the app is deployed on
    kubernetes_cluster_id: str
    #: The id of the template for the app
    template_id: str
    #: The version of the template that the app is using
    version: str
    #: The values that were used for the app
    values: dict[str, t.Any]
    #: The deployment status of the app
    status: str
    #: The usage text produced by the chart
    usage: str
    #: The failure message if present
    failure_message: str
    #: The services for the app
    services: list[Service]
    #: The time at which the app was created
    created_at: datetime.datetime
    #: Details about the users interacting with the app
    created_by_username: str | None
    created_by_user_id: str | None
    updated_by_username: str | None
    updated_by_user_id: str | None
