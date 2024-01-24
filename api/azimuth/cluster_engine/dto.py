"""
This module defines data-transfer objects used by cluster engines.
"""

from dataclasses import dataclass, field
from datetime import datetime
import enum
import io
import json
import re
from typing import Any, Mapping, Optional, Sequence

import yaml
import requests

from ..provider import dto as cloud_dto


@dataclass(frozen = True)
class Context:
    """
    Represents a context for an operation.
    """
    #: The username of the user carrying out the operation
    username: str
    #: The user id of the user carrying out the operation
    user_id: str
    #: The tenancy that the operation is being carried out in
    tenancy: cloud_dto.Tenancy
    #: The cloud credential associated with the operation
    #: If the credential is not yet known, this should be None
    credential: Optional[cloud_dto.Credential] = None


@dataclass(frozen = True)
class ClusterParameter:
    """
    Represents a parameter required by a cluster type.
    """
    #: The name of the parameter
    name: str
    #: A human-readable label for the parameter
    label: str
    #: A description of the parameter
    description: Optional[str]
    #: The kind of the parameter
    kind: str
    #: A dictionary of kind-specific options for the parameter
    options: Mapping[str, Any]
    #: Indicates if the option is immutable, i.e. cannot be updated
    immutable: bool
    #: Indicates if the parameter is required
    required: bool
    #: A default value for the parameter
    default: Any
    #: Indicates whether or not the parameter should be hidden in the UI
    hidden: bool


@dataclass(frozen = True)
class ClusterServiceSpec:
    """
    Represents a Zenith service exposed by a cluster type (when apps are enabled).
    """
    #: The name of the service
    name: str
    #: A human-readable label for the service
    label: str
    #: The URL of an icon for the service
    icon_url: Optional[str]
    #: An expression indicating when the service is available
    when: Optional[str]


@dataclass(frozen = True)
class ClusterType:
    """
    Represents a cluster type.
    """
    #: The name of the cluster type
    name: str
    #: A human-readable label for the cluster type
    label: str
    #: A description of the cluster type
    description: Optional[str]
    #: The URL or data URI of the logo for the cluster type
    logo: Optional[str]
    #: Indicates whether the cluster requires a user SSH key
    requires_ssh_key: bool
    #: The parameters for the cluster type
    parameters: Sequence[ClusterParameter]
    #: The services for the cluster type
    services: Sequence[ClusterServiceSpec]
    #: Template for the usage of the clusters deployed using this type
    #: Can use Jinja2 syntax and should produce valid Markdown
    #: Receives the cluster parameters, as defined in `parameters`, as template args
    usage_template: Optional[str]
    #: Used by the Azimuth CRD to support patching
    version: Optional[str]

    @classmethod
    def from_dict(cls, name, spec, version=None):
        """
        Returns a new cluster type from the given dictionary specification.

        Args:
            spec: The cluster type specification as a ``dict``.

        Returns:
            A :py:class:`ClusterType`.
        """
        return cls(
            name,
            spec.get('label', name),
            spec.get('description'),
            spec.get('logo'),
            spec.get('requires_ssh_key', spec.get("requiresSshKey", True)),
            tuple(
                ClusterParameter(
                    param['name'],
                    param.get('label', param['name']),
                    param.get('description'),
                    param['kind'],
                    param.get('options', {}),
                    param.get('immutable', False),
                    param.get('required', True),
                    param.get('default', None),
                    param.get('hidden', False)
                )
                for param in spec.get('parameters', [])
            ),
            tuple(
                ClusterServiceSpec(
                    service['name'],
                    service.get('label', service['name']),
                    service.get('icon_url', service.get('iconUrl')),
                    service.get('when')
                )
                for service in spec.get('services', [])
            ),
            spec.get('usage_template', spec.get('usageTemplate', None)),
            version,
        )

    @classmethod
    def _open(cls, path):
        if re.match(r'https?://', path):
            response = requests.get(path)
            response.raise_for_status()
            return io.StringIO(response.text)
        else:
            return open(path)

    @classmethod
    def from_json(cls, name, path):
        """
        Returns a new cluster type from the given JSON file.

        Args:
            name: The name of the cluster type.
            path: Path to or URL of a JSON specification file.

        Returns:
            A :py:class:`ClusterType`.
        """
        with cls._open(path) as fh:
            return cls.from_dict(name, json.load(fh))

    @classmethod
    def from_yaml(cls, name, path):
        """
        Returns a new cluster type from the given YAML file.

        Args:
            name: The name of the cluster type.
            path: Path to or URL of a YAML specification file.

        Returns:
            A :py:class:`ClusterType`.
        """
        with cls._open(path) as fh:
            return cls.from_dict(name, yaml.safe_load(fh))


@enum.unique
class ClusterStatus(enum.Enum):
    """
    Enum for the possible cluster statuses.
    """
    CONFIGURING = 'CONFIGURING'
    READY = 'READY'
    DELETING = 'DELETING'
    ERROR = 'ERROR'


@dataclass(frozen = True)
class ClusterService:
    """
    Represents a Zenith service for a cluster.
    """
    #: The name of the service
    name: str
    #: A human-readable label for the service
    label: str
    #: The URL of an icon for the service
    icon_url: Optional[str]
    #: The FQDN for the service
    fqdn: str
    #: The subdomain for the service
    subdomain: str


@dataclass(frozen = True)
class Cluster:
    """
    Represents a cluster.
    """
    #: The id of the cluster
    id: str
    #: The name of the cluster
    name: str
    #: The name of the cluster type of the cluster
    cluster_type: str
    #: The status of the cluster
    status: ClusterStatus
    #: Description of the currently executing task, or None if no task is executing
    task: Optional[str]
    #: Description of the error that occured, or None if there is no error
    error_message: Optional[str]
    #: Dictionary containing the current parameter values
    parameter_values: Mapping[str, Any]
    #: A list of tags describing the cluster
    tags: Sequence[str]
    #: Dictionary of output variables
    outputs: Mapping[str, Any]
    #: The datetime at which the cluster was created
    created: datetime
    #: The datetime at which the cluster was updated
    updated: datetime
    #: The datetime at which the cluster was last patched
    patched: datetime
    #: A list of Zenith services enabled for the cluster
    services: Sequence[ClusterService] = field(default_factory = list)
    #: Details about the users interacting with the cluster
    created_by_username: Optional[str] = None
    created_by_user_id: Optional[str] = None
    updated_by_username: Optional[str] = None
    updated_by_user_id: Optional[str] = None
