import dataclasses
import datetime
import typing as t

from ..scheduling import dto as scheduling_dto


@dataclasses.dataclass(frozen = True)
class ClusterTemplate:
    """
    Represents a template for Kubernetes clusters.
    """
    #: The id of the template
    id: str
    #: The human-readable name of the template
    name: str
    #: A brief description of the template
    description: t.Optional[str]
    #: The Kubernetes version that this template will deploy
    kubernetes_version: str
    #: Indicates if this is a deprecated template
    deprecated: bool
    #: The number of control plane nodes that this template will deploy
    control_plane_count: int
    #: The size of the volumes that will be used for etcd (0 for no separate volume)
    etcd_volume_size: int
    #: The size of the volumes used for control plane nodes (0 for ephemeral root disk)
    control_plane_root_volume_size: int
    #: The size of the volumes used for worker nodes (0 for ephemeral root disk)
    node_group_root_volume_size: int
    #: The tags for the template
    tags: t.List[str]
    #: The datetime at which the template was created
    created_at: datetime.datetime


@dataclasses.dataclass(frozen = True)
class NodeGroup:
    """
    Represents a node group in a cluster.
    """
    #: The name of the node group
    name: str
    #: The id of the size of machines in the node group
    machine_size_id: str
    #: Indicates if the node group should autoscale
    autoscale: bool
    #: The fixed number of nodes in the node group when autoscale is false
    count: t.Optional[int]
    #: The minimum number of nodes in the node group when autoscale is true
    min_count: t.Optional[int]
    #: The maximum number of nodes in the node group when autoscale is true
    max_count: t.Optional[int]


@dataclasses.dataclass(frozen = True)
class Node:
    """
    Represents a node in the cluster.
    """
    #: The name of the node
    name: str
    #: The role of the node in the cluster
    role: str
    #: The status of the node
    status: str
    #: The id of the size of the node
    size_id: str
    #: The internal IP of the node
    ip: t.Optional[str]
    #: The kubelet version of the node
    kubelet_version: t.Optional[str]
    #: The node group of the node
    node_group: t.Optional[str]
    #: The time at which the node was created
    created_at: datetime.datetime


@dataclasses.dataclass(frozen = True)
class Addon:
    """
    Represents an addon in the cluster.
    """
    #: The name of the addon
    name: str
    #: The status of the addon
    status: str


@dataclasses.dataclass(frozen = True)
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
    icon_url: t.Optional[str]


@dataclasses.dataclass(frozen = True)
class Cluster:
    """
    Represents a Kubernetes cluster.
    """
    #: The id of the cluster
    id: str
    #: The human-readable name of the cluster
    name: str
    #: The id of the template for the cluster
    template_id: str
    #: The id of the size of the control plane nodes
    control_plane_size_id: str
    #: The node groups in the cluster
    node_groups: t.List[NodeGroup]
    #: Indicates if autohealing is enabled
    autohealing_enabled: bool
    #: Indicates if the Kubernetes dashboard is enabled
    dashboard_enabled: bool
    #: Indicates if ingress is enabled
    ingress_enabled: bool
    #: The IP address of the ingress controller load balancer
    ingress_controller_load_balancer_ip: t.Optional[str]
    #: Indicates if monitoring is enabled
    monitoring_enabled: bool
    #: The size of the volume to use for metrics data
    monitoring_metrics_volume_size: int
    #: The size of the volume to use for logging data
    monitoring_logs_volume_size: int
    #: The Kubernetes version of the cluster
    kubernetes_version: t.Optional[str]
    #: The overall status of the cluster
    status: t.Optional[str]
    #: The status of the control plane
    control_plane_status: t.Optional[str]
    #: The nodes in the cluster
    nodes: t.List[Node]
    #: The addons for the cluster
    addons: t.List[Addon]
    #: The services for the cluster
    services: t.List[Service]
    #: The time at which the cluster was created
    created_at: datetime.datetime
    #: Details about the users interacting with the cluster
    created_by_username: t.Optional[str]
    created_by_user_id: t.Optional[str]
    updated_by_username: t.Optional[str]
    updated_by_user_id: t.Optional[str]
    #: Scheduling information for the cluster
    schedule: t.Optional[scheduling_dto.PlatformSchedule] = None
