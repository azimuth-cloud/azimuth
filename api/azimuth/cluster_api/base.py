import base64
import functools
import importlib
import json
import logging
import typing as t

import dateutil.parser
import httpx
from easykube import PRESENT, ApiError, Configuration, SyncClient  # noqa: F401

from .. import utils  # noqa: TID252
from ..acls import allowed_by_acls  # noqa: TID252
from ..provider import base as cloud_base  # noqa: TID252
from ..provider import dto as cloud_dto  # noqa: TID252
from ..provider import errors as cloud_errors  # noqa: TID252
from ..scheduling import dto as scheduling_dto  # noqa: TID252
from ..scheduling import k8s as scheduling_k8s  # noqa: TID252
from . import dto, errors

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
        except httpx.HTTPError as exc:  # noqa: F841
            logger.exception("Could not connect to Kubernetes API.")
            raise errors.CommunicationError("Could not connect to Kubernetes API.")

    return wrapper


class Provider:
    """
    Base class for Cluster API providers.
    """

    def __init__(self):
        # Get the easykube configuration from the environment
        self._ekconfig = Configuration.from_environment()

    def get_session_class(self) -> type["Session"]:
        """
        Returns the session class for the provider.

        By default, it uses a class called ``Session`` in the same module as the
        provider.
        """
        module = importlib.import_module(self.__module__)
        return module.Session

    def session(self, cloud_session: cloud_base.ScopedSession) -> "Session":
        """
        Returns a Cluster API session scoped to the given cloud provider session.
        """
        session_class = self.get_session_class()
        client = self._ekconfig.sync_client()
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
    count: int | None
    #: The minimum number of nodes in the node group when autoscale is true
    min_count: int | None
    #: The maximum number of nodes in the node group when autoscale is true
    max_count: int | None


