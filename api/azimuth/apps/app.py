import functools
import json
import logging
import typing as t

import dateutil.parser

import httpx

import yaml

from easykube import (
    Configuration,
    ApiError,
    SyncClient,
    PRESENT
)

from ..acls import allowed_by_acls
from ..cluster_api import dto as capi_dto
from ..provider import base as cloud_base
from ..utils import get_namespace

from . import base, dto, errors


logger = logging.getLogger(__name__)


APPS_API_VERSION = "apps.azimuth-cloud.io/v1alpha1"


def convert_exceptions(f):
    """
    Decorator that converts Kubernetes API exceptions into errors from :py:mod:`..errors`.
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
                    .replace("apptemplates.apps.azimuth-cloud.io", "Kubernetes app template")
                    .replace("apps.apps.azimuth-cloud.io", "Kubernetes app")
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
        except httpx.HTTPError as exc:
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

    def session(self, cloud_session: cloud_base.ScopedSession) -> 'Session':
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

    def _log(self, message, *args, level = logging.INFO, **kwargs):
        logger.log(
            level,
            "[%s] [%s] " + message,
            self._cloud_session.username(),
            self._cloud_session.tenancy().name,
            *args,
            **kwargs
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
            dto.Chart(
                at.spec.chart.repo,
                at.spec.chart.name
            ),
            at.spec.get("defaultValues", {}),
            [
                dto.Version(
                    version["name"],
                    version.get("valuesSchema", {}),
                    version.get("uiSchema", {})
                )
                for version in status.get("versions", [])
            ]
        )

    @convert_exceptions
    def app_templates(self) -> t.Iterable[dto.AppTemplate]:
        """
        Lists the app templates currently available to the tenancy.
        """
        self._log("Fetching available app templates")
        templates = list(self._client.api(APPS_API_VERSION).resource("apptemplates").list())
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
    def find_app_template(self, id: str) -> dto.AppTemplate:
        """
        Finds an app template by id.
        """
        self._log("Fetching app template with id '%s'", id)
        template = self._client.api(APPS_API_VERSION).resource("apptemplates").fetch(id)

        tenancy =  self._cloud_session.tenancy()
        if not allowed_by_acls(template, tenancy):
            raise errors.ObjectNotFoundError(f"Cannot find app template {id}")

        # Don't return app templates with no versions
        if template.get("status", {}).get("versions"):
            return self._from_api_app_template(template)
        else:
            raise errors.ObjectNotFoundError(f"Kubernetes app template '{id}' not found")

    def _from_api_app(self, app):
        """
        Converts a Helm release to an app DTO.
        """
        # We want to account for the case where a change has been made but the operator
        # has not yet caught up by tweaking the status
        app_phase = app.get("status", {}).get("phase")
        if app.metadata.get("deletionTimestamp"):
            # If the app has a deletion timestamp, flag it as uninstalling even if
            # the operator hasn't yet updated the status
            app_phase = "Uninstalling"
        elif not app_phase:
            # If there is no status, then the operator has not caught up after a create
            app_phase = "Pending"
        else:
            # Otherwise, we can compare the spec to the last handled configuration
            last_handled_configuration = json.loads(
                app.metadata
                    .get("annotations", {})
                    .get("apps.azimuth-cloud.io/last-handled-configuration", "{}")
            )
            last_handled_spec = last_handled_configuration.get("spec")
            if last_handled_spec and app.spec != last_handled_spec:
                app_phase = "Upgrading"
        app_status = app.get("status", {})
        return dto.App(
            app.metadata.name,
            app.metadata.name,
            app.metadata.get("annotations", {}).get("azimuth.stackhpc.com/cluster"),
            app.spec.template.name,
            app.spec.template.version,
            app.spec.get("values", {}),
            app_phase,
            app_status.get("usage") or None,
            app_status.get("failureMessage") or None,
            [
                dto.Service(
                    name,
                    service["label"],
                    service["fqdn"],
                    service.get("iconUrl")
                )
                for name, service in app_status.get("services", {}).items()
            ],
            dateutil.parser.parse(app.metadata["creationTimestamp"]),
            app.spec["createdByUsername"],
            app.spec["createdByUserId"],
            app.spec.get("updatedByUsername"),
            app.spec.get("updatedByUserId"),
        )

    @convert_exceptions
    def apps(self) -> t.Iterable[dto.App]:
        """
        Lists the apps for the tenancy.
        """
        self._log("Fetching available apps")
        # The apps are the HelmReleases that reference an Azimuth app template
        apps = list(self._client.api(APPS_API_VERSION).resource("apps").list())
        self._log("Found %s apps", len(apps))
        return tuple(self._from_api_app(app) for app in apps)

    @convert_exceptions
    def find_app(self, id: str) -> dto.App:
        """
        Finds an app by id.
        """
        self._log("Fetching app with id '%s'", id)
        # We only want to include apps with the app-template label
        app = self._client.api(APPS_API_VERSION).resource("apps").fetch(id)
        return self._from_api_app(app)

    @convert_exceptions
    def create_app(
        self,
        name: str,
        template: dto.AppTemplate,
        values: t.Dict[str, t.Any],
        *,
        kubernetes_cluster: t.Optional[capi_dto.Cluster] = None,
        zenith_identity_realm_name: t.Optional[str] = None
    ) -> dto.App:
        """
        Create a new app in the tenancy.
        """
        # For now, we require a Kubernetes cluster
        if not kubernetes_cluster:
            raise errors.BadInputError("No Kubernetes cluster specified.")
        # This driver requires the Zenith identity realm to be specified
        if not zenith_identity_realm_name:
            raise errors.BadInputError("No Zenith identity realm specified.")
        # NOTE(mkjpryor)
        # We know that the target namespace exists because it has a cluster in
        return self._from_api_app(
            self._client
                .api(APPS_API_VERSION)
                .resource("apps")
                .create({
                    "metadata": {
                        "name": name,
                        "labels": {
                            "app.kubernetes.io/managed-by": "azimuth",
                        },
                        # If the app belongs to a cluster, store that in an annotation
                        "annotations": {
                            "azimuth.stackhpc.com/cluster": kubernetes_cluster.id,
                        },
                    },
                    "spec": {
                        "template": {
                            "name": template.id,
                            # Use the most recent version when creating an app
                            "version": template.versions[0].name,
                        },
                        "kubeconfigSecret": {
                            # Use the kubeconfig for the cluster
                            "name": f"{kubernetes_cluster.id}-kubeconfig",
                            "key": "value",
                        },
                        "zenithIdentityRealmName": zenith_identity_realm_name,
                        "values": values,
                        "createdByUsername": self._cloud_session.username(),
                        "createdByUserId": self._cloud_session.user_id(),
                    },
                })
        )

    @convert_exceptions
    def update_app(
        self,
        app: t.Union[dto.App, str],
        template: dto.AppTemplate,
        version: dto.Version,
        values: t.Dict[str, t.Any]
    ) -> dto.App:
        """
        Update the specified cluster with the given parameters.
        """
        if isinstance(app, dto.App):
            app = app.id
        return self._from_api_app(
            self._client
                .api(APPS_API_VERSION)
                .resource("apps")
                .patch(
                    app,
                    {
                        "spec": {
                            "template": {
                                "name": template.id,
                                "version": version.name,
                            },
                            "values": values,
                            "updatedByUsername": self._cloud_session.username(),
                            "updatedByUserId": self._cloud_session.user_id(),
                        },
                    },
                )
        )

    @convert_exceptions
    def delete_app(self, app: t.Union[dto.App, str]) -> t.Optional[dto.App]:
        """
        Delete the specified app.
        """
        # Check if the specified id is actually an app before deleting it
        if isinstance(app, dto.App):
            app = app.id
        self._client.api(APPS_API_VERSION).resource("apps").delete(
            app,
            propagation_policy = "Foreground"
        )
        return self.find_app(app)

    def close(self):
        """
        Closes the session and performs any cleanup.
        """
        self._client.close()
