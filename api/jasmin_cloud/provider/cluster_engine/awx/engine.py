"""
This module contains the cluster engine implementation for AWX.
"""

import dataclasses
import logging
import json
import re
import uuid

import dateutil.parser

import rackit

from . import api
from .. import base
from ... import dto, errors


logger = logging.getLogger(__name__)


#: Maps credential types to AWX credential type names
#: Currently, only OpenStack tokens are supported
CREDENTIAL_TYPE_NAMES = dict(openstack_token = 'OpenStack Token')


@dataclasses.dataclass
class FakeTeam:
    """
    Returned in place of a real team in the case where teams should be auto-created.
    This is used to defer the creation of a team until a write is required.
    """
    #: The name of the team
    name: str
    #: Indicates whether the team should be granted access to all job templates
    #: This is used when listing cluster types using a fake team and when reifying the team
    #: Corresponds to create_team_allow_all_permission = True
    allow_all: bool


class Engine(base.Engine):
    """
    Cluster engine implementation for AWX.

    Args:
        url: The AWX API url.
        username: The username of the service account to use.
        password: The password of the service account.
        create_teams: Whether to create teams which do not exist.
        verify_ssl: Whether to verify SSL connections to AWX.
        template_inventory: The name of the template inventory.
    """
    def __init__(self, url,
                       username,
                       password,
                       create_teams = False,
                       create_team_allow_all_permission = False,
                       verify_ssl = True,
                       template_inventory = 'openstack'):
        self._url = url.rstrip('/')
        self._username = username
        self._password = password
        self._verify_ssl = verify_ssl
        self._template_inventory = template_inventory
        self._create_teams = create_teams
        self._create_team_allow_all_permission = create_team_allow_all_permission

    def create_manager(self, username, tenancy):
        """
        See :py:meth:`.base.Engine.create_manager`.
        """
        logger.info("[%s] Starting AWX connection", username)
        connection = api.Connection(
            self._url,
            self._username,
            self._password,
            self._verify_ssl
        )
        organisation = next(connection.organisations.all(), None)
        if not organisation:
            raise errors.ImproperlyConfiguredError('Could not find organisation.')
        # Try to find the team named after the tenancy
        team = next(connection.teams.all(name__iexact = tenancy.name), None)
        if team:
            logger.info("[%s] Found AWX team '%s'", username, team.name)
        elif self._create_teams:
            # If no team was found but we want to create teams on demand, use a fake team
            # until a write is required
            logger.info("[%s] Using fake team for '%s'", username, tenancy.name)
            team = FakeTeam(tenancy.name, self._create_team_allow_all_permission)
        if team:
            return ClusterManager(
                username,
                connection,
                organisation,
                self._template_inventory,
                team
            )
        else:
            logger.warn("[%s] Could not find AWX team '%s'", username, tenancy.name)
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
                       template_inventory,
                       team):
        self._username = username
        self._connection = connection
        self._organisation = organisation
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

    def _ensure_team(self):
        """
        Ensures that the team associated with this manager is a actual team. If the
        team is a fake team it will be created at this point.

        Because this creates resources in AWX, it should only be executed before a
        write request.
        """
        # If the team is not a fake team, then it is a real team and we are done
        if not isinstance(self._team, FakeTeam):
            return
        fake_team = self._team
        # Create the team
        self._log("Reifying fake team")
        self._team = self._connection.teams.create(
            name = fake_team.name,
            organization = self._organisation.id
        )
        # Create the allow all permission if required
        # This is represented in AWX as holding the execute role for the entire organisation
        if fake_team.allow_all:
            self._log("Granting allow-all permission to team")
            execute_role = next(
                role
                for role in self._connection.roles.all()
                if (
                    role.name.lower() == 'execute' and
                    role.summary_fields.get('resource_type') == 'organization' and
                    role.summary_fields.get('resource_id') == self._organisation.id
                )
            )
            # Associate the role with the newly created team
            self._connection.api_post(
                f"/teams/{self._team.id}/roles/",
                json = dict(id = execute_role.id)
            )

    def _fetch_team_permissions(self):
        """
        Returns a tuple of (allow_all, job_template_names) indicating the permissions
        granted to the team associated with this manager to access job templates.

        It can accept a fake team or a real team.
        If given a real team, the roles for the team are queried.
        If given a fake team, job_template_names will always be empty and allow_all will
        depend on the value of create_team_allow_all_permission given to the engine.
        """
        # If we have a fake team, just return the value of allow_all
        if isinstance(self._team, FakeTeam):
            self._log("Using permissions from fake team")
            return (self._team.allow_all, {})
        # If we have a real team, start by fetching the roles
        self._log("Fetching roles for team")
        roles = list(self._team.roles.all())
        # If the team has the execute permission on the organisation, then they are
        # permitted to access all the templates
        allow_all = any(
            (
                role.name.lower() == 'execute' and
                role.summary_fields['resource_type'] == 'organization' and
                role.summary_fields['resource_id'] == self._organisation.id
            )
            for role in roles
        )
        if allow_all:
            self._log("Team has execute permission for organisation")
            return (True, {})
        # Otherwise, the team may have been granted the execute permission on
        # individual job templates
        permitted = {
            role.summary_fields['resource_id']
            for role in roles
            if (
                role.name.lower() == 'execute' and
                role.summary_fields['resource_type'] == 'job_template'
            )
        }
        self._log("Found %s permitted job templates", len(permitted))
        return (False, permitted)

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
        # Get the names of the job templates that the team has been granted execute access to
        allow_all, permitted = self._fetch_team_permissions()
        # Only fetch the job templates if there are some permissions to check
        if allow_all or permitted:
            # Fetch the job templates, filter the allowed ones and return the cluster types
            return tuple(
                self._from_job_template(jt)
                for jt in self._connection.job_templates.all()
                if allow_all or jt.id in permitted
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
            status = dto.ClusterStatus.ERROR
        else:
            # The cluster_state comes from the extra vars of the most recent job
            latest_extra_vars = json.loads(latest.extra_vars)
            cluster_state = latest_extra_vars.get('cluster_state', 'present')
            if latest.status == 'successful':
                if cluster_state == 'present':
                    status = dto.ClusterStatus.READY
                    updated = latest.finished
                    if latest_extra_vars.get('cluster_upgrade_system_packages', False):
                        patched = latest.finished
                else:
                    self._log("Inventory '%s' represents deleted cluster - ignoring", inventory.name)
                    raise errors.ObjectNotFoundError("Could not find cluster with ID {}".format(id))
            elif latest.status == 'canceled':
                status = dto.ClusterStatus.ERROR
                error_message = 'Cluster configuration cancelled by an administrator.'
            elif latest.status in {'failed', 'error'}:
                status = dto.ClusterStatus.ERROR
                # Try to retrieve an error from the failed task
                event = next(
                    latest.job_events.all(event = 'runner_on_failed', order_by = '-created'),
                    None
                )
                msg = getattr(event, 'event_data', {}).get('res', {}).get('msg')
                error_message = msg or 'Error during cluster configuration. Please contact support.'
            else:
                if cluster_state == 'present':
                    status = dto.ClusterStatus.CONFIGURING
                else:
                    status = dto.ClusterStatus.DELETING
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
        # Get the inventory variables
        params = inventory.variable_data._as_dict()
        # Extract the parameters that aren't really parameters
        name = params.pop('cluster_name')
        cluster_type = params.pop('cluster_type')
        params.pop('cluster_user_ssh_public_key')
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

    def _create_credential(self, credential):
        """
        Utility method to return a credential to use.
        """
        # First, try to find the AWX credential type
        try:
            credential_type_name = CREDENTIAL_TYPE_NAMES[credential.type]
        except KeyError:
            self._log("Unknown credential type '%s'", credential.type, level = logging.WARNING)
            credential_type = None
        else:
            self._log("Finding credential type '%s'", credential_type_name)
            credential_type = self._connection.credential_types.find_by_name(credential_type_name)
        if not credential_type:
            message = "Unknown credential type '{}'.".format(credential.type)
            raise errors.InvalidOperationError(message)
        # Now we have found the credential type, create and return the credential
        credential_name = re.sub(
            '[^a-zA-Z0-9]+',
            '-',
            # Combine the username and team name with some randomness to avoid collisions
            "{}-{}-{}".format(
                self._username,
                self._team.name,
                uuid.uuid4().hex[:16]
            )
        )
        self._log("Creating credential '%s'", credential_name)
        return self._connection.credentials.create(
            name = credential_name,
            credential_type = credential_type.id,
            organization = self._organisation.id,
            inputs = credential.data
        )

    def _run_inventory(self, cluster_type, inventory, credential, extra_vars = {}):
        """
        Utility method to update inventory variables and run a job with the given credential.
        """
        self._log("Finding job template '%s'", cluster_type)
        job_template = self._connection.job_templates.find_by_name(cluster_type)
        if not job_template:
            raise errors.ObjectNotFoundError(
                "Could not find cluster type '%s'",
                cluster_type
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
        # Ensure that the team exists
        self._ensure_team()
        # Try to find the template inventory
        # There is no point proceeding if this fails
        template_inventory = self._connection.inventories.find_by_name(self._template_inventory)
        if not template_inventory:
            raise errors.ImproperlyConfiguredError('Could not find template inventory.')
        # Get the AWX credential to use from the given data
        # Do this before anything else as there is no point proceeding if the credential
        # is not recognised
        awx_credential = self._create_credential(credential)
        # The inventory name is prefixed with the tenancy name
        inventory_name = "{}-{}".format(self._team.name, name)
        self._log("Try to find existing inventory '%s'", inventory_name)
        # Try to find an existing inventory with the name we want to use
        inventory = self._connection.inventories.find_by_name(inventory_name)
        if inventory:
            self._log("Existing inventory called '%s' found", inventory_name)
            # If an inventory exists, check if it represents a valid cluster
            try:
                _ = self._from_inventory(inventory)
            except errors.ObjectNotFoundError:
                self._log("Inventory '%s' represents deleted cluster - removing", inventory_name)
                # If the cluster does not exist, delete the inventory
                inventory._delete()
                # Inventories don't always delete straight away, so try up to
                # five times to refetch it until we get a 404
                remaining = 5
                while remaining > 0:
                    try:
                        inventory = self._connection.inventories.get(inventory.id, force = True)
                    except rackit.NotFound:
                        break
                    else:
                        remaining = remaining - 1
                else:
                    raise errors.OperationTimedOutError('Timed out while removing inventory.')
            else:
                # If the cluster also exists, we have a conflict
                raise errors.BadInputError("A cluster called '{}' aleady exists.".format(name))
        # Start to build the new inventory for the new cluster
        self._log("Copying template inventory as '%s'", inventory_name)
        inventory = self._connection.inventories.copy(template_inventory.id, inventory_name)
        # Update the inventory variables
        self._log("Setting inventory variables for '%s'", inventory.name)
        inventory.variable_data._update(
            dict(
                params,
                cluster_id = inventory.id,
                cluster_name = name,
                cluster_type = cluster_type,
                cluster_user_ssh_public_key = ssh_key
            )
        )
        # Execute the creation job
        self._run_inventory(
            cluster_type,
            inventory,
            awx_credential,
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
        # Ensure that the team exists
        self._ensure_team()
        # Get the AWX credential to use from the given data
        # Do this before anything else as there is no point proceeding if the credential
        # is not recognised
        awx_credential = self._create_credential(credential)
        cluster = self.find_cluster(cluster)
        if cluster.status in {dto.ClusterStatus.CONFIGURING, dto.ClusterStatus.DELETING}:
            raise errors.InvalidOperationError(
                'Cannot update cluster with status {}'.format(cluster.status.name)
            )
        self._log("Updating cluster '%s'", cluster.id)
        # Update the inventory variables with the given parameters
        inventory = self._connection.inventories.get(cluster.id)
        inventory_variables = inventory.variable_data._as_dict()
        inventory_variables.update(params)
        inventory.variable_data._update(inventory_variables)
        # Run the inventory
        self._run_inventory(cluster.cluster_type, inventory, awx_credential)
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
        # Ensure that the team exists
        self._ensure_team()
        # Get the AWX credential to use from the given data
        # Do this before anything else as there is no point proceeding if the credential
        # is not recognised
        awx_credential = self._create_credential(credential)
        cluster = self.find_cluster(cluster)
        if cluster.status in {dto.ClusterStatus.CONFIGURING, dto.ClusterStatus.DELETING}:
            raise errors.InvalidOperationError(
                'Cannot patch cluster with status {}'.format(cluster.status.name)
            )
        self._log("Patching cluster '%s'", cluster.id)
        # Run a job against the inventory with the patch variable set
        self._run_inventory(
            cluster.cluster_type,
            self._connection.inventories.get(cluster.id),
            awx_credential,
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
        # Ensure that the team exists
        self._ensure_team()
        # Get the AWX credential to use from the given data
        # Do this before anything else as there is no point proceeding if the credential
        # is not recognised
        awx_credential = self._create_credential(credential)
        cluster = self.find_cluster(cluster)
        if cluster.status in {dto.ClusterStatus.CONFIGURING, dto.ClusterStatus.DELETING}:
            raise errors.InvalidOperationError(
                'Cannot delete cluster with status {}'.format(cluster.status.name)
            )
        self._log("Deleting cluster '%s'", cluster.id)
        # The job that is executed has cluster_state = absent in the extra vars
        inventory = self._connection.inventories.get(cluster.id)
        self._run_inventory(
            cluster.cluster_type,
            inventory,
            awx_credential,
            extra_vars = dict(cluster_state = 'absent')
        )
        return self.find_cluster(inventory.id)

    def close(self):
        self._connection.close()
