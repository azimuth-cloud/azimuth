import base64  # noqa: F401
import functools
import importlib  # noqa: F401
import json
import logging
import typing as t

import dateutil.parser
import httpx
import yaml
from easykube import PRESENT, ApiError, Configuration, SyncClient

from ..acls import allowed_by_acls  # noqa: TID252
from ..cluster_api import dto as capi_dto  # noqa: TID252
from ..provider import base as cloud_base  # noqa: TID252
from ..utils import get_namespace  # noqa: TID252
from . import base, dto, errors

logger = logging.getLogger(__name__)


CAPI_ADDONS_API_VERSION = "addons.stackhpc.com/v1alpha1"
AZIMUTH_API_VERSION = "azimuth.stackhpc.com/v1alpha1"


def convert_exceptions(f):
    """
    Decorator that converts Kubernetes API exceptions into errors from
    :py:mod:`..errors`.
    """

    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except ApiError as exc:
            # Extract the status code and message
            status_code = exc.response.status_code
            message = (
                str(exc)
                .replace("apptemplates.azimuth.stackhpc.com", "Kubernetes app template")
                .replace("helmreleases.addons.stackhpc.com", "Kubernetes app")
            )
            if status_code == 400:
                raise errors.BadInputError(message)
            elif status_code == 404:
                raise errors.ObjectNotFoundError(message)
            elif status_code == 409:
                raise errors.InvalidOperationError(message)
            else:
                logger.exception("Unknown error with Kubernetes API.")
                raise errors.CommunicationError("Unknown error with Kubernetes API.")
        except httpx.HTTPError as exc:  # noqa: F841
            logger.exception("Could not connect to Kubernetes API.")
            raise errors.CommunicationError("Could not connect to Kubernetes API.")

    return wrapper


class Provider(base.Provider):
    """
    Base class for Cluster API providers.
    """

    def __init__(self):
        # Get the easykube configuration from the environment
        self._ekconfig = Configuration.from_environment()

    def session(self, cloud_session: cloud_base.ScopedSession) -> "Session":
        """
        Returns a Cluster API session scoped to the given cloud provider session.
        """
        client = self._ekconfig.sync_client()
        # Work out what namespace to target for the tenancy
        namespace = get_namespace(client, cloud_session.tenancy())
        # Set the target namespace as the default namespace for the client
        client.default_namespace = namespace
        return Session(client, cloud_session)


