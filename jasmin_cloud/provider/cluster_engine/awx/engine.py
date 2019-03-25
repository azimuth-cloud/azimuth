"""
This module contains the cluster engine implementation for AWX.
"""

import logging
import functools
import io
import json
import uuid

import dateutil.parser

from . import api
from .. import base
from ... import dto, errors


logger = logging.getLogger(__name__)


def convert_api_exceptions(func):
    """
    Decorator that converts api exceptions into provider errors.
    """
    @functools.wraps(func)
    def decorator(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except:
            raise
    return decorator


class Engine(base.Engine):
    """
    Cluster engine implementation for AWX.

    Args:
        url: The AWX API url.
        username: The username of the service account to use.
        password: The password of the service account.
        credential_type: The name of the credential type to use.
        verify_ssl: Whether to verify SSL connections to AWX.
        template_inventory: The name of the template inventory.
    """
    def __init__(self, url,
                       username,
                       password,
                       credential_type,
                       verify_ssl = True,
                       template_inventory = 'openstack'):
        self._url = url.rstrip('/')
        self._username = username
        self._password = password
        self._verify_ssl = verify_ssl
        self._template_inventory = template_inventory
        self._credential_type = credential_type

    def create_manager(self, username, tenancy):
        """
        See :py:meth:`.base.Engine.create_manager`.
        """
        logger.info("Starting AWX connection")
        connection = api.Connection(
            self._url,
            self._username,
            self._password,
            self._verify_ssl
        )
        organisation = connection.organisation.fetch_one()
        template_inventory = connection.inventory.fetch_one(
            name = self._template_inventory
        )
        credential_type = connection.credential_type.fetch_one(
            name = self._credential_type
        )
        try:
            team = connection.team.fetch_one(name__iexact = tenancy.name)
            logger.info("Found AWX team '%s'", team.name)
            return ClusterManager(
                username,
                connection,
                organisation,
                credential_type,
                template_inventory,
                team
            )
        except api.NotFound:
            logger.warn("Could not find AWX team '%s'", tenancy.name)
            return None


class ClusterManager(base.ClusterManager):
    """
    Cluster manager implementation for AWX.

    Cluster types correspond to available job templates, and clusters correspond
    to inventories. A cluster is configured by launching a job using the job
    template for the cluster type and the cluster inventory.
    """
    def __init__(self, username,
                       connection,
                       organisation,
                       credential_type,
                       template_inventory,
                       team):
        self._username = username
        self._connection = connection
        self._organisation = organisation
        self._credential_type = credential_type
        self._template_inventory = template_inventory
        self._team = team

    def _log(self, message, *args, level = logging.INFO, **kwargs):
        logger.log(
            level,
            '[%s] [%s] ' + message,
            self._username,
            self._team.name,
            *args,
            **kwargs
        )

    def cluster_types(self):
        """
        See :py:meth:`.base.ClusterManager.cluster_types`.
        """
        # Get the names of the job temaplates that the team has been
        # granted execute access for
        self._log("Fetching team permissions")
        permitted = [
            role.summary_fields['resource_name']
            for role in self._team.fetch_related('roles')
            if role.name.lower() == 'execute' and
               role.summary_fields['resource_type'] == 'job_template'
        ]
        self._log("Found %s permitted job templates", len(permitted))
        # Convert to DTO objects
        return tuple(self.find_cluster_type(name) for name in permitted)

    def find_cluster_type(self, name):
        """
        See :py:meth:`.base.ClusterManager.find_cluster_type`.
        """
        self._log("Fetching job template '%s'", name)
        try:
            job_template = self._connection.job_template.fetch_one(name = name)
        except api.NotFound:
            raise errors.ObjectNotFoundError("Could not find cluster type '{}'".format(name))
        if not job_template.description:
            raise errors.ImproperlyConfiguredError(
                "No metadata specified for cluster type '{}'".format(name)
            )
        self._log("Loading metadata from {}".format(job_template.description))
        return dto.ClusterType.from_yaml(name, job_template.description)

    def clusters(self):
        """
        See :py:meth:`.base.ClusterManager.clusters`.
        """
        # Inventories for a tenancy are prefixed with the tenancy name
        prefix = "{}-".format(self._team.name)
        self._log("Fetching inventories")
        inventories = self._connection.inventory.fetch_all(name__istartswith = prefix)
        self._log("Found %s inventories", len(inventories))
        # find_cluster might raise ObjectNotFoundError for inventories representing a
        # deleted cluster
        def active_inventories(inventories):
            for inventory in inventories:
                try:
                    yield self.find_cluster(inventory.id)
                except errors.ObjectNotFoundError:
                    pass
        return tuple(active_inventories(inventories))

    def find_cluster(self, id):
        """
        See :py:meth:`.base.ClusterManager.find_cluster`.
        """
        # First, load the inventory
        self._log("Fetching inventory with id '%s'", id)
        try:
            inventory = self._connection.inventory.fetch_one(id)
        except api.NotFound:
            raise errors.ObjectNotFoundError(
                "Could not find cluster with ID {}".format(id)
            )
        if not inventory.name.startswith(self._team.name):
            raise errors.ObjectNotFoundError(
                "Could not find cluster with ID {}".format(id)
            )
        # Get the inventory variables
        params = dict(inventory.fetch_related('variable_data'))
        # Extract the parameters that aren't really parameters
        name = params.pop('cluster_name')
        cluster_type = params.pop('cluster_type')
        cluster_state = params.pop('cluster_state', 'present')
        # Get the jobs for the inventory
        jobs = self._connection.job.fetch_all(
            inventory = inventory.id,
            order_by = '-started'
        )
        # The status of the cluster is the status of the latest job
        try:
            latest = next(iter(jobs))
        except StopIteration:
            # There should be at least one job...
            status = dto.Cluster.Status.ERROR
        else:
            if latest.status in {'new', 'pending', 'waiting', 'running'}:
                if cluster_state == 'present':
                    status = dto.Cluster.Status.CONFIGURING
                else:
                    status = dto.Cluster.Status.DELETING
            elif latest.status == 'successful':
                # If the last job was a successful delete, pretend
                # that the cluster doesn't exist any more
                if cluster_state == 'present':
                    status = dto.Cluster.Status.READY
                else:
                    raise errors.ObjectNotFoundError(
                        "Could not find cluster with ID {}".format(id)
                    )
            else:
                status = dto.Cluster.Status.ERROR
        # The updated time is the start time of the last successful job
        try:
            func = lambda j: j.status == 'successful'
            updated = next(iter(filter(func, jobs))).started
        except StopIteration:
            updated = inventory.created
        # The patched time is the start time of the last successful job
        # with the "cluster_upgrade_system_packages" variable set to true
        try:
            func = lambda j: (
                j.status == 'successful' and
                json.loads(j.extra_vars).get('cluster_upgrade_system_packages', False)
            )
            patched = next(iter(filter(func, jobs))).started
        except StopIteration:
            patched = inventory.created
        return dto.Cluster(
            inventory.id,
            name,
            cluster_type,
            status,
            params,
            dateutil.parser.parse(inventory.created),
            dateutil.parser.parse(updated),
            dateutil.parser.parse(patched)
        )

    def _update_and_run_inventory(self, cluster_type,
                                        inventory,
                                        credential_inputs,
                                        inventory_variables = {},
                                        extra_vars = {}):
        """
        Utility method to update inventory variables, create a credential
        and run a job.
        """
        self._log("Finding job template '%s'", cluster_type)
        try:
            job_template = self._connection.job_template.fetch_one(name = cluster_type)
        except api.NotFound:
            raise errors.ObjectNotFoundError(
                "Could not find cluster type '%s'",
                cluster_type
            )
        self._log("Updating inventory variables for '%s'", inventory.name)
        inventory.update_related(
            'variable_data',
            **dict(
                inventory.fetch_related('variable_data'),
                **inventory_variables
            )
        )
        self._log("Creating credential to run job")
        credential = self._connection.credential.create(
            name = str(uuid.uuid4()),
            organization = self._organisation.id,
            credential_type = self._credential_type.id,
            inputs = credential_inputs
        )
        self._log("Executing job for inventory '%s'", inventory.name)
        # Once everything is updated, launch a job
        job_template.create_related(
            'launch',
            inventory = inventory.id,
            credentials = [credential.id],
            extra_vars = json.dumps(extra_vars)
        )
        # Evict the inventory from the cache as it has changed
        self._connection.inventory.cache_evict(inventory.id)

    def create_cluster(self, name, cluster_type, params, credential):
        """
        See :py:meth:`.base.ClusterManager.create_cluster`.
        """
        if isinstance(cluster_type, dto.ClusterType):
            cluster_type = cluster_type.name
        # The inventory name is prefixed with the tenancy name
        inventory_name = "{}-{}".format(self._team.name, name)
        self._log("Try to find existing inventory '%s'", inventory_name)
        # Try to find an existing inventory with the name we want to use
        try:
            inventory = self._connection.inventory.fetch_one(name = inventory_name)
        except api.NotFound:
            # Not found is great!
            self._log("No inventory called '%s' exists", inventory_name)
            pass
        else:
            self._log("Existing inventory called '%s' found", inventory_name)
            # If there is an existing inventory, try to fetch the corresponding cluster
            try:
                _ = self.find_cluster(inventory.id)
            except errors.ObjectNotFoundError:
                self._log("Inventory '%s' represents deleted cluster - removing", inventory_name)
                # If the cluster is not found, that means the inventory represents
                # a deleted cluster, so delete it
                self._connection.inventory.delete(inventory)
            else:
                # If the cluster also exists, this is a bad request
                raise errors.BadInputError("A cluster called '%s' aleady exists.", name)
        self._log("Copying template inventory as '%s'", inventory_name)
        inventory = self._connection.inventory.copy(
            self._template_inventory.id,
            inventory_name
        )
        # Update the inventory variables and execute the creation job
        self._update_and_run_inventory(
            cluster_type,
            inventory,
            credential,
            dict(
                params,
                cluster_name = name,
                cluster_type = cluster_type
            )
        )
        return self.find_cluster(inventory.id)

    def update_cluster(self, cluster, params, credential):
        """
        See :py:meth:`.base.ClusterManager.update_cluster`.
        """
        # Start by re-fetching the cluster - it might already have been deleted or have a
        # currently running job
        if isinstance(cluster, dto.Cluster):
            cluster = cluster.id
        cluster = self.find_cluster(cluster)
        if cluster.status in {dto.Cluster.Status.CONFIGURING, dto.Cluster.Status.DELETING}:
            raise errors.InvalidOperationError(
                'Cannot update cluster with status {}'.format(cluster.status.name)
            )
        self._log("Updating cluster '%s'", cluster.id)
        # Update the inventory with the given parameters
        self._update_and_run_inventory(
            cluster.cluster_type,
            self._connection.inventory.fetch_one(cluster.id),
            credential,
            params
        )
        # Refetch the cluster to get the new status
        return self.find_cluster(cluster.id)

    def patch_cluster(self, cluster, credential):
        """
        See :py:meth:`.base.ClusterManager.patch_cluster`.
        """
        # Start by re-fetching the cluster - it might already have been deleted or have a
        # currently running job
        if isinstance(cluster, dto.Cluster):
            cluster = cluster.id
        cluster = self.find_cluster(cluster)
        if cluster.status in {dto.Cluster.Status.CONFIGURING, dto.Cluster.Status.DELETING}:
            raise errors.InvalidOperationError(
                'Cannot patch cluster with status {}'.format(cluster.status.name)
            )
        self._log("Patching cluster '%s'", cluster.id)
        # Update the inventory with the given parameters
        self._update_and_run_inventory(
            cluster.cluster_type,
            self._connection.inventory.fetch_one(cluster.id),
            credential,
            extra_vars = dict(cluster_upgrade_system_packages = True)
        )
        # Refetch the cluster to get the new status
        return self.find_cluster(cluster.id)

    def delete_cluster(self, cluster, credential):
        """
        See :py:meth:`.base.ClusterManager.delete_cluster`.
        """
        # Start by re-fetching the cluster - it might already have been deleted
        if isinstance(cluster, dto.Cluster):
            cluster = cluster.id
        cluster = self.find_cluster(cluster)
        if cluster.status in {dto.Cluster.Status.CONFIGURING, dto.Cluster.Status.DELETING}:
            raise errors.InvalidOperationError(
                'Cannot delete cluster with status {}'.format(cluster.status.name)
            )
        self._log("Deleting cluster '%s'", cluster.id)
        # Update the inventory to have cluster_state = absent
        inventory = self._connection.inventory.fetch_one(cluster.id)
        self._update_and_run_inventory(
            cluster.cluster_type,
            inventory,
            credential,
            dict(cluster_state = 'absent')
        )
        return self.find_cluster(inventory.id)

    def close(self):
        self._connection.close()
