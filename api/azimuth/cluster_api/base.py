import base64
import functools
import importlib
import json
import logging
import re
import typing as t

import dateutil.parser

import httpx

import easykube
from easykube.resources import Namespace, Secret

from ..provider import base as cloud_base, dto as cloud_dto

from . import dto, errors


logger = logging.getLogger(__name__)


ClusterTemplate = easykube.ResourceSpec(
    "azimuth.stackhpc.com/v1alpha1",
    "clustertemplates",
    "ClusterTemplate",
    False
)
Cluster = easykube.ResourceSpec(
    "azimuth.stackhpc.com/v1alpha1",
    "clusters",
    "Cluster",
    True
)


def convert_exceptions(f):
    """
    Decorator that converts Kubernetes API exceptions into errors from :py:mod:`..errors`.
    """
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except easykube.ApiError as exc:
            # Extract the status code and message
            status_code = exc.response.status_code
            message = (
                str(exc)
                    .replace("clustertemplates.azimuth.stackhpc.com", "Cluster template")
                    .replace("clusters.azimuth.stackhpc.com", "Cluster")
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
    def __init__(
        self,
        namespace_template: str = "az-{tenancy_name}",
        last_handled_configuration_annotation: str = "azimuth.stackhpc.com/last-handled-configuration"
    ):
        self._namespace_template = namespace_template
        self._last_handled_configuration_annotation = last_handled_configuration_annotation

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
        tenancy_name = re.sub("[^a-z0-9]+", "-", cloud_session._tenancy.name.lower()).strip("-")
        namespace = self._namespace_template.format(tenancy_name = tenancy_name)
        # Create an easykube client targetting our namespace
        client = easykube.SyncClient.from_environment(default_namespace = namespace)
        return session_class(client, cloud_session, self._last_handled_configuration_annotation)


class NodeGroupSpec(t.TypedDict):
    """
    Type representing a node group specification dict.
    """
    #: The name of the node group
    name: str
    #: The size of nodes in the group
    machine_size: cloud_dto.Size
    #: The target number of nodes in the group
    count: int


class Session:
    """
    Base class for a scoped session.
    """
    def __init__(
        self,
        client: easykube.SyncClient,
        cloud_session: cloud_base.ScopedSession,
        last_handled_configuration_annotation: str
    ):
        self._client = client
        self._cloud_session = cloud_session
        self._last_handled_configuration_annotation = last_handled_configuration_annotation

    def _log(self, message, *args, level = logging.INFO, **kwargs):
        logger.log(
            level,
            "[%s] [%s] " + message,
            self._cloud_session._username,
            self._cloud_session._tenancy.name,
            *args,
            **kwargs
        )

    def _ensure_namespace(self):
        """
        Ensures that the target namespace exists.
        """
        try:
            Namespace(self._client).create({
                "metadata": {
                    "name": self._client.default_namespace,
                },
            })
        except easykube.ApiError as exc:
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
            ct.spec["values"]["global"]["kubernetesVersion"],
            ct.spec.deprecated,
            dateutil.parser.parse(ct.metadata["creationTimestamp"]),
        )

    @convert_exceptions
    def cluster_templates(self) -> t.Iterable[dto.ClusterTemplate]:
        """
        Lists the cluster templates currently available to the tenancy.
        """
        self._log("Fetching available cluster templates")
        templates = list(ClusterTemplate(self._client).list())
        self._log("Found %s cluster templates", len(templates))
        return tuple(self._from_api_cluster_template(ct) for ct in templates)

    @convert_exceptions
    def find_cluster_template(self, id: str) -> dto.ClusterTemplate:
        """
        Finds a cluster template by id.
        """
        self._log("Fetching cluster template with id '%s'", id)
        return self._from_api_cluster_template(ClusterTemplate(self._client).fetch(id))

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
                    .get(self._last_handled_configuration_annotation, "{}")
            )
            last_handled_spec = last_handled_configuration.get("spec", {})
            if cluster.spec["templateName"] != last_handled_spec["templateName"]:
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
                    ng["count"]
                )
                for ng in cluster.spec.get("nodeGroups", [])
            ],
            cluster.spec["autohealing"],
            cluster.spec.get("addons", {}).get("certManager", False),
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
                    node.get("ip"),
                    node.get("kubeletVersion"),
                    node.get("nodeGroup")
                )
                for name, node in cluster.get("status", {}).get("nodes", {}).items()
            ],
            [
                dto.Addon(name, addon.get("phase", "Unknown"))
                for name, addon in cluster.get("status", {}).get("addons", {}).items()
            ],
            dateutil.parser.parse(cluster.metadata["creationTimestamp"]),
        )

    @convert_exceptions
    def clusters(self) -> t.Iterable[dto.Cluster]:
        """
        Lists the clusters currently available to the tenancy.
        """
        self._log("Fetching available clusters")
        clusters = list(Cluster(self._client).list())
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
        sizes = list(self._cloud_session.sizes())
        return self._from_api_cluster(Cluster(self._client).fetch(id), sizes)

    def _create_credential(self):
        """
        Creates a new credential and returns the Kubernetes secret data.;l

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
                    "count": ng["count"],
                }
                for ng in options["node_groups"]
            ]
        if "autohealing_enabled" in options:
            spec["autohealing"] = options["autohealing_enabled"]
        if "cert_manager_enabled" in options:
            spec.setdefault("addons", {})["certManager"] = options["cert_manager_enabled"]
        if "ingress_enabled" in options:
            spec.setdefault("addons", {})["ingress"] = options["ingress_enabled"]
        if "monitoring_enabled" in options:
            spec.setdefault("addons", {})["monitoring"] = options["monitoring_enabled"]
        return spec

    @convert_exceptions
    def create_cluster(
        self,
        name: str,
        template: dto.ClusterTemplate,
        control_plane_size: cloud_dto.Size,
        node_groups: t.List[NodeGroupSpec],
        autohealing_enabled: bool = True,
        cert_manager_enabled: bool = False,
        ingress_enabled: bool = False,
        monitoring_enabled: bool = False
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
        secret = Secret(self._client).create_or_replace(secret_name, secret_data)
        # Build the cluster spec
        cluster_spec = self._build_cluster_spec(
            control_plane_size = control_plane_size,
            node_groups = node_groups,
            autohealing_enabled = autohealing_enabled,
            cert_manager_enabled = cert_manager_enabled,
            ingress_enabled = ingress_enabled,
            monitoring_enabled = monitoring_enabled
        )
        # Add the create-only pieces
        cluster_spec.update({
            "label": name,
            "templateName": template.id,
            "cloudCredentialsSecretName": secret.metadata.name,
        })
        # Create the cluster
        cluster = Cluster(self._client).create({
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
        cluster = Cluster(self._client).patch(cluster, { "spec": spec })
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
        cluster = Cluster(self._client).patch(cluster, {
            "spec": {
                "templateName": template.id,
            },
        })
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
        Cluster(self._client).delete(cluster)
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
        cluster = Cluster(self._client).fetch(cluster)
        # Just get the named secret
        kubeconfig_secret_name = cluster.get("status", {}).get("kubeconfigSecretName")
        if kubeconfig_secret_name:
            try:
                secret = Secret(self._client).fetch(kubeconfig_secret_name)
            except easykube.ApiError as exc:
                if exc.status_code != 404:
                    raise
            else:
                # The kubeconfig is base64-encoded in the data
                return base64.b64decode(secret.data.value)
        raise errors.ObjectNotFoundError(f"Kubeconfig not available for cluster '{cluster.metadata.name}'")

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