class Session:
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

    def _from_api_cluster_template(self, ct):
        """
        Converts a cluster template from the Kubernetes API to a DTO.
        """
        values = ct.spec["values"]
        # We only need to account for the etcd volume if it has type Volume
        etcd_volume_size = 0
        etcd_volume = values.get("etcd", {}).get("blockDevice")
        if etcd_volume and etcd_volume.get("type", "Volume") == "Volume":
            etcd_volume_size = etcd_volume["size"]
        return dto.ClusterTemplate(
            ct.metadata.name,
            ct.spec.label,
            ct.spec.get("description"),
            values["kubernetesVersion"],
            ct.spec.get("deprecated", False),
            values.get("controlPlane", {}).get("machineCount", 3),
            etcd_volume_size,
            values.get("controlPlane", {}).get("machineRootVolume", {}).get("diskSize")
            or 0,
            values.get("nodeGroupDefaults", {})
            .get("machineRootVolume", {})
            .get("diskSize")
            or 0,
            ct.spec.get("tags", []),
            dateutil.parser.parse(ct.metadata["creationTimestamp"]),
        )

    @convert_exceptions
    def cluster_templates(self) -> t.Iterable[dto.ClusterTemplate]:
        """
        Lists the cluster templates currently available to the tenancy.
        """
        self._log("Fetching available cluster templates")
        templates = list(
            self._client.api(AZIMUTH_API_VERSION).resource("clustertemplates").list()
        )

        # Filter cluster templates based on ACL annotations
        tenancy = self._cloud_session.tenancy()
        templates = [t for t in templates if allowed_by_acls(t, tenancy)]

        self._log("Found %s cluster templates", len(templates))
        return tuple(self._from_api_cluster_template(ct) for ct in templates)

    @convert_exceptions
    def find_cluster_template(self, id: str) -> dto.ClusterTemplate:  # noqa: A002
        """
        Finds a cluster template by id.
        """
        self._log("Fetching cluster template with id '%s'", id)
        template = (
            self._client.api(AZIMUTH_API_VERSION).resource("clustertemplates").fetch(id)
        )

        if not allowed_by_acls(template, self._cloud_session.tenancy()):
            raise errors.ObjectNotFoundError(f"Cannot find cluster template {id}")

        return self._from_api_cluster_template(template)

    def _from_api_cluster(self, cluster, sizes):
        """
        Converts a cluster from the Kubernetes API to a DTO.
        """
        cluster_addons = cluster.spec.get("addons", {})
        cluster_status = cluster.get("status", {})

        # We want to account for the case where a change has been made but the operator
        # has not yet caught up by tweaking the cluster state against what is reported
        cluster_state = cluster_status.get("phase")
        if cluster.metadata.get("deletionTimestamp"):
            # If the cluster has a deletion timestamp, flag it as deleting even if
            # the operator hasn't yet updated the status
            cluster_state = "Deleting"
        elif not cluster_state:
            # If there is no state, then the operator has not caught up after a create
            # So use Reconciling as the state in this case
            cluster_state = "Reconciling"
        elif cluster_state == "Unhealthy":
            # TODO(mkjpryor) find a better way to make sure unhealthy and reconciling
            #                are displayed as appropriate
            #
            # If the cluster is unhealthy, always expose this state regardless of what
            # the else clause below would decide to do
            #
            # This is because the last-handled-configuration is only updated when the
            # create/update handler executes successfully, meaning that if an error
            # occurs in the handler the cluster will stay reconciling forever if using
            # the logic from the else clause, even when the operator has moved it into
            # the unhealthy state due to the timeout
            #
            # This has the undesired effect that when a change is made to an unhealthy
            # cluster, it will not move to reconciling until the operator catches up
            # and starts making changes
            cluster_state = "Unhealthy"
        else:
            # Otherwise, we can compare the spec to the last handled configuration
            # If the template has changed, we have an upgrade
            # If anything else has changed, we have a reconciliation
            last_handled_configuration = json.loads(
                cluster.metadata.get("annotations", {}).get(
                    "azimuth.stackhpc.com/last-handled-configuration", "{}"
                )
            )
            last_handled_spec = last_handled_configuration.get("spec", {})
            if "templateName" not in last_handled_spec:
                cluster_state = "Reconciling"
            elif cluster.spec["templateName"] != last_handled_spec["templateName"]:
                cluster_state = "Upgrading"
            elif cluster.spec != last_handled_spec:
                cluster_state = "Reconciling"

        # If there is a schedule in the annotations, unserialize it
        annotations = cluster.metadata.get("annotations", {})
        schedule_json = annotations.get("azimuth.stackhpc.com/schedule")
        schedule = (
            scheduling_dto.PlatformSchedule.from_json(schedule_json)
            if schedule_json
            else None
        )

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
                None,
            ),
            [
                dto.NodeGroup(
                    ng["name"],
                    next(
                        (size.id for size in sizes if size.name == ng["machineSize"]),
                        None,
                    ),
                    ng.get("autoscale", False),
                    ng.get("count"),
                    ng.get("minCount"),
                    ng.get("maxCount"),
                )
                for ng in cluster.spec.get("nodeGroups", [])
            ],
            cluster.spec["autohealing"],
            cluster_addons.get("dashboard", False),
            cluster_addons.get("monitoring", False),
            cluster_addons.get("monitoringPrometheusVolumeSize", 10),
            cluster_addons.get("monitoringLokiVolumeSize", 10),
            cluster_status.get("kubernetesVersion"),
            cluster_state,
            cluster_status.get("controlPlanePhase", "Unknown"),
            [
                dto.Node(
                    name,
                    node["role"],
                    node.get("phase", "Unknown"),
                    next(
                        (size.id for size in sizes if size.name == node["size"]), None
                    ),
                    node.get("ip"),
                    node.get("kubeletVersion"),
                    node.get("nodeGroup"),
                    dateutil.parser.parse(node["created"]),
                )
                for name, node in cluster_status.get("nodes", {}).items()
            ],
            [
                dto.Addon(name, addon.get("phase", "Unknown"))
                for name, addon in cluster_status.get("addons", {}).items()
            ],
            [
                dto.Service(
                    name, service["label"], service["fqdn"], service.get("iconUrl")
                )
                for name, service in cluster_status.get("services", {}).items()
            ],
            dateutil.parser.parse(cluster.metadata["creationTimestamp"]),
            cluster.spec.get("createdByUsername"),
            cluster.spec.get("createdByUserId"),
            cluster.spec.get("updatedByUsername"),
            cluster.spec.get("updatedByUserId"),
            schedule,
        )

    @convert_exceptions
    def clusters(self) -> t.Iterable[dto.Cluster]:
        """
        Lists the clusters currently available to the tenancy.
        """
        self._log("Fetching available clusters")
        clusters = list(
            self._client.api(AZIMUTH_API_VERSION).resource("clusters").list()
        )
        self._log("Found %s clusters", len(clusters))
        if clusters:
            sizes = list(self._cloud_session.sizes())
            return tuple(self._from_api_cluster(c, sizes) for c in clusters)
        else:
            return ()

    @convert_exceptions
    def find_cluster(self, id: str) -> dto.Cluster:  # noqa: A002
        """
        Finds a cluster by id.
        """
        self._log("Fetching cluster with id '%s'", id)
        cluster = self._client.api(AZIMUTH_API_VERSION).resource("clusters").fetch(id)
        sizes = list(self._cloud_session.sizes())
        return self._from_api_cluster(cluster, sizes)

    def _create_credential(self, cluster_name):
        """
        Creates a new credential and returns the Kubernetes secret data.

        The return value should be a dict with the "data" and/or "stringData" keys.
        """
        credential = self._cloud_session.cloud_credential(
            f"az-kube-{cluster_name}",
            f"Used by Azimuth to manage Kubernetes cluster '{cluster_name}'.",
        )
        return credential.data

    def _ensure_shared_resources(self):
        """
        This method can be overridden by subclasses to ensure that any shared resources,
        such as networks, exist before a cluster is created.

        By default, it is a no-op.
        """

    def _build_cluster_spec(self, **options):
        """
        Translates API options into a CRD spec.
        """
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
        addons = spec.setdefault("addons", {})
        if "dashboard_enabled" in options:
            addons["dashboard"] = options["dashboard_enabled"]
        if "monitoring_enabled" in options:
            addons["monitoring"] = options["monitoring_enabled"]
        if "monitoring_metrics_volume_size" in options:
            addons["monitoringPrometheusVolumeSize"] = options[
                "monitoring_metrics_volume_size"
            ]
        if "monitoring_logs_volume_size" in options:
            addons["monitoringLokiVolumeSize"] = options["monitoring_logs_volume_size"]
        return spec

    @convert_exceptions
    def create_cluster(
        self,
        name: str,
        template: dto.ClusterTemplate,
        control_plane_size: cloud_dto.Size,
        node_groups: list[NodeGroupSpec],
        resources: scheduling_dto.PlatformResources,
        autohealing_enabled: bool = True,
        dashboard_enabled: bool = False,
        monitoring_enabled: bool = False,
        monitoring_metrics_volume_size: int | None = None,
        monitoring_logs_volume_size: int | None = None,
        zenith_identity_realm_name: str | None = None,
        schedule: scheduling_dto.PlatformSchedule | None = None,
    ) -> dto.Cluster:
        """
        Create a new cluster in the tenancy.
        """
        # Make sure that the target namespace exists
        utils.ensure_namespace(
            self._client, self._client.default_namespace, self._cloud_session.tenancy()
        )
        # Make sure any shared resources exist
        self._ensure_shared_resources()
        # Determine if leases are available on the target cluster
        leases_available = scheduling_k8s.leases_available(self._client)
        try:
            credential = self._create_credential(name)
        except cloud_errors.InvalidOperationError:
            raise errors.InvalidOperationError(f"Cluster '{name}' already exists")
        secret = self._client.client_side_apply_object(
            {
                "apiVersion": "v1",
                "kind": "Secret",
                "metadata": {
                    "name": f"{name}-cloud-credentials",
                    "labels": {
                        "app.kubernetes.io/managed-by": "azimuth",
                    },
                    "annotations": {
                        # If we are using leases, the lease will delete the appcred
                        # If not, we want the janitor to delete it
                        "janitor.capi.stackhpc.com/credential-policy": (
                            "keep" if leases_available else "delete"
                        ),
                    },
                },
                "stringData": credential,
            }
        )
        # Build the cluster spec
        options = dict(
            control_plane_size=control_plane_size,
            node_groups=node_groups,
            autohealing_enabled=autohealing_enabled,
            dashboard_enabled=dashboard_enabled,
            monitoring_enabled=monitoring_enabled,
        )
        if monitoring_metrics_volume_size is not None:
            options.update(
                monitoring_metrics_volume_size=monitoring_metrics_volume_size
            )
        if monitoring_logs_volume_size is not None:
            options.update(monitoring_logs_volume_size=monitoring_logs_volume_size)
        cluster_spec = self._build_cluster_spec(**options)
        # Add the create-only pieces
        cluster_spec.update(
            {
                "label": name,
                "templateName": template.id,
                "cloudCredentialsSecretName": secret.metadata.name,
                "createdByUsername": self._cloud_session.username(),
                "createdByUserId": self._cloud_session.user_id(),
            }
        )
        if leases_available:
            cluster_spec["leaseName"] = f"kube-{name}"
        if zenith_identity_realm_name:
            cluster_spec["zenithIdentityRealmName"] = zenith_identity_realm_name
        # Create the cluster
        ekclusters = self._client.api(AZIMUTH_API_VERSION).resource("clusters")
        cluster = ekclusters.create(
            {
                "metadata": {
                    "name": name,
                    "labels": {
                        "app.kubernetes.io/managed-by": "azimuth",
                    },
                    # Annotate the cluster with the serialized schedule object
                    # This is to avoid doing an N+1 query when we retrieve clusters
                    "annotations": (
                        {"azimuth.stackhpc.com/schedule": schedule.to_json()}
                        if schedule
                        else {}
                    ),
                },
                "spec": cluster_spec,
            }
        )
        # Create the scheduling resources for the cluster
        # This may or may not create a Blazar lease to reserve the resources
        scheduling_k8s.create_scheduling_resources(
            self._client,
            f"kube-{name}",
            cluster,
            cluster.spec["cloudCredentialsSecretName"],
            resources,
            schedule,
        )
        # Use the sizes that we already have
        sizes = [control_plane_size] + [ng["machine_size"] for ng in node_groups]
        return self._from_api_cluster(cluster, sizes)

    @convert_exceptions
    def update_cluster(self, cluster: dto.Cluster | str, **options):
        """
        Update the specified cluster with the given parameters.
        """
        if isinstance(cluster, dto.Cluster):
            cluster = cluster.id
        spec = self._build_cluster_spec(**options)
        spec["updatedByUsername"] = self._cloud_session.username()
        spec["updatedByUserId"] = self._cloud_session.user_id()
        cluster = (
            self._client.api(AZIMUTH_API_VERSION)
            .resource("clusters")
            .patch(cluster, {"spec": spec})
        )
        sizes = list(self._cloud_session.sizes())
        return self._from_api_cluster(cluster, sizes)

    @convert_exceptions
    def upgrade_cluster(
        self, cluster: dto.Cluster | str, template: dto.ClusterTemplate | str
    ) -> dto.Cluster:
        """
        Upgrade the specified cluster to the specified template.
        """
        if isinstance(cluster, dto.Cluster):
            cluster = cluster.id
        if not isinstance(template, dto.ClusterTemplate):
            template = self.find_cluster_template(template)

        # note who triggered the upgrade
        spec = {"templateName": template.id}
        spec["updatedByUsername"] = self._cloud_session.username()
        spec["updatedByUserId"] = self._cloud_session.user_id()

        # Apply a patch to the specified cluster to update the template
        ekclusters = self._client.api(AZIMUTH_API_VERSION).resource("clusters")
        cluster = ekclusters.patch(cluster, {"spec": spec})
        sizes = list(self._cloud_session.sizes())
        return self._from_api_cluster(cluster, sizes)

    @convert_exceptions
    def delete_cluster(self, cluster: dto.Cluster | str) -> dto.Cluster | None:
        """
        Delete the specified Kubernetes cluster.
        """
        if isinstance(cluster, dto.Cluster):
            cluster = cluster.id
        # Before deleting the cluster, check if the credential secret has a janitor
        # annotation
        # If it doesn't then it is a very old cluster from before the leases or janitor
        # integration, and we add the annotation so that the janitor removes the appcred
        secrets = self._client.api("v1").resource("secrets")
        try:
            secret = secrets.fetch(f"{cluster}-cloud-credentials")
        except ApiError as exc:
            if exc.status_code != 404:
                raise
        else:
            annotations = secret.metadata.get("annotations", {})
            if "janitor.capi.stackhpc.com/credential-policy" not in annotations:
                _ = secrets.patch(
                    secret.metadata.name,
                    {
                        "metadata": {
                            "annotations": {
                                "janitor.capi.stackhpc.com/credential-policy": "delete",
                            },
                        },
                    },
                )
        self._client.api(AZIMUTH_API_VERSION).resource("clusters").delete(
            cluster, propagation_policy="Foreground"
        )
        return self.find_cluster(cluster)

    @convert_exceptions
    def generate_kubeconfig(self, cluster: dto.Cluster | str) -> str:
        """
        Generate a kubeconfig for the specified cluster.
        """
        if isinstance(cluster, dto.Cluster):
            cluster = cluster.id
        self._log("Generating kubeconfig for cluster with id '%s'", id)
        cluster = (
            self._client.api(AZIMUTH_API_VERSION).resource("clusters").fetch(cluster)
        )
        # Just get the named secret
        kubeconfig_secret_name = cluster.get("status", {}).get("kubeconfigSecretName")
        if kubeconfig_secret_name:
            try:
                secret = (
                    self._client.api("v1")
                    .resource("secrets")
                    .fetch(kubeconfig_secret_name)
                )
            except ApiError as exc:
                if exc.status_code != 404:
                    raise
            else:
                # The kubeconfig is base64-encoded in the data
                return base64.b64decode(secret.data.value)
        raise errors.ObjectNotFoundError(
            f"Kubeconfig not available for cluster '{cluster.metadata.name}'"
        )

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
        # Work out what namespace to target for the tenancy
        namespace = utils.get_namespace(self._client, self._cloud_session.tenancy())
        # Set the target namespace as the default namespace for the client
        self._client.default_namespace = namespace
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
