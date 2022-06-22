"""
This module contains the cluster engine implementation for AWX.
"""

import functools
import logging
import json
import re
import time
import typing as t
import uuid

import dateutil.parser

import rackit

from ... import dto, errors
from .. import base
from . import api


logger = logging.getLogger(__name__)


#: Maps credential types to AWX credential type names
#: Currently, only OpenStack tokens are supported
CREDENTIAL_TYPE_NAMES = dict(openstack_token = "OpenStack Token")


def convert_exceptions(f):
    """
    Decorator that converts AWX API exceptions into errors from :py:mod:`..errors`.
    """
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except rackit.ApiError as exc:
            # Extract the status code and message
            status_code = exc.status_code
            message = str(exc)
            if status_code == 400:
                raise errors.BadInputError(message)
            elif status_code == 401:
                raise errors.AuthenticationError(message)
            elif status_code == 403:
                raise errors.PermissionDeniedError(message)
            elif status_code == 404:
                raise errors.ObjectNotFoundError(message)
            elif status_code == 409:
                raise errors.InvalidOperationError(message)
            else:
                logger.exception("Unknown error with AWX API.")
                raise errors.CommunicationError("Unknown error with AWX API.")
        except rackit.RackitError as exc:
            logger.exception("Could not connect to AWX API.")
            raise errors.CommunicationError("Could not connect to AWX API.")
    return wrapper


class cached_property:
    """
    Similar to the `@property` decorator except that the result of invoking the wrapped
    method is cached and reused.
    """
    def __init__(self, func):
        self.func = func

    def __set_name__(self, owner, name):
        self.name = name

    def __get__(self, instance, owner):
        result = instance.__dict__[self.name] = self.func(instance)
        return result


