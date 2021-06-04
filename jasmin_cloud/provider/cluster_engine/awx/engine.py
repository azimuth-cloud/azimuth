"""
This module contains the cluster engine implementation for AWX.
"""

import logging
import json
import uuid

import dateutil.parser

import rackit

from . import api
from .. import base
from ... import dto, errors


logger = logging.getLogger(__name__)


class Engine(base.Engine):
    """
    Cluster engine implementation for AWX.

    Args:
        url: The AWX API url.
        username: The username of the service account to use.
        password: The password of the service account.
        credential_type: The name of the credential type to use.
        create_teams: Whether to create teams which do not exist.
        verify_ssl: Whether to verify SSL connections to AWX.
        template_inventory: The name of the template inventory.
    """
    def __init__(self, url,
                       username,
                       password,
                       credential_type,
                       create_teams = False,
                       create_team_allow_all_permission = False,
                       verify_ssl = True,
                       template_inventory = 'openstack'):
        self._url = url.rstrip('/')
        self._username = username
        self._password = password
        self._verify_ssl = verify_ssl
        self._template_inventory = template_inventory
        self._credential_type = credential_type
        self._create_teams = create_teams
        self._create_team_allow_all_permission = create_team_allow_all_permission

    def _create_team(self, connection, organisation, name):
        """
        Create the specified team and, if configured, the allow-all permission.
        """
        team = connection.teams.create(name = name, organization = organisation.id)
        if self._create_team_allow_all_permission:
            # Find the execute role for the organisation
            execute_role = next(
                role
                for role in connection.roles.all()
                if (
                    role.name.lower() == 'execute' and
                    role.summary_fields.get('resource_type') == 'organization' and
                    role.summary_fields.get('resource_id') == organisation.id
                )
            )
            # Associate the role with the newly created team
            connection.api_post(f"/teams/{team.id}/roles/", json = dict(id = execute_role.id))
        return team

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
        try:
            organisation = next(connection.organisations.all(), None)
            if not organisation:
                raise errors.ImproperlyConfiguredError('Could not find organisation.')
            template_inventory = connection.inventories.find_by_name(self._template_inventory)
            if not template_inventory:
                raise errors.ImproperlyConfiguredError('Could not find template inventory.')
            credential_type = connection.credential_types.find_by_name(self._credential_type)
            if not credential_type:
                raise errors.ImproperlyConfiguredError('Could not find credential type.')
        except:
            connection.close()
            raise
        team = next(connection.teams.all(name__iexact = tenancy.name), None)
        if team:
            logger.info("Found AWX team '%s'", team.name)
        elif self._create_teams:
            logger.info("Creating AWX team '%s'", tenancy.name)
            team = self._create_team(connection, organisation, tenancy.name)
        if team:
            return ClusterManager(
                username,
                connection,
                organisation,
                credential_type,
                template_inventory,
                team
            )
        else:
            logger.warn("Could not find AWX team '%s'", tenancy.name)
            connection.close()
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

    def _from_job_template(self, job_template):
        """
        Returns a cluster template from the given job template.
        """
        if not job_template.description:
            raise errors.ImproperlyConfiguredError(
                "No metadata specified for cluster type '{}'".format(job_template.name)
            )
        self._log("Loading metadata from {}".format(job_template.description))
        return dto.ClusterType.from_yaml(job_template.name, job_template.description)

    def cluster_types(self):
        """
        See :py:meth:`.base.ClusterManager.cluster_types`.
        """
        # Get the names of the job temaplates that the team has been
        # granted execute access for
        self._log("Fetching team permissions")
        # First, get the team roles
        roles = list(self._team.roles.all())
        # If the team has the execute permission on the organisation, then they are
        # permitted to access all the templates
        all_permitted = any(
            (
                role.name.lower() == 'execute' and
                role.summary_fields['resource_type'] == 'organization' and
                role.summary_fields['resource_id'] == self._organisation.id
            )
            for role in roles
        )
        # Otherwise, the team may have been granted the execute permission on
        # individual job templates
        if all_permitted:
            permitted = {}
        else:
            permitted = {
                role.summary_fields['resource_name']
                for role in roles
                if (
                    role.name.lower() == 'execute' and
                    role.summary_fields['resource_type'] == 'job_template'
                )
            }
        self._log("Found %s permitted job templates", len(permitted))
        if all_permitted or permitted:
            # Fetch the job templates, filter the allowed ones and return the cluster types
            return tuple(
                self._from_job_template(jt)
                for jt in self._connection.job_templates.all()
                if all_permitted or jt.name in permitted
            )
        else:
            return ()

    def find_cluster_type(self, name):
        """
        See :py:meth:`.base.ClusterManager.find_cluster_type`.
        """
        self._log("Fetching job template '%s'", name)
        job_template = self._connection.job_templates.find_by_name(name)
        if not job_template:
            raise errors.ObjectNotFoundError("Could not find cluster type '{}'".format(name))
        return self._from_job_template(job_template)

    def _from_inventory(self, inventory):
        """
        Returns a cluster from the given inventory.
        """
        # Get the inventory variables
        params = inventory.variable_data._as_dict()
        # Extract the parameters that aren't really parameters
        name = params.pop('cluster_name')
        cluster_type = params.pop('cluster_type')
        ssh_key = params.pop('cluster_user_ssh_public_key')
        # Get the jobs for the inventory
        jobs = self._connection.jobs.all(inventory = inventory.id, order_by = '-started')
        # The status of the cluster is the status of the latest job
        task = None
        error_message = None
        # The updated and patched times are based on successful jobs
        # The patched time is from a job with cluster_upgrade_system_packages = True
        updated = None
        patched = None
        try:
            latest = next(jobs)
        except StopIteration:
            # There should be at least one job...
            status = dto.Cluster.Status.ERROR
        else:
            # The cluster_state comes from the extra vars of the most recent job
            latest_extra_vars = json.loads(latest.extra_vars)
            cluster_state = latest_extra_vars.get('cluster_state', 'present')
            if latest.status == 'successful':
                if cluster_state == 'present':
                    status = dto.Cluster.Status.READY
                    updated = latest.finished
                    if latest_extra_vars.get('cluster_upgrade_system_packages', False):
                        patched = latest.finished
                else:
                    self._log("Inventory '%s' represents deleted cluster - removing", inventory.name)
                    # If the last job was a successful delete, delete the inventory
                    inventory._delete()
                    # Inventories don't always delete straight away, so try up to five times
                    remaining = 5
                    while remaining > 0:
                        try:
                            inventory = self._connection.inventories.get(inventory.id)
                        except rackit.NotFound:
                            break
                        else:
                            # Evict the inventory from the cache so it isn't cached for future accesses
                            self._connection.inventories.cache.evict(inventory.id)
                            remaining = remaining - 1
                    else:
                        raise errors.OperationTimedOutError('Timed out while removing inventory.')
                    raise errors.ObjectNotFoundError(
                        "Could not find cluster with ID {}".format(id)
                    )
            elif latest.status == 'canceled':
                status = dto.Cluster.Status.ERROR
                error_message = 'Cluster configuration cancelled by an administrator.'
            elif latest.status in {'failed', 'error'}:
                status = dto.Cluster.Status.ERROR
                # Try to retrieve an error from the failed task
                event = next(
                    latest.job_events.all(event = 'runner_on_failed', order_by = '-created'),
                    None
                )
                msg = getattr(event, 'event_data', {}).get('res', {}).get('msg')
                error_message = msg or 'Error during cluster configuration. Please contact support.'
            else:
                if cluster_state == 'present':
                    status = dto.Cluster.Status.CONFIGURING
                else:
                    status = dto.Cluster.Status.DELETING
                # Find the name of the currently executing task
                task = next(
                    (
                        event.task
                        for event in latest.job_events.all(
                            event = 'playbook_on_task_start',
                            order_by = '-created'
                        )
                    ),
                    None
                )
        # If we haven't found the update or patch time, traverse the rest of the jobs until we find them
        while not updated or not patched:
            try:
                job = next(jobs)
            except StopIteration:
                break
            if job.status != 'successful':
                continue
            updated = updated or job.finished
            if json.loads(job.extra_vars).get('cluster_upgrade_system_packages', False):
                patched = patched or job.finished
        return dto.Cluster(
            inventory.id,
            name,
            cluster_type,
            status,
            task,
            error_message,
            params,
            (),
            dateutil.parser.parse(inventory.created),
            dateutil.parser.parse(updated) if updated else None,
            dateutil.parser.parse(patched) if patched else None
        )

    def clusters(self):
        """
        See :py:meth:`.base.ClusterManager.clusters`.
        """
        # Inventories for a tenancy are prefixed with the tenancy name
        prefix = "{}-".format(self._team.name)
        self._log("Fetching inventories")
        inventories = list(self._connection.inventories.all(name__istartswith = prefix))
        self._log("Found %s inventories", len(inventories))
        # If any of the clusters raise ObjectNotFound while iterating, omit them
        def active_inventories(inventories):
            for inventory in inventories:
                try:
                    yield self._from_inventory(inventory)
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
            inventory = self._connection.inventories.get(id)
        except rackit.NotFound:
            raise errors.ObjectNotFoundError(
                "Could not find cluster with ID {}".format(id)
            )
        if not inventory.name.startswith(self._team.name):
            raise errors.ObjectNotFoundError(
                "Could not find cluster with ID {}".format(id)
            )
        return self._from_inventory(inventory)

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
        job_template = self._connection.job_templates.find_by_name(cluster_type)
        if not job_template:
            raise errors.ObjectNotFoundError(
                "Could not find cluster type '%s'",
                cluster_type
            )
        self._log("Updating inventory variables for '%s'", inventory.name)
        variable_data = inventory.variable_data._as_dict()
        variable_data.update(inventory_variables)
        inventory.variable_data._update(variable_data)
        self._log("Creating credential to run job")
        credential = self._connection.credentials.create(
            name = str(uuid.uuid4()),
            organization = self._organisation.id,
            credential_type = self._credential_type.id,
            inputs = credential_inputs
        )
        self._log("Executing job for inventory '%s'", inventory.name)
        # Append the cloud credential to the existing creds for the template
        credentials = [c['id'] for c in job_template.summary_fields['credentials']]
        credentials.append(credential.id)
        # Once everything is updated, launch a job
        job_template.launch(
            inventory = inventory.id,
            credentials = credentials,
            extra_vars = json.dumps(extra_vars)
        )
        # Evict the inventory from the cache as it has changed
        self._connection.inventories.cache.evict(inventory)

    def create_cluster(self, name, cluster_type, params, ssh_key, credential):
        """
        See :py:meth:`.base.ClusterManager.create_cluster`.
        """
        if isinstance(cluster_type, dto.ClusterType):
            cluster_type = cluster_type.name
        # The inventory name is prefixed with the tenancy name
        inventory_name = "{}-{}".format(self._team.name, name)
        self._log("Try to find existing inventory '%s'", inventory_name)
        # Try to find an existing inventory with the name we want to use
        inventory = self._connection.inventories.find_by_name(inventory_name)
        if not inventory:
            # Not found is great!
            self._log("No inventory called '%s' exists", inventory_name)
        else:
            self._log("Existing inventory called '%s' found", inventory_name)
            # If there is an existing inventory, try to fetch the corresponding cluster
            try:
                _ = self.find_cluster(inventory.id)
            except errors.ObjectNotFoundError:
                # If the cluster is not found, that means the inventory will have
                # been removed and we can continue
                pass
            else:
                # If the cluster also exists, this is a bad request
                raise errors.BadInputError("A cluster called '%s' aleady exists.", name)
        self._log("Copying template inventory as '%s'", inventory_name)
        inventory = self._connection.inventories.copy(self._template_inventory.id, inventory_name)
        # Update the inventory variables and execute the creation job
        self._update_and_run_inventory(
            cluster_type,
            inventory,
            credential,
            dict(
                params,
                cluster_name = name,
                cluster_type = cluster_type,
                cluster_user_ssh_public_key = ssh_key
            ),
            # Cluster creation should include a patch
            # There is no point in creating clusters that have known vulnerabilities!
            extra_vars = dict(cluster_upgrade_system_packages = True)
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
            self._connection.inventories.get(cluster.id),
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
            self._connection.inventories.get(cluster.id),
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
        # The job that is executed has cluster_state = absent in the extra vars
        inventory = self._connection.inventories.get(cluster.id)
        self._update_and_run_inventory(
            cluster.cluster_type,
            inventory,
            credential,
            extra_vars = dict(cluster_state = 'absent')
        )
        return self.find_cluster(inventory.id)

    def close(self):
        self._connection.close()
