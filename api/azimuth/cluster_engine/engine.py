"""
This module defines the base class for cluster managers.
"""

import dataclasses
import datetime
import typing as t

import jinja2

from ..provider import base as cloud_base
from ..scheduling import dto as scheduling_dto
from ..zenith import Zenith

from . import dto, errors
from .drivers import base as drivers_base


ZENITH_REGISTRAR_URL_VAR = "zenith_registrar_url"
ZENITH_REGISTRAR_VERIFY_SSL_VAR = "zenith_registrar_verify_ssl"
ZENITH_SSHD_HOST_VAR = "zenith_sshd_host"
ZENITH_SSHD_PORT_VAR = "zenith_sshd_port"

ZENITH_SUBDOMAIN_VAR_PREFIX = "zenith_subdomain_"
ZENITH_LABEL_VAR_TPL = "zenith_label_{}"
ZENITH_ICON_URL_VAR_TPL = "zenith_icon_url_{}"
ZENITH_SUBDOMAIN_VAR_TPL = ZENITH_SUBDOMAIN_VAR_PREFIX + "{}"
ZENITH_FQDN_VAR_TPL = "zenith_fqdn_{}"
ZENITH_TOKEN_VAR_TPL = "zenith_token_{}"


def index_or_len(items, value):
    """
    Returns the index of the given value in items, or the length of the list if not present.
    """
    try:
        return items.index(value)
    except ValueError:
        return len(items)


class Engine:
    """
    Class for the cluster engine.
    """
    def __init__(self, driver: drivers_base.Driver, zenith: Zenith):
        self._driver = driver
        self._zenith = zenith

    def create_manager(self, cloud_session: cloud_base.ScopedSession) -> 'ClusterManager':
        """
        Creates a cluster manager for the given tenancy-scoped cloud session.
        """
        return ClusterManager(self._driver, self._zenith, cloud_session)