class Driver(base.Driver):
    """
    Cluster engine driver implementation for AWX.

    Cluster types correspond to available job templates, and clusters correspond
    to inventories. A cluster is configured by launching a job using the job
    template for the cluster type and the cluster inventory.
    """
    def __init__(
        self,
        url: str,
        username: str,
        password: str,
        create_teams: bool = False,
        create_team_allow_all_permission: bool = False,
        verify_ssl: bool = True,
        template_inventory: str = "openstack"
    ):
        self._connection = api.Connection(url.rstrip("/"), username, password, verify_ssl)
        self._create_teams = create_teams
        self._create_team_allow_all_permission = create_team_allow_all_permission
        self._template_inventory = template_inventory

    def _log(
        self,
        message: str,
        *args,
        level: int = logging.INFO,
        ctx: t.Optional[dto.Context] = None,
        **kwargs
    ):
        logger.log(
            level,
            f"[{ctx.username}] [{ctx.tenancy.name}] {message}" if ctx else message,
            *args,
            **kwargs
        )

    @cached_property
    def _organisation(self):
        """
        The AWX organisation in which resources should be created.
        """
        try:
            organisation = next(self._connection.organisations.all())
        except StopIteration:
            raise errors.ImproperlyConfiguredError("Could not find organisation.")
        else:
            self._log("Using AWX organisation '%s'", organisation.name)
        return organisation

    def _get_team(self, ctx: dto.Context):
        """
        Returns the AWX team associated with the given context, or None if the team
        has not been created yet.
        """
        team = None
        try:
            team = next(self._connection.teams.all(name__iexact = ctx.tenancy.name))
        except StopIteration:
            # If we are creating teams on-demand, just return None
            # If we are not, then not finding a team for the context is a permissions error
            if self._create_teams:
                self._log("No AWX team found - it will be created when required", ctx = ctx)
            else:
                self._log("Could not find AWX team", level = logging.WARN, ctx = ctx)
                raise errors.PermissionDeniedError("Clusters are not enabled for this tenancy")
        else:
            self._log("Found AWX team", ctx = ctx)
        return team

    def _get_or_create_team(self, ctx: dto.Context):
        """
        Return a team for the given context, creating it if enabled.
        """
        # This will raise an exception if there is no team and we are not creating teams
        team = self._get_team(ctx)
        if not team:
            self._log("Creating team", ctx = ctx)
            team = self._connection.teams.create(
                name = ctx.tenancy.name,
                organization = self._organisation.id
            )
            # Create the allow all permission if required
            # This is represented in AWX as holding the execute role for the entire organisation
            if self._create_team_allow_all_permission:
                self._log("Granting allow-all permission to team", ctx = ctx)
                execute_role = next(
                    role
                    for role in self._connection.roles.all()
                    if (
                        role.name.lower() == "execute" and
                        role.summary_fields.get("resource_type") == "organization" and
                        role.summary_fields.get("resource_id") == self._organisation.id
                    )
                )
                team.associate_role(execute_role)
        return team

    def _get_permitted_job_templates(self, ctx: dto.Context):
        """
        Returns a tuple of (allow_all, set of job template ids) indicating the job
        templates that the given context is permitted to use.
        """
        team = self._get_team(ctx)
        if not team:
            self._log("Using allow-all permission directly", ctx = ctx)
            return (self._create_team_allow_all_permission, set())
        # If we have a real team, start by fetching the roles
        self._log("Fetching roles for team", ctx = ctx)
        roles = list(team.roles.all())
        # If the team has the execute permission for the organisation, it is permitted to
        # access all the templates
        allow_all = any(
            (
                role.name.lower() == "execute" and
                role.summary_fields["resource_type"] == "organization" and
                role.summary_fields["resource_id"] == self._organisation.id
            )
            for role in roles
        )
        if allow_all:
            self._log("Team has execute permission for organisation", ctx = ctx)
            return (True, set())
        # Otherwise, the team may have been granted the execute permission on specific templates
        permitted = {
            role.summary_fields["resource_id"]
            for role in roles
            if (
                role.name.lower() == "execute" and
                role.summary_fields["resource_type"] == "job_template"
            )
        }
        self._log("Found %s permitted job templates", len(permitted), ctx = ctx)
        return (False, permitted)

    def _from_job_template(self, job_template: api.JobTemplate, ctx: dto.Context):
        """
        Returns a cluster template from the given job template.
        """
        if not job_template.description:
            raise errors.ImproperlyConfiguredError(
                "No metadata specified for cluster type '{}'".format(job_template.name)
            )
        self._log("Loading metadata from %s", job_template.description, ctx = ctx)
        return dto.ClusterType.from_yaml(job_template.name, job_template.description)

    @convert_exceptions
    def cluster_types(self, ctx: dto.Context) -> t.Iterable[dto.ClusterType]:
        """
        See :py:meth:`.base.Driver.cluster_types`.
        """
        # Get the names of the job templates that the team has been granted execute access to
        allow_all, permitted = self._get_permitted_job_templates(ctx)
        # Only fetch the job templates if there are some permissions to check
        if allow_all or permitted:
            self._log("Fetching job templates", ctx = ctx)
            # Filter the allowed cluster types
            job_templates = tuple(
                self._from_job_template(jt, ctx)
                for jt in self._connection.job_templates.all()
                if allow_all or jt.id in permitted
            )
            self._log("Found %s permitted job templates", len(job_templates), ctx = ctx)
            return job_templates
        else:
            return ()

    @convert_exceptions
    def find_cluster_type(self, name: str, ctx: dto.Context) -> dto.ClusterType:
        """
        See :py:meth:`.base.Driver.find_cluster_type`.
        """
        self._log("Fetching job template '%s'", name, ctx = ctx)
        job_template = self._connection.job_templates.find_by_name(name)
        if not job_template:
            raise errors.ObjectNotFoundError("Could not find cluster type '{}'".format(name))
        # Check if the context has permission to access the cluster template
        allow_all, permitted = self._get_permitted_job_templates(ctx)
        if allow_all or job_template.id in permitted:
            return self._from_job_template(job_template, ctx)
        else:
            raise errors.ObjectNotFoundError("Could not find cluster type '{}'".format(name))

    def _get_permitted_inventories(self, team: api.Team, ctx: dto.Context):
        """
        Returns the ids of the inventories that the given team has access to.
        """
        self._log("Fetching roles for team", ctx = ctx)
        roles = list(team.roles.all())
        # The team will have the admin permission on their own inventories
        permitted = {
            role.summary_fields["resource_id"]
            for role in roles
            if (
                role.name.lower() == "admin" and
                role.summary_fields["resource_type"] == "inventory"
            )
        }
        self._log("Found %s permitted inventories", len(permitted), ctx = ctx)
        return permitted

    def _from_inventory(self, inventory: api.Inventory, ctx: dto.Context):
        """
        Returns a cluster from the given inventory.
        """
        # Get the jobs for the inventory
        self._log("Fetching jobs for inventory '%s'", inventory.name, ctx = ctx)
        jobs = self._connection.jobs.all(inventory = inventory.id, order_by = "-started")
        # The status of the cluster is based on the status of the latest job
        latest = None
        task = None
        error_message = None
        try:
            latest = next(jobs)
        except StopIteration:
            # There should be at least one job...
            status = dto.ClusterStatus.ERROR
        else:
            # The cluster_state comes from the extra vars of the most recent job
            latest_extra_vars = json.loads(latest.extra_vars)
            cluster_state = latest_extra_vars.get("cluster_state", "present")
            if latest.status == "successful":
                if cluster_state == "present":
                    status = dto.ClusterStatus.READY
                else:
                    self._log(
                        "Inventory '%s' represents deleted cluster - ignoring",
                        inventory.name,
                        ctx = ctx
                    )
                    raise errors.ObjectNotFoundError(
                        "Could not find cluster with ID {}".format(inventory.id)
                    )
            elif latest.status == "canceled":
                status = dto.ClusterStatus.ERROR
                error_message = "Cluster configuration cancelled by an administrator."
            elif latest.status in {"failed", "error"}:
                status = dto.ClusterStatus.ERROR
                # Try to retrieve an error from the failed task
                event = next(
                    latest.job_events.all(event = "runner_on_failed", order_by = "-created"),
                    None
                )
                host = getattr(event, "event_data", {}).get("host")
                result = getattr(event, "event_data", {}).get("res", {})
                no_log = result.pop("_ansible_no_log", False)
                if no_log or not result:
                    msg = "Error during cluster configuration. Please contact support."
                else:
                    msg = json.dumps(result, indent = 4)
                if host:
                    error_message = "[{}] => {}".format(host, msg)
                else:
                    error_message = msg
            else:
                if cluster_state == "present":
                    status = dto.ClusterStatus.CONFIGURING
                else:
                    status = dto.ClusterStatus.DELETING
                # Find the name of the currently executing task
                # Use a combination of the task and the role that it comes from (if present)
                # However we remove any galaxy namespaces from the role if present
                task = next(
                    (
                        "{} : {}".format(event.role.split(".")[-1], event.task)
                            if event.role
                            else event.task
                        for event in latest.job_events.all(
                            event = "playbook_on_task_start",
                            order_by = "-created"
                        )
                    ),
                    # If there is no task, indicate that we are waiting to be scheduled
                    "Waiting to be scheduled"
                )
        # The outputs and updated time come from the last successful job
        # The patched time comes from the last successful job with cluster_upgrade_system_packages = True
        job = latest
        outputs = {}
        updated = None
        patched = None
        # If we haven't found the update or patch time, traverse the rest of the jobs until we find them
        while job:
            if job.status == "successful":
                # Outputs and updated are set together, based on the same job
                if not updated:
                    updated = updated or job.finished
                    # If the last task is a debug action for the "outputs" variable, then that
                    # value is used as the outputs
                    event = next(
                        job.job_events.all(event = "runner_on_ok", order_by = "-created"),
                        None
                    )
                    event_data = getattr(event, "event_data", {})
                    if event_data.get("task_action") == "debug":
                        outputs = event_data.get("res", {}).get("outputs", {})
                if json.loads(job.extra_vars).get("cluster_upgrade_system_packages", False):
                    patched = patched or job.finished
            if updated and patched:
                break
            else:
                job = next(jobs, None)
        # Get the inventory variables
        params = inventory.variable_data._as_dict()
        # Extract the parameters that aren't really parameters
        name = params.pop("cluster_name")
        cluster_type = params.pop("cluster_type")
        params.pop("cluster_user_ssh_public_key")
        return dto.Cluster(
            inventory.id,
            name,
            cluster_type,
            status,
            task,
            error_message,
            params,
            (),
            outputs,
            dateutil.parser.parse(inventory.created),
            dateutil.parser.parse(updated) if updated else None,
            dateutil.parser.parse(patched) if patched else None
        )

    @convert_exceptions
    def clusters(self, ctx: dto.Context) -> t.Iterable[dto.Cluster]:
        """
        See :py:meth:`.base.Driver.clusters`.
        """
        team = self._get_team(ctx)
        if not team:
            return ()
        permitted = self._get_permitted_inventories(team, ctx)
        self._log("Fetching inventories", ctx = ctx)
        inventories = self._connection.inventories.all()
        def active_inventories(inventories):
            for inventory in inventories:
                if inventory.id in permitted:
                    try:
                        yield self._from_inventory(inventory, ctx)
                    except errors.ObjectNotFoundError:
                        pass
        inventories = tuple(active_inventories(inventories))
        self._log("Found %s inventories", len(inventories), ctx = ctx)
        return inventories

    @convert_exceptions
    def find_cluster(self, id: str, ctx: dto.Context) -> dto.Cluster:
        """
        See :py:meth:`.base.Driver.find_cluster`.
        """
        # The ID should be an integer, or it cannot be a valid id in AWX
        try:
            id = int(id)
        except ValueError:
            raise errors.ObjectNotFoundError(
                "Could not find cluster with ID {}".format(id)
            )
        team = self._get_team(ctx)
        if not team:
            raise errors.ObjectNotFoundError(
                "Could not find cluster with ID {}".format(id)
            )
        if id not in self._get_permitted_inventories(team, ctx):
            raise errors.ObjectNotFoundError(
                "Could not find cluster with ID {}".format(id)
            )
        self._log("Fetching inventory with id '%s'", id, ctx = ctx)
        try:
            inventory = self._connection.inventories.get(id)
        except rackit.NotFound:
            raise errors.ObjectNotFoundError(
                "Could not find cluster with ID {}".format(id)
            )
        else:
            return self._from_inventory(inventory, ctx)

    def _create_credential(self, ctx: dto.Context):
        """
        Utility method to return a credential to use.
        """
        # First, try to find the AWX credential type
        try:
            credential_type_name = CREDENTIAL_TYPE_NAMES[ctx.credential.type]
        except KeyError:
            self._log(
                "Unknown credential type '%s'",
                ctx.credential.type,
                level = logging.WARNING,
                ctx = ctx
            )
            credential_type = None
        else:
            self._log(
                "Finding credential type '%s'",
                credential_type_name,
                ctx = ctx
            )
            credential_type = self._connection.credential_types.find_by_name(credential_type_name)
        if not credential_type:
            message = "Unknown credential type '{}'.".format(ctx.credential.type)
            raise errors.InvalidOperationError(message)
        # Now we have found the credential type, create and return the credential
        credential_name = re.sub(
            "[^a-zA-Z0-9]+",
            "-",
            # Combine the username and team name with some randomness to avoid collisions
            "{}-{}-{}".format(ctx.username, ctx.tenancy.name, uuid.uuid4().hex[:16])
        )
        self._log("Creating credential '%s'", credential_name, ctx = ctx)
        return self._connection.credentials.create(
            name = credential_name,
            credential_type = credential_type.id,
            organization = self._organisation.id,
            inputs = ctx.credential.data
        )

    def _run_inventory(
        self,
        cluster_type: str,
        inventory: api.Inventory,
        awx_credential: api.Credential,
        extra_vars: t.Dict[str, t.Any],
        ctx: dto.Context
    ):
        """
        Utility method to update inventory variables and run a job with the given credential.
        """
        self._log("Finding job template '%s'", cluster_type, ctx = ctx)
        job_template = self._connection.job_templates.find_by_name(cluster_type)
        if not job_template:
            raise errors.ObjectNotFoundError(
                "Could not find cluster type '{}'".format(cluster_type)
            )
        self._log("Executing job for inventory '%s'", inventory.name, ctx = ctx)
        # Append the cloud credential to the existing creds for the template
        credentials = [c["id"] for c in job_template.summary_fields["credentials"]]
        credentials.append(awx_credential.id)
        # Once everything is updated, launch a job
        job_template.launch(
            inventory = inventory.id,
            credentials = credentials,
            extra_vars = json.dumps(extra_vars)
        )
        # Evict the inventory from the cache as it has changed
        self._connection.inventories.cache.evict(inventory)

    @convert_exceptions
    def create_cluster(
        self,
        name: str,
        cluster_type: dto.ClusterType,
        params: t.Mapping[str, t.Any],
        ssh_key: t.Optional[str],
        ctx: dto.Context
    ):
        """
        See :py:meth:`.base.Driver.create_cluster`.
        """
        team = self._get_or_create_team(ctx)
        template_inventory = self._connection.inventories.find_by_name(self._template_inventory)
        if not template_inventory:
            raise errors.ImproperlyConfiguredError("Could not find template inventory.")
        awx_credential = self._create_credential(ctx)
        # The inventory name is prefixed with the tenancy name
        inventory_name = "{}-{}".format(ctx.tenancy.name, name)
        self._log("Try to find existing inventory '%s'", inventory_name, ctx = ctx)
        # Try to find an existing inventory with the name we want to use
        inventory = self._connection.inventories.find_by_name(inventory_name)
        if inventory:
            self._log("Existing inventory called '%s' found", inventory_name, ctx = ctx)
            # If an inventory exists, check if it represents a valid cluster
            try:
                _ = self._from_inventory(inventory, ctx)
            except errors.ObjectNotFoundError:
                self._log(
                    "Inventory '%s' represents deleted cluster - removing",
                    inventory_name,
                    ctx = ctx
                )
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
                        time.sleep(1)
                else:
                    raise errors.OperationTimedOutError("Timed out while removing inventory.")
            else:
                # If the cluster already exists, we have a conflict
                raise errors.BadInputError("A cluster called '{}' aleady exists.".format(name))
        # Start to build the new inventory for the new cluster
        self._log("Copying template inventory as '%s'", inventory_name, ctx = ctx)
        inventory = template_inventory.copy(inventory_name)
        # Once the inventory exists, add the team as an admin
        self._log("Granting admin role for inventory '%s'", inventory.name, ctx = ctx)
        admin_role = next(
            role
            for role in self._connection.roles.all()
            if (
                role.name.lower() == "admin" and
                role.summary_fields.get("resource_type") == "inventory" and
                role.summary_fields.get("resource_id") == inventory.id
            )
        )
        team.associate_role(admin_role)
        # Update the inventory variables
        self._log("Setting inventory variables for '%s'", inventory.name, ctx = ctx)
        inventory.variable_data._update(
            dict(
                # Parameters with a value of None should be omitted
                { k: v for k, v in params.items() if v is not None },
                cluster_id = inventory.id,
                cluster_name = name,
                cluster_type = cluster_type.name,
                cluster_user_ssh_public_key = ssh_key
            )
        )
        # Execute the creation job
        self._run_inventory(
            cluster_type.name,
            inventory,
            awx_credential,
            # Cluster creation should include a patch
            # There is no point in creating clusters that have known vulnerabilities!
            dict(cluster_upgrade_system_packages = True),
            ctx
        )
        return self.find_cluster(inventory.id, ctx)

    @convert_exceptions
    def update_cluster(
        self,
        cluster: dto.Cluster,
        params: t.Mapping[str, t.Any],
        ctx: dto.Context
    ) -> dto.Cluster:
        """
        See :py:meth:`.base.Driver.update_cluster`.
        """
        awx_credential = self._create_credential(ctx)
        self._log("Updating cluster '%s'", cluster.id, ctx = ctx)
        inventory = self._connection.inventories.get(cluster.id)
        inventory_variables = inventory.variable_data._as_dict()
        for key, value in params.items():
            if value is not None:
                inventory_variables[key] = value
            else:
                inventory_variables.pop(key, None)
        inventory.variable_data._update(inventory_variables)
        self._run_inventory(cluster.cluster_type, inventory, awx_credential, {}, ctx)
        return self.find_cluster(cluster.id, ctx)

    @convert_exceptions
    def patch_cluster(self, cluster: dto.Cluster, ctx: dto.Context) -> dto.Cluster:
        """
        See :py:meth:`.base.Driver.patch_cluster`.
        """
        awx_credential = self._create_credential(ctx)
        self._log("Patching cluster '%s'", cluster.id, ctx = ctx)
        self._run_inventory(
            cluster.cluster_type,
            self._connection.inventories.get(cluster.id),
            awx_credential,
            dict(cluster_upgrade_system_packages = True),
            ctx
        )
        return self.find_cluster(cluster.id, ctx)

    @convert_exceptions
    def delete_cluster(self, cluster: dto.Cluster, ctx: dto.Context) -> t.Optional[dto.Cluster]:
        """
        See :py:meth:`.base.Driver.delete_cluster`.
        """
        awx_credential = self._create_credential(ctx)
        self._log("Deleting cluster '%s'", cluster.id, ctx = ctx)
        inventory = self._connection.inventories.get(cluster.id)
        self._run_inventory(
            cluster.cluster_type,
            inventory,
            awx_credential,
            dict(cluster_state = "absent"),
            ctx
        )
        return self.find_cluster(inventory.id, ctx)

    @convert_exceptions
    def close(self):
        self._connection.close()
