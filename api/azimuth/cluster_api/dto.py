import dataclasses
import datetime
import typing as t


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
    #: The number of machines in the node group
    count: int


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
    #: The internal IP of the node
    ip: t.Optional[str]
    #: The kubelet version of the node
    kubelet_version: t.Optional[str]
    #: The node group of the node
    node_group: t.Optional[str]


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
    #: Indicates if cert-manager is enabled
    cert_manager_enabled: bool
    #: Indicates if ingress is enabled
    ingress_enabled: bool
    #: Indicates if monitoring is enabled
    monitoring_enabled: bool
    #: The Kubernetes version of the cluster
    kubernetes_version: t.Optional[str]
    #: The overall status of the cluster
    status: t.Optional[str]
    #: The status of the control plane
    control_plane_status: t.Optional[str]
    #: The status of the cluster addons
    addons_status: t.Optional[str]
    #: The nodes in the cluster
    nodes: t.List[Node]
    #: The time at which the cluster was created
    created_at: datetime.datetime