class Session(base.Session):
    """
    Base class for a scoped session.
    """

    def __init__(self, client: SyncClient, cloud_session: cloud_base.ScopedSession):
        self._client = client
        self._cloud_session = cloud_session

    def _log(self, message, *args, level=logging.INFO, **kwargs):
        logger.log(
            level,
            "[%s] [%s] " + message,
            self._cloud_session.username(),
            self._cloud_session.tenancy().name,
            *args,
            **kwargs,
        )

    def _from_api_app_template(self, at):
        """
        Converts an app template from the Kubernetes API to a DTO.
        """
        status = at.get("status", {})
        return dto.AppTemplate(
            at.metadata.name,
            status.get("label", at.metadata.name),
            status.get("logo"),
            status.get("description"),
            dto.Chart(at.spec.chart.repo, at.spec.chart.name),
            at.spec.get("defaultValues", {}),
            [
                dto.Version(
                    version["name"],
                    version.get("valuesSchema", {}),
                    version.get("uiSchema", {}),
                )
                for version in status.get("versions", [])
            ],
        )

    @convert_exceptions
    def app_templates(self) -> t.Iterable[dto.AppTemplate]:
        """
        Lists the app templates currently available to the tenancy.
        """
        self._log("Fetching available app templates")
        templates = list(
            self._client.api(AZIMUTH_API_VERSION).resource("apptemplates").list()
        )
        self._log("Found %s app templates", len(templates))

        # Filter templates based on ACL annotations
        tenancy = self._cloud_session.tenancy()
        templates = [t for t in templates if allowed_by_acls(t, tenancy)]

        # Don't return app templates with no versions
        return tuple(
            self._from_api_app_template(at)
            for at in templates
            if at.get("status", {}).get("versions")
        )

    @convert_exceptions
    def find_app_template(self, id: str) -> dto.AppTemplate:  # noqa: A002
        """
        Finds an app template by id.
        """
        self._log("Fetching app template with id '%s'", id)
        template = (
            self._client.api(AZIMUTH_API_VERSION).resource("apptemplates").fetch(id)
        )

        tenancy = self._cloud_session.tenancy()
        if not allowed_by_acls(template, tenancy):
            raise errors.ObjectNotFoundError(f"Cannot find app template {id}")

        # Don't return app templates with no versions
        if template.get("status", {}).get("versions"):
            return self._from_api_app_template(template)
        else:
            raise errors.ObjectNotFoundError(
                f"Kubernetes app template '{id}' not found"
            )

    def _from_helm_release(self, helm_release):
        """
        Converts a Helm release to an app DTO.
        """
        # We want to account for the case where a change has been made but the operator
        # has not yet caught up by tweaking the release state
        app_state = helm_release.get("status", {}).get("phase")
        if helm_release.metadata.get("deletionTimestamp"):
            # If the release has a deletion timestamp, flag it as uninstalling even if
            # the operator hasn't yet updated the status
            app_state = "Uninstalling"
        elif not app_state:
            # If there is no state, then the operator has not caught up after a create
            app_state = "Pending"
        else:
            # Otherwise, we can compare the spec to the last handled configuration
            last_handled_configuration = json.loads(
                helm_release.metadata.get("annotations", {}).get(
                    "addons.stackhpc.com/last-handled-configuration", "{}"
                )
            )
            last_handled_spec = last_handled_configuration.get("spec")
            if last_handled_spec and helm_release.spec != last_handled_spec:
                app_state = "Upgrading"
        annotations = helm_release.metadata.get("annotations", {})
        services_annotation = annotations.get("azimuth.stackhpc.com/services")
        services = json.loads(services_annotation) if services_annotation else {}
        return dto.App(
            helm_release.metadata.name,
            helm_release.metadata.name,
            helm_release.spec["clusterName"],
            helm_release.metadata.labels["azimuth.stackhpc.com/app-template"],
            helm_release.spec.chart.version,
            # Just pull the values out of the first template source
            next(
                (
                    yaml.safe_load(source["template"])
                    for source in helm_release.spec.get("valuesSources", [])
                    if "template" in source
                ),
                {},
            ),
            app_state,
            helm_release.get("status", {}).get("notes") or None,
            helm_release.get("status", {}).get("failureMessage") or None,
            [
                dto.Service(
                    name, service["label"], service["fqdn"], service.get("iconUrl")
                )
                for name, service in services.items()
            ],
            dateutil.parser.parse(helm_release.metadata["creationTimestamp"]),
            annotations.get("azimuth.stackhpc.com/created-by-username"),
            annotations.get("azimuth.stackhpc.com/created-by-user-id"),
            annotations.get("azimuth.stackhpc.com/updated-by-username"),
            annotations.get("azimuth.stackhpc.com/updated-by-user-id"),
        )

    @convert_exceptions
    def apps(self) -> t.Iterable[dto.App]:
        """
        Lists the apps for the tenancy.
        """
        self._log("Fetching available apps")
        # The apps are the HelmReleases that reference an Azimuth app template
        apps = list(
            self._client.api(CAPI_ADDONS_API_VERSION)
            .resource("helmreleases")
            .list(
                labels={
                    "azimuth.stackhpc.com/app-template": PRESENT,
                }
            )
        )
        self._log("Found %s apps", len(apps))
        return tuple(self._from_helm_release(app) for app in apps)

    @convert_exceptions
    def find_app(self, id: str) -> dto.App:  # noqa: A002
        """
        Finds an app by id.
        """
        self._log("Fetching app with id '%s'", id)
        # We only want to include apps with the app-template label
        app = (
            self._client.api(CAPI_ADDONS_API_VERSION).resource("helmreleases").fetch(id)
        )
        if "azimuth.stackhpc.com/app-template" not in app.metadata.labels:
            raise errors.ObjectNotFoundError(f'Kubernetes app "{id}" not found')
        return self._from_helm_release(app)

    @convert_exceptions
    def create_app(
        self,
        name: str,
        template: dto.AppTemplate,
        values: dict[str, t.Any],
        *,
        kubernetes_cluster: capi_dto.Cluster | None = None,
        # This is ignored for the HelmRelease driver - the realm for the target cluster is used
        zenith_identity_realm_name: str | None = None
    ) -> dto.App:
        """
        Create a new app in the tenancy.
        """
        # A Kubernetes cluster is required for the helm release driver
        if not kubernetes_cluster:
            raise errors.BadInputError("No Kubernetes cluster specified.")
        # We know that the cluster exists, which means that the namespace exists
        ekapps = self._client.api(CAPI_ADDONS_API_VERSION).resource("helmreleases")
        app = ekapps.create(
            {
                "metadata": {
                    "name": name,
                    "labels": {
                        "app.kubernetes.io/managed-by": "azimuth",
                        "azimuth.stackhpc.com/app-template": template.id,
                    },
                    # Use annotations to indicate who created the app
                    "annotations": {
                        "azimuth.stackhpc.com/created-by-username": self._cloud_session.username(),  # noqa: E501
                        "azimuth.stackhpc.com/created-by-user-id": self._cloud_session.user_id(),  # noqa: E501
                    },
                },
                "spec": {
                    "clusterName": kubernetes_cluster.id,
                    "targetNamespace": name,
                    "releaseName": name,
                    "chart": {
                        "repo": template.chart.repo,
                        "name": template.chart.name,
                        # Use the first version when creating an app
                        "version": template.versions[0].name,
                    },
                    "valuesSources": [
                        {
                            "template": yaml.safe_dump(values),
                        },
                    ],
                },
            }
        )
        return self._from_helm_release(app)

    @convert_exceptions
    def update_app(
        self,
        app: dto.App | str,
        template: dto.AppTemplate,
        version: dto.Version,
        values: dict[str, t.Any],
    ) -> dto.App:
        """
        Update the specified cluster with the given parameters.
        """
        # First, fetch the app to verify that it is actually an app, not a cluster addon
        if not isinstance(app, dto.App):
            app = self.find_app(app)
        return self._from_helm_release(
            self._client.api(CAPI_ADDONS_API_VERSION)
            .resource("helmreleases")
            .patch(
                app.id,
                {
                    # Add/update the annotations that record the user doing the
                    # update
                    "metadata": {
                        "annotations": {
                            "azimuth.stackhpc.com/updated-by-username": (
                                self._cloud_session.username()
                            ),
                            "azimuth.stackhpc.com/updated-by-user-id": (
                                self._cloud_session.user_id()
                            ),
                        },
                    },
                    "spec": {
                        "chart": {
                            "repo": template.chart.repo,
                            "name": template.chart.name,
                            "version": version.name,
                        },
                        "valuesSources": [
                            {
                                "template": yaml.safe_dump(values),
                            },
                        ],
                    },
                },
            )
        )

    @convert_exceptions
    def delete_app(self, app: dto.App | str) -> dto.App | None:
        """
        Delete the specified app.
        """
        # Check if the specified id is actually an app before deleting it
        if not isinstance(app, dto.App):
            app = self.find_app(app)
        self._client.api(CAPI_ADDONS_API_VERSION).resource("helmreleases").delete(
            app.id
        )
        return self.find_app(app.id)

    def close(self):
        """
        Closes the session and performs any cleanup.
        """
        self._client.close()