class ClusterManager:
    """
    Class for a tenancy-scoped cluster manager.
    """
    def __init__(
        self,
        driver: drivers_base.Driver,
        zenith: Zenith,
        cloud_session: cloud_base.ScopedSession
    ):
        self._driver = driver
        self._zenith = zenith
        self._cloud_session = cloud_session
        self._user_id = cloud_session.user_id()
        self._username = cloud_session.username()
        self._tenancy = cloud_session.tenancy()
        self._jinja_env = jinja2.Environment()

    def cluster_types(self) -> t.Iterable[dto.ClusterType]:
        """
        Lists the available cluster types.
        """
        ctx = dto.Context(self._username, self._user_id, self._tenancy)
        return self._driver.cluster_types(ctx)

    def find_cluster_type(self, name: str) -> dto.ClusterType:
        """
        Find a cluster type by name.
        """
        ctx = dto.Context(self._username, self._user_id, self._tenancy)
        return self._driver.find_cluster_type(name, ctx)

    def _cluster_modify(
        self,
        cluster: dto.Cluster,
        cluster_types: t.Optional[t.Dict[str, dto.ClusterType]] = None
    ) -> dto.Cluster:
        """
        Modifies a cluster returned from a driver before returning it.

        Used to add additional, driver-agnostic functionality.
        """
        # Process the parameters to remove Zenith variables and convert them to services
        params = dict(cluster.parameter_values)
        services = []
        # Throw away the Zenith connection information
        params.pop(ZENITH_REGISTRAR_URL_VAR, None)
        params.pop(ZENITH_REGISTRAR_VERIFY_SSL_VAR, None)
        params.pop(ZENITH_SSHD_HOST_VAR, None)
        params.pop(ZENITH_SSHD_PORT_VAR, None)
        zenith_service_names = [
            k.removeprefix(ZENITH_SUBDOMAIN_VAR_PREFIX)
            for k in params.keys()
            if k.startswith(ZENITH_SUBDOMAIN_VAR_PREFIX)
        ]
        for service_name in zenith_service_names:
            label_variable = ZENITH_LABEL_VAR_TPL.format(service_name)
            icon_url_variable = ZENITH_ICON_URL_VAR_TPL.format(service_name)
            subdomain_variable = ZENITH_SUBDOMAIN_VAR_TPL.format(service_name)
            fqdn_variable = ZENITH_FQDN_VAR_TPL.format(service_name)
            token_variable = ZENITH_TOKEN_VAR_TPL.format(service_name)
            # Throw away the token
            params.pop(token_variable, None)
            # Extract the other variables and use them to build a service
            services.append(
                dto.ClusterService(
                    service_name,
                    params.pop(label_variable, service_name),
                    params.pop(icon_url_variable, None),
                    params.pop(fqdn_variable),
                    params.pop(subdomain_variable)
                )
            )
        # Try to order the services according to the cluster type
        if cluster_types is not None:
            cluster_type = cluster_types.get(cluster.cluster_type)
        else:
            try:
                cluster_type = self.find_cluster_type(cluster.cluster_type)
            except errors.ObjectNotFoundError:
                cluster_type = None
        cluster_type_service_names = [
            s.name
            for s in getattr(cluster_type, "services", [])
        ]
        cluster = dataclasses.replace(
            cluster,
            parameter_values = params,
            services = sorted(
                services,
                key = lambda s: (index_or_len(cluster_type_service_names, s.name), s.label)
            )
        )
        return self._cloud_session.cluster_modify(cluster)

    def clusters(self) -> t.Iterable[dto.Cluster]:
        """
        List the clusters that are deployed.
        """
        ctx = dto.Context(self._username, self._user_id, self._tenancy)
        cluster_types = None
        for cluster in self._driver.clusters(ctx):
            # cluster_types is lazily initialised once we know there is a cluster
            if not cluster_types:
                cluster_types = {
                    ct.name: ct
                    for ct in self.cluster_types()
                }
            yield self._cluster_modify(cluster, cluster_types)

    def find_cluster(self, id: str) -> dto.Cluster:
        """
        Find a cluster by id.
        """
        ctx = dto.Context(self._username, self._user_id, self._tenancy)
        cluster = self._driver.find_cluster(id, ctx)
        return self._cluster_modify(cluster)

    def validate_cluster_params(
        self,
        cluster_type: t.Union[dto.ClusterType, str],
        params: t.Mapping[str, t.Any],
        prev_params: t.Mapping[str, t.Any] = {}
    ) -> t.Mapping[str, t.Any]:
        """
        Validates the given user parameter values against the given cluster type.

        If validation fails, a `ValidationError` is raised.
        """
        from . import validation
        if not isinstance(cluster_type, dto.ClusterType):
            cluster_type = self.find_cluster_type(cluster_type)
        validator = validation.build_validator(
            self._cloud_session,
            self,
            cluster_type.parameters,
            prev_params
        )
        return validator(params)

    def _with_zenith_params(
        self,
        params: t.Mapping[str, t.Any],
        cluster_type: dto.ClusterType,
        cluster: t.Optional[dto.Cluster] = None
    ):
        """
        Returns a new set of parameters that have the required Zenith parameters
        added or removed depending on the enabled services.
        """
        zenith_params = params.copy()
        # next_params represents the next state of the cluster before any
        # modifications for Zenith services that need to be enabled or disabled
        next_params = getattr(cluster, "parameter_values", {}).copy()
        next_params.update(params)
        # Add the connection information for Zenith services
        zenith_params.update({
            ZENITH_REGISTRAR_URL_VAR: self._zenith.registrar_external_url,
            ZENITH_REGISTRAR_VERIFY_SSL_VAR: self._zenith.verify_ssl_clients,
            ZENITH_SSHD_HOST_VAR: self._zenith.sshd_host,
            ZENITH_SSHD_PORT_VAR: self._zenith.sshd_port,
        })
        # Determine the existing services
        existing_services = { s.name for s in getattr(cluster, "services", []) }
        # Update the parameters based on the services for the cluster type
        for service in cluster_type.services:
            # Check if the service is enabled
            if service.when:
                expr = self._jinja_env.compile_expression(service.when)
                service_enabled = expr(**next_params)
            else:
                service_enabled = True
            label_variable = ZENITH_LABEL_VAR_TPL.format(service.name)
            icon_url_variable = ZENITH_ICON_URL_VAR_TPL.format(service.name)
            subdomain_variable = ZENITH_SUBDOMAIN_VAR_TPL.format(service.name)
            fqdn_variable = ZENITH_FQDN_VAR_TPL.format(service.name)
            token_variable = ZENITH_TOKEN_VAR_TPL.format(service.name)
            # If the service is enabled but already exists, there is nothing to do
            # If the service is enabled but doesn't exist, we need to reserve a subdomain
            # and inject the parameters for it
            # If the service is not enabled, make sure the variables are removed
            if service_enabled:
                if service.name not in existing_services:
                    reservation = self._zenith.reserve_subdomain()
                    zenith_params.update({
                        subdomain_variable: reservation.subdomain,
                        fqdn_variable: reservation.fqdn,
                        token_variable: reservation.token,
                    })
                # Always make sure the label and icon URL are up to date
                zenith_params.update({
                    label_variable: service.label,
                    icon_url_variable: service.icon_url,
                })
            else:
                # When the service is disabled, remove all the Zenith variables for the service
                # To do this, they should be set to None
                zenith_params.update({
                    label_variable: None,
                    icon_url_variable: None,
                    subdomain_variable: None,
                    fqdn_variable: None,
                    token_variable: None,
                })
        return zenith_params

    def create_cluster(
        self,
        name: str,
        cluster_type: dto.ClusterType,
        params: t.Mapping[str, t.Any],
        ssh_key: t.Optional[str],
        schedule: t.Optional[scheduling_dto.PlatformSchedule]
    ) -> dto.Cluster:
        """
        Creates a new cluster with the given name, type and parameters.
        """
        if cluster_type.requires_ssh_key and not ssh_key:
            raise errors.InvalidOperationError(
                f"Clusters of type '{cluster_type.label}' require an SSH key."
            )
        validated = getattr(params, "__validated__", False)
        # If the parameters have not already been validated, validated them
        if not validated:
            params = self.validate_cluster_params(cluster_type, params)
        params = dict(params, **self._cloud_session.cluster_parameters())
        if ssh_key:
            params["cluster_user_ssh_public_key"] = ssh_key
        if self._zenith:
            params = self._with_zenith_params(params, cluster_type)
        ctx = dto.Context(
            self._username,
            self._user_id,
            self._tenancy,
            self._cloud_session.cloud_credential(
                f"az-caas-{name}",
                f"Used by Azimuth to manage CaaS cluster '{name}'."
            )
        )
        cluster = self._driver.create_cluster(
            name,
            cluster_type,
            params,
            schedule,
            ctx
        )
        return self._cluster_modify(cluster)

    def update_cluster(
        self,
        cluster: t.Union[dto.Cluster, str],
        params: t.Mapping[str, t.Any]
    ) -> dto.Cluster:
        """
        Updates an existing cluster with the given parameters.
        """
        if not isinstance(cluster, dto.Cluster):
            cluster = self.find_cluster(cluster)
        if cluster.status in {dto.ClusterStatus.CONFIGURING, dto.ClusterStatus.DELETING}:
            raise errors.InvalidOperationError(
                'Cannot update cluster with status {}'.format(cluster.status.name)
            )
        validated = getattr(params, "__validated__", False)
        # Load the cluster type once if required
        if not validated or self._zenith:
            cluster_type = self.find_cluster_type(cluster.cluster_type)
        else:
            cluster_type = None
        # If the parameters have not already been validated, validated them
        if not validated:
            params = self.validate_cluster_params(
                cluster_type,
                params,
                cluster.parameter_values
            )
        params = dict(params, **self._cloud_session.cluster_parameters())
        if self._zenith:
            params = self._with_zenith_params(params, cluster_type, cluster)
        ctx = dto.Context(self._username, self._user_id, self._tenancy)
        cluster = self._driver.update_cluster(cluster, params, ctx)
        return self._cluster_modify(cluster)

    def patch_cluster(
        self,
        cluster: t.Union[dto.Cluster, str]
    ) -> dto.Cluster:
        """
        Patches the given existing cluster.
        """
        if not isinstance(cluster, dto.Cluster):
            cluster = self.find_cluster(cluster)
        if cluster.status in {dto.ClusterStatus.CONFIGURING, dto.ClusterStatus.DELETING}:
            raise errors.InvalidOperationError(
                'Cannot patch cluster with status {}'.format(cluster.status.name)
            )
        ctx = dto.Context(self._username, self._user_id, self._tenancy)
        cluster = self._driver.patch_cluster(
            cluster,
            self._cloud_session.cluster_parameters(),
            ctx
        )
        return self._cluster_modify(cluster)

    def delete_cluster(
        self,
        cluster: t.Union[dto.Cluster, str]
    ) -> t.Optional[dto.Cluster]:
        """
        Deletes an existing cluster.
        """
        if not isinstance(cluster, dto.Cluster):
            cluster = self.find_cluster(cluster)
        if cluster.status in {dto.ClusterStatus.CONFIGURING, dto.ClusterStatus.DELETING}:
            raise errors.InvalidOperationError(
                'Cannot delete cluster with status {}'.format(cluster.status.name)
            )
        ctx = dto.Context(self._username, self._user_id, self._tenancy)
        cluster = self._driver.delete_cluster(cluster, ctx)
        if cluster:
            return self._cluster_modify(cluster)
        else:
            return None

    def close(self):
        """
        Release any resources held by this cluster manager.
        """
        # By default, this is a NOOP

    def __enter__(self):
        """
        Called when entering a context manager block.
        """
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """
        Called when exiting a context manager block. Ensures that close is called.
        """
        self.close()

    def __del__(self):
        """
        Ensures that close is called when the session is garbage collected.
        """
        self.close()
