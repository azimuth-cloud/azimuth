import base64
import functools
import importlib
import json
import logging
import re
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

from ..provider import base as cloud_base, dto as cloud_dto

from . import dto, errors


logger = logging.getLogger(__name__)


CAPI_ADDONS_API_VERSION = "addons.stackhpc.com/v1alpha1"
AZIMUTH_API_VERSION = "azimuth.stackhpc.com/v1alpha1"


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
                    .replace("clustertemplates.azimuth.stackhpc.com", "Cluster template")
                    .replace("clusters.azimuth.stackhpc.com", "Cluster")
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
        except httpx.HTTPError as exc:
            logger.exception("Could not connect to Kubernetes API.")
            raise errors.CommunicationError("Could not connect to Kubernetes API.")
    return wrapper


class Provider:
    """
    Base class for Cluster API providers.
    """
    def __init__(self, namespace_template: str):
        self._namespace_template = namespace_template
        # Get the easykube configuration from the environment
        self._ekconfig = Configuration.from_environment()

    def get_session_class(self) -> t.Type['Session']:
        """
        Returns the session class for the provider.

        By default, it uses a class called ``Session`` in the same module as the provider.
        """
        module = importlib.import_module(self.__module__)
        return module.Session

    def session(self, cloud_session: cloud_base.ScopedSession) -> 'Session':
        """
        Returns a Cluster API session scoped to the given cloud provider session.
        """
        session_class = self.get_session_class()
        # Get the namespace to use by substituting the sanitised tenancy name into the template
        tenancy_name = re.sub("[^a-z0-9]+", "-", cloud_session.tenancy().name.lower()).strip("-")
        namespace = self._namespace_template.format(tenancy_name = tenancy_name)
        # Create an easykube client targetting our namespace
        client = self._ekconfig.sync_client(default_namespace = namespace)
        return session_class(client, cloud_session)


class NodeGroupSpec(t.TypedDict):
    """
    Type representing a node group specification dict.
    """
    #: The name of the node group
    name: str
    #: The size of nodes in the group
    machine_size: cloud_dto.Size
    #: Indicates if the node group should autoscale
    autoscale: bool
    #: The fixed number of nodes in the node group when autoscale is false
    count: t.Optional[int]
    #: The minimum number of nodes in the node group when autoscale is true
    min_count: t.Optional[int]
    #: The maximum number of nodes in the node group when autoscale is true
    max_count: t.Optional[int]


