"""
This module defines a mock implementation of a cluster engine.
"""

import uuid
import json
from functools import reduce
from datetime import datetime
import dateutil.parser

from .. import dto, errors
from . import base


class Engine(base.Engine):
    """
    Base class for a cluster engine.
    """
    def __init__(self, cluster_types, clusters_file):
        self._cluster_types = cluster_types
        self._clusters_file = clusters_file

    def create_manager(self, username, tenancy):
        """
        Creates a cluster manager for the given tenancy.

        Args:
            tenancy: The :py:class:`~..provider.dto.Tenancy`.

        Returns:
            A :py:class:`ClusterManager`.
        """
        return ClusterManager(self._cluster_types, self._clusters_file)


class ClusterManager(base.ClusterManager):
    """
    Base class for a tenancy-scoped cluster manager.
    """
    def __init__(self, cluster_types, clusters_file):
        self._cluster_types = cluster_types
        self._clusters_file = clusters_file

    def cluster_types(self):
        return tuple(self._cluster_types)

    def find_cluster_type(self, name):
        try:
            return next(ct for ct in self.cluster_types() if ct.name == name)
        except StopIteration:
            raise errors.ObjectNotFoundError("Could not find cluster type '{}'".format(name))

    def clusters(self):
        with open(self._clusters_file) as fh:
            return tuple(
                dto.Cluster(
                    c['id'],
                    c['name'],
                    c['cluster_type'],
                    dto.Cluster.Status[c['status']],
                    None,
                    None,
                    c['parameter_values'],
                    tuple(c.get('tags', [])),
                    dateutil.parser.parse(c['created']),
                    dateutil.parser.parse(c['updated']),
                    dateutil.parser.parse(c['patched'])
                )
                for c in json.load(fh)
            )

    def find_cluster(self, id):
        try:
            return next(c for c in self.clusters() if c.id == id)
        except StopIteration:
            raise errors.ObjectNotFoundError("Could not find cluster '{}'".format(id))

    def create_cluster(self, name, cluster_type, params, *args, **kwargs):
        with open(self._clusters_file) as fh:
            clusters = json.load(fh)
        id = str(uuid.uuid4())
        clusters.append({
            'id': id,
            'name': name,
            'cluster_type': cluster_type.name,
            'status': dto.Cluster.Status.CONFIGURING.name,
            'parameter_values': params,
            'created': datetime.now().isoformat(),
            'updated': datetime.now().isoformat(),
            'patched': datetime.now().isoformat()
        })
        with open(self._clusters_file, 'w') as fh:
            json.dump(clusters, fh, indent = 2)
        return self.find_cluster(id)

    def update_cluster(self, cluster, params, *args, **kwargs):
        cluster = cluster.id if isinstance(cluster, dto.Cluster) else cluster
        with open(self._clusters_file) as fh:
            clusters = json.load(fh)
        for c in clusters:
            if c['id'] == cluster:
                c['parameter_values'].update(params)
                c.update(
                    status = dto.Cluster.Status.CONFIGURING.name,
                    updated = datetime.now().isoformat()
                )
                break
        else:
            raise errors.ObjectNotFoundError("Could not find cluster '{}'".format(cluster))
        with open(self._clusters_file, 'w') as fh:
            json.dump(clusters, fh, indent = 2)
        return self.find_cluster(cluster)

    def patch_cluster(self, cluster, *args, **kwargs):
        cluster = cluster.id if isinstance(cluster, dto.Cluster) else cluster
        with open(self._clusters_file) as fh:
            clusters = json.load(fh)
        for c in clusters:
            if c['id'] == cluster:
                c.update(
                    status = dto.Cluster.Status.CONFIGURING.name,
                    patched = datetime.now().isoformat()
                )
                break
        else:
            raise errors.ObjectNotFoundError("Could not find cluster '{}'".format(cluster))
        with open(self._clusters_file, 'w') as fh:
            json.dump(clusters, fh, indent = 2)
        return self.find_cluster(cluster)

    def delete_cluster(self, cluster, *args, **kwargs):
        cluster = cluster if isinstance(cluster, dto.Cluster) else self.find_cluster(cluster)
        with open(self._clusters_file) as fh:
            clusters = json.load(fh)
        clusters = [c for c in clusters if c['id'] != cluster.id]
        with open(self._clusters_file, 'w') as fh:
            json.dump(clusters, fh, indent = 2)
        return cluster._replace(status = dto.Cluster.Status.DELETING)