class Session:
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

    def _ensure_namespace(self):
        """
        Ensures that the target namespace exists.
        """
        try:
            self._client.api("v1").resource("namespaces").create({
                "metadata": {
                    "name": self._client.default_namespace,
                    "labels": {
                        "app.kubernetes.io/managed-by": "azimuth",
                    },
                },
            })
        except ApiError as exc:
            # Swallow the conflict that occurs when the namespace already exists
            if exc.status_code != 409 or exc.reason.lower() != "alreadyexists":
                raise

    def _from_api_cluster_template(self, ct):
        """
        Converts a cluster template from the Kubernetes API to a DTO.
        """
        return dto.ClusterTemplate(
            ct.metadata.name,
            ct.spec.label,
            ct.spec.get("description"),
            ct.spec["values"]["kubernetesVersion"],
            ct.spec.get("deprecated", False),
            dateutil.parser.parse(ct.metadata["creationTimestamp"]),
        )

    @convert_exceptions
    def cluster_templates(self) -> t.Iterable[dto.ClusterTemplate]:
        """
        Lists the cluster templates currently available to the tenancy.
        """
        self._log("Fetching available cluster templates")
        templates = list(
            self._client
                .api(AZIMUTH_API_VERSION)
                .resource("clustertemplates")
                .list()
        )
        self._log("Found %s cluster templates", len(templates))
        return tuple(self._from_api_cluster_template(ct) for ct in templates)

    @convert_exceptions
    def find_cluster_template(self, id: str) -> dto.ClusterTemplate:
        """
        Finds a cluster template by id.
        """
        self._log("Fetching cluster template with id '%s'", id)
        return self._from_api_cluster_template(
            self._client
                .api(AZIMUTH_API_VERSION)
                .resource("clustertemplates")
                .fetch(id)
        )

    def _from_api_cluster(self, cluster, sizes):
        """
        Converts a cluster from the Kubernetes API to a DTO.
        """
        # We want to account for the case where a change has been made but the operator
        # has not yet caught up by tweaking the cluster state against what is reported
        cluster_state = cluster.get("status", {}).get("phase")
        if cluster.metadata.get("deletionTimestamp"):
            # If the cluster has a deletion timestamp, flag it as deleting even if
            # the operator hasn't yet updated the status
            cluster_state = "Deleting"
        elif not cluster_state:
            # If there is no state, then the operator has not caught up after a create
            # So use Reconciling as the state in this case
            cluster_state = "Reconciling"
        else:
            # Otherwise, we can compare the spec to the last handled configuration
            # If the template has changed, we have an upgrade
            # If anything else has changed, we have a reconciliation
            last_handled_configuration = json.loads(
                cluster.metadata
                    .get("annotations", {})
                    .get("azimuth.stackhpc.com/last-handled-configuration", "{}")
            )
            last_handled_spec = last_handled_configuration.get("spec", {})
            if "templateName" not in last_handled_spec:
                cluster_state = "Reconciling"
            elif cluster.spec["templateName"] != last_handled_spec["templateName"]:
                cluster_state = "Upgrading"
            elif cluster.spec != last_handled_spec:
                cluster_state = "Reconciling"
        return dto.Cluster(
            cluster.metadata.name,
            cluster.metadata.name,
            cluster.spec["templateName"],
            next(
                (
                    size.id
                    for size in sizes
                    if size.name == cluster.spec["controlPlaneMachineSize"]
                ),
                None
            ),
            [
                dto.NodeGroup(
                    ng["name"],
                    next(
                        (
                            size.id
                            for size in sizes
                            if size.name == ng["machineSize"]
                        ),
                        None
                    ),
                    ng.get("autoscale", False),
                    ng.get("count"),
                    ng.get("minCount"),
                    ng.get("maxCount")
                )
                for ng in cluster.spec.get("nodeGroups", [])
            ],
            cluster.spec["autohealing"],
            cluster.spec.get("addons", {}).get("dashboard", False),
            cluster.spec.get("addons", {}).get("ingress", False),
            cluster.spec.get("addons", {}).get("monitoring", False),
            cluster.get("status", {}).get("kubernetesVersion"),
            cluster_state,
            cluster.get("status", {}).get("controlPlanePhase", "Unknown"),
            [
                dto.Node(
                    name,
                    node["role"],
                    node["phase"],
                    next(
                        (
                            size.id
                            for size in sizes
                            if size.name == node["size"]
                        ),
                        None
                    ),
                    node.get("ip"),
                    node.get("kubeletVersion"),
                    node.get("nodeGroup"),
                    dateutil.parser.parse(node["created"])
                )
                for name, node in cluster.get("status", {}).get("nodes", {}).items()
            ],
            [
                dto.Addon(name, addon.get("phase", "Unknown"))
                for name, addon in cluster.get("status", {}).get("addons", {}).items()
            ],
            [
                dto.Service(name, service["label"], service["fqdn"], service.get("iconUrl"))
                for name, service in cluster.get("status", {}).get("services", {}).items()
            ],
            dateutil.parser.parse(cluster.metadata["creationTimestamp"]),
        )

    @convert_exceptions
    def clusters(self) -> t.Iterable[dto.Cluster]:
        """
        Lists the clusters currently available to the tenancy.
        """
        self._log("Fetching available clusters")
        clusters = list(
            self._client
                .api(AZIMUTH_API_VERSION)
                .resource("clusters")
                .list()
        )
        self._log("Found %s clusters", len(clusters))
        if clusters:
            sizes = list(self._cloud_session.sizes())
            return tuple(self._from_api_cluster(c, sizes) for c in clusters)
        else:
            return ()

    @convert_exceptions
    def find_cluster(self, id: str) -> dto.Cluster:
        """
        Finds a cluster by id.
        """
        self._log("Fetching cluster with id '%s'", id)
        cluster = (
            self._client
                .api(AZIMUTH_API_VERSION)
                .resource("clusters")
                .fetch(id)
        )
        sizes = list(self._cloud_session.sizes())
        return self._from_api_cluster(cluster, sizes)

    def _create_credential(self):
        """
        Creates a new credential and returns the Kubernetes secret data.

        The return value should be a dict with the "data" and/or "stringData" keys.
        """
        raise NotImplementedError

    def _build_cluster_spec(self, **options):
        spec = {}
        if "control_plane_size" in options:
            spec["controlPlaneMachineSize"] = options["control_plane_size"].name
        if "node_groups" in options:
            spec["nodeGroups"] = [
                {
                    "name": ng["name"],
                    "machineSize": ng["machine_size"].name,
                    "autoscale": ng["autoscale"],
                    "count": ng.get("count"),
                    "minCount": ng.get("min_count"),
                    "maxCount": ng.get("max_count"),
                }
                for ng in options["node_groups"]
            ]
        if "autohealing_enabled" in options:
            spec["autohealing"] = options["autohealing_enabled"]
        if "dashboard_enabled" in options:
            spec.setdefault("addons", {})["dashboard"] = options["dashboard_enabled"]
        if "ingress_enabled" in options:
            spec.setdefault("addons", {})["ingress"] = options["ingress_enabled"]
        if "monitoring_enabled" in options:
            spec.setdefault("addons", {})["monitoring"] = options["monitoring_enabled"]
        return spec

    def _modify_cluster_spec(
        self,
        cluster_spec: t.Dict[str, t.Any],
        is_create: bool
    ) -> t.Dict[str, t.Any]:
        """
        Hook that can be implemented by subclasses to make cloud-specific modifications
        to the cluster spec.
        """
        return cluster_spec

    @convert_exceptions
    def create_cluster(
        self,
        name: str,
        template: dto.ClusterTemplate,
        control_plane_size: cloud_dto.Size,
        node_groups: t.List[NodeGroupSpec],
        autohealing_enabled: bool = True,
        dashboard_enabled: bool = False,
        ingress_enabled: bool = False,
        monitoring_enabled: bool = False,
        zenith_identity_realm_name: t.Optional[str] = None
    ) -> dto.Cluster:
        """
        Create a new cluster in the tenancy.
        """
        # Make sure that the target namespace exists
        self._ensure_namespace()
        # Create the cloud credential secret
        secret_data = self._create_credential(name)
        secret_name = f"{name}-cloud-credentials"
        secret_data.setdefault("metadata", {})["name"] = secret_name
        secret = (
            self._client
                .api("v1")
                .resource("secrets")
                .create_or_replace(secret_name, secret_data)
        )
        # Build the cluster spec
        cluster_spec = self._build_cluster_spec(
            control_plane_size = control_plane_size,
            node_groups = node_groups,
            autohealing_enabled = autohealing_enabled,
            dashboard_enabled = dashboard_enabled,
            ingress_enabled = ingress_enabled,
            monitoring_enabled = monitoring_enabled
        )
        # Add the create-only pieces
        cluster_spec.update({
            "label": name,
            "templateName": template.id,
            "cloudCredentialsSecretName": secret.metadata.name,
        })
        if zenith_identity_realm_name:
            cluster_spec["zenithIdentityRealmName"] = zenith_identity_realm_name
        # Call the hook method to allow any modifications
        cluster_spec = self._modify_cluster_spec(cluster_spec, True)
        # Create the cluster
        ekclusters = self._client.api(AZIMUTH_API_VERSION).resource("clusters")
        cluster = ekclusters.create({
            "metadata": {
                "name": name,
                "labels": {
                    "app.kubernetes.io/managed-by": "azimuth",
                },
            },
            "spec": cluster_spec,
        })
        # Use the sizes that we already have
        sizes = [control_plane_size] + [ng["machine_size"] for ng in node_groups]
        return self._from_api_cluster(cluster, sizes)

    @convert_exceptions
    def update_cluster(self, cluster: t.Union[dto.Cluster, str], **options):
        """
        Update the specified cluster with the given parameters.
        """
        spec = self._build_cluster_spec(**options)
        spec = self._modify_cluster_spec(spec, False)
        cluster = (
            self._client
                .api(AZIMUTH_API_VERSION)
                .resource("clusters")
                .patch(cluster, { "spec": spec })
        )
        sizes = list(self._cloud_session.sizes())
        return self._from_api_cluster(cluster, sizes)

    @convert_exceptions
    def upgrade_cluster(
        self,
        cluster: t.Union[dto.Cluster, str],
        template: t.Union[dto.ClusterTemplate, str]
    ) -> dto.Cluster:
        """
        Upgrade the specified cluster to the specified template.
        """
        if isinstance(cluster, dto.Cluster):
            cluster = cluster.id
        if not isinstance(template, dto.ClusterTemplate):
            template = self.find_cluster_template(template)
        # Apply a patch to the specified cluster to update the template
        ekclusters = self._client.api(AZIMUTH_API_VERSION).resource("clusters")
        cluster = ekclusters.patch(
            cluster,
            {
                "spec": {
                    "templateName": template.id,
                },
            }
        )
        sizes = list(self._cloud_session.sizes())
        return self._from_api_cluster(cluster, sizes)

    @convert_exceptions
    def delete_cluster(
        self,
        cluster: t.Union[dto.Cluster, str]
    ) -> t.Optional[dto.Cluster]:
        """
        Delete the specified Kubernetes cluster.
        """
        if isinstance(cluster, dto.Cluster):
            cluster = cluster.id
        self._client.api(AZIMUTH_API_VERSION).resource("clusters").delete(cluster)
        return self.find_cluster(cluster)

    @convert_exceptions
    def generate_kubeconfig(
        self,
        cluster: t.Union[dto.Cluster, str]
    ) -> str:
        """
        Generate a kubeconfig for the specified cluster.
        """
        if isinstance(cluster, dto.Cluster):
            cluster = cluster.id
        self._log("Generating kubeconfig for cluster with id '%s'", id)
        cluster = (
            self._client
                .api(AZIMUTH_API_VERSION)
                .resource("clusters")
                .fetch(cluster)
        )
        # Just get the named secret
        kubeconfig_secret_name = cluster.get("status", {}).get("kubeconfigSecretName")
        if kubeconfig_secret_name:
            try:
                secret = (
                    self._client
                        .api("v1")
                        .resource("secrets")
                        .fetch(kubeconfig_secret_name)
                )
            except ApiError as exc:
                if exc.status_code != 404:
                    raise
            else:
                # The kubeconfig is base64-encoded in the data
                return base64.b64decode(secret.data.value)
        raise errors.ObjectNotFoundError(f"Kubeconfig not available for cluster '{cluster.metadata.name}'")

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
        templates = list(
            self._client
                .api(AZIMUTH_API_VERSION)
                .resource("apptemplates")
                .list()
        )
        self._log("Found %s app templates", len(templates))
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
        template = (
            self._client
                .api(AZIMUTH_API_VERSION)
                .resource("apptemplates")
                .fetch(id)
        )
        # Don't return app templates with no versions
        if template.get("status", {}).get("versions"):
            return self._from_api_app_template(template)
        else:
            raise errors.ObjectNotFoundError(f"Kubernetes app template '{id}' not found")

    def _from_helm_release(self, helm_release):
        """
        Converts a Helm release to an app DTO.
        """
        # We want to account for the case where a change has been made but the operator
        # has not yet caught up by tweaking the release state
        app_state = helm_release.get("status", {}).get("phase")
        if helm_release.metadata.get("deletionTimestamp"):
            # If the release has a deletion timestamp, flag it as uninstalling even if
            # the operator hasn't yet updated the status
            app_state = "Uninstalling"
        elif not app_state:
            # If there is no state, then the operator has not caught up after a create
            app_state = "Pending"
        else:
            # Otherwise, we can compare the spec to the last handled configuration
            last_handled_configuration = json.loads(
                helm_release.metadata
                    .get("annotations", {})
                    .get("addons.stackhpc.com/last-handled-configuration", "{}")
            )
            last_handled_spec = last_handled_configuration.get("spec")
            if last_handled_spec and helm_release.spec != last_handled_spec:
                app_state = "Upgrading"
        services_annotation = (
            helm_release
                .metadata
                .get("annotations", {})
                .get("azimuth.stackhpc.com/services")
        )
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
                {}
            ),
            app_state,
            helm_release.get("status", {}).get("notes") or None,
            helm_release.get("status", {}).get("failureMessage") or None,
            [
                dto.Service(
                    name,
                    service["label"],
                    service["fqdn"],
                    service.get("iconUrl")
                )
                for name, service in services.items()
            ],
            dateutil.parser.parse(helm_release.metadata["creationTimestamp"])
        )

    @convert_exceptions
    def apps(self) -> t.Iterable[dto.Cluster]:
        """
        Lists the apps for the tenancy.
        """
        self._log("Fetching available apps")
        # The apps are the HelmReleases that reference an Azimuth app template
        apps = list(
            self._client
                .api(CAPI_ADDONS_API_VERSION)
                .resource("helmreleases")
                .list(
                    labels = {
                        "azimuth.stackhpc.com/app-template": PRESENT,
                    }
                )
        )
        self._log("Found %s apps", len(apps))
        return tuple(self._from_helm_release(app) for app in apps)

    @convert_exceptions
    def find_app(self, id: str) -> dto.Cluster:
        """
        Finds an app by id.
        """
        self._log("Fetching app with id '%s'", id)
        # We only want to include apps with the app-template label
        app = (
            self._client
                .api(CAPI_ADDONS_API_VERSION)
                .resource("helmreleases")
                .fetch(id)
        )
        if "azimuth.stackhpc.com/app-template" not in app.metadata.labels:
            raise errors.ObjectNotFoundError(f"Kubernetes app \"{id}\" not found")
        return self._from_helm_release(app)

    @convert_exceptions
    def create_app(
        self,
        name: str,
        template: dto.AppTemplate,
        kubernetes_cluster: dto.Cluster,
        values: t.Dict[str, t.Any]
    ) -> dto.App:
        """
        Create a new app in the tenancy.
        """
        # We know that the cluster exists, which means that the namespace exists
        ekapps = self._client.api(CAPI_ADDONS_API_VERSION).resource("helmreleases")
        app = ekapps.create({
            "metadata": {
                "name": name,
                "labels": {
                    "app.kubernetes.io/managed-by": "azimuth",
                    "azimuth.stackhpc.com/app-template": template.id
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
        })
        return self._from_helm_release(app)

    @convert_exceptions
    def update_app(
        self,
        app: t.Union[dto.App, str],
        version: dto.Version,
        values: t.Dict[str, t.Any]
    ) -> dto.App:
        """
        Update the specified cluster with the given parameters.
        """
        # First, fetch the app to verify that it is actually an app, not a cluster addon
        if not isinstance(app, dto.App):
            app = self.find_app(app)
        return self._from_helm_release(
            self._client
                .api(CAPI_ADDONS_API_VERSION)
                .resource("helmreleases")
                .patch(
                    app.id,
                    {
                        "spec": {
                            "chart": {
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
    def delete_app(self, app: t.Union[dto.App, str]) -> t.Optional[dto.App]:
        """
        Delete the specified app.
        """
        # Check if the specified id is actually an app before deleting it
        if not isinstance(app, dto.App):
            app = self.find_app(app)
        self._client.api(CAPI_ADDONS_API_VERSION).resource("helmreleases").delete(app.id)
        return self.find_app(app.id)

    def close(self):
        """
        Closes the session and performs any cleanup.
        """
        self._client.close()

    def __enter__(self):
        """
        Called when entering a context manager block.
        """
        self._client.__enter__()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """
        Called when exiting a context manager block. Ensures that close is called.
        """
        self._client.__exit__(exc_type, exc_value, traceback)

    def __del__(self):
        """
        Ensures that close is called when the session is garbage collected.
        """
        self.close()
