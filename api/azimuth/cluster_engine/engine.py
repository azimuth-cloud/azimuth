"""
This module defines the base class for cluster managers.
"""

import dataclasses
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

ZENITH_LABEL_VAR_TPL = "zenith_label_{}"
ZENITH_ICON_URL_VAR_TPL = "zenith_icon_url_{}"
ZENITH_SUBDOMAIN_VAR_TPL = "zenith_subdomain_{}"
ZENITH_FQDN_VAR_TPL = "zenith_fqdn_{}"
ZENITH_INTERNAL_FQDN_VAR_TPL = "zenith_internal_fqdn_{}"
ZENITH_TOKEN_VAR_TPL = "zenith_token_{}"


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

        Used to add additional, driver-agnostic functionality and remove any injected parameters.
        """
        # First, allow the cloud provider to modify the cluster if required
        cluster = self._cloud_session.cluster_modify(cluster)
        # Get the services as specified in the cluster type
        if cluster_types is not None:
            cluster_type = cluster_types.get(cluster.cluster_type)
        else:
            try:
                cluster_type = self.find_cluster_type(cluster.cluster_type)
            except errors.ObjectNotFoundError:
                cluster_type = None
        # Limit the parameters to only those specified in the cluster type
        ct_params = { p.name for p in cluster_type.parameters }
        params = { k: v for k, v in cluster.raw_parameter_values.items() if k in ct_params }
        # Populate the Zenith services for the cluster from the cluster type
        services = []
        if cluster_type:
            for service in cluster_type.services:
                if service.internal:
                    continue
                subdomain_variable = ZENITH_SUBDOMAIN_VAR_TPL.format(service.name)
                if subdomain_variable not in cluster.raw_parameter_values:
                    continue
                fqdn_variable = ZENITH_FQDN_VAR_TPL.format(service.name)
                services.append(
                    dto.ClusterService(
                        service.name,
                        service.label,
                        service.icon_url,
                        cluster.raw_parameter_values[fqdn_variable],
                        cluster.raw_parameter_values[subdomain_variable]
                    )
                )
        # Build and return the new cluster object
        return dataclasses.replace(
            cluster,
            parameter_values = params,
            services = services
        )

    def clusters(self) -> t.Iterable[dto.Cluster]:
        """
        List the clusters that are deployed.
        """
        ctx = dto.Context(self._username, self._user_id, self._tenancy)
        cluster_types = None
        for cluster in self._driver.clusters(ctx):
            # cluster_types is lazily initialised once we know there is a cluster
            if not cluster_types:
                cluster_types = { ct.name: ct for ct in self.cluster_types() }
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
        # Create a copy of the parameters that we can modify
        zenith_params = params.copy()
        # Get the current parameters for the cluster
        current_params = getattr(cluster, "raw_parameter_values", {})
        # Get the future state of the cluster parameters after the changes
        next_params = dict(current_params, **params)
        # Add the connection information for Zenith services
        zenith_params.update({
            ZENITH_REGISTRAR_URL_VAR: self._zenith.registrar_external_url,
            ZENITH_REGISTRAR_VERIFY_SSL_VAR: self._zenith.verify_ssl_clients,
            ZENITH_SSHD_HOST_VAR: self._zenith.sshd_host,
            ZENITH_SSHD_PORT_VAR: self._zenith.sshd_port,
        })
        # Make sure each service in the cluster type has variables
        for service in cluster_type.services:
            # Check if the service is enabled based on the future params
            if service.when:
                expr = self._jinja_env.compile_expression(service.when)
                service_enabled = expr(**next_params)
            else:
                service_enabled = True
            # Get the names of the variables for the service
            label_variable = ZENITH_LABEL_VAR_TPL.format(service.name)
            icon_url_variable = ZENITH_ICON_URL_VAR_TPL.format(service.name)
            subdomain_variable = ZENITH_SUBDOMAIN_VAR_TPL.format(service.name)
            fqdn_variable = ZENITH_FQDN_VAR_TPL.format(service.name)
            internal_fqdn_variable = ZENITH_INTERNAL_FQDN_VAR_TPL.format(service.name)
            token_variable = ZENITH_TOKEN_VAR_TPL.format(service.name)
            # Update the variables for the service
            if service_enabled:
                # If the subdomain variable is not present, reserve a new subdomain
                if subdomain_variable not in current_params:
                    reservation = self._zenith.reserve_subdomain()
                    zenith_params.update({
                        subdomain_variable: reservation.subdomain,
                        fqdn_variable: reservation.fqdn,
                        token_variable: reservation.token,
                    })
                    if reservation.internal_fqdn:
                        zenith_params[internal_fqdn_variable] = reservation.internal_fqdn
                # Always make sure that the icon URL and label are up to date
                zenith_params.update({
                    label_variable: service.label,
                    icon_url_variable: service.icon_url,
                })
            else:
                # If the service is disabled, unset all the variables
                zenith_params.update({
                    label_variable: None,
                    icon_url_variable: None,
                    subdomain_variable: None,
                    fqdn_variable: None,
                    internal_fqdn_variable: None,
                    token_variable: None,
                })
        return zenith_params

    def create_cluster(
        self,
        name: str,
        cluster_type: dto.ClusterType,
        params: t.Mapping[str, t.Any],
        ssh_key: t.Optional[str],
        resources: scheduling_dto.PlatformResources,
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
            resources,
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
        params = self._cloud_session.cluster_parameters()
        if self._zenith:
            cluster_type = self.find_cluster_type(cluster.cluster_type)
            params = self._with_zenith_params(params, cluster_type, cluster)
        ctx = dto.Context(self._username, self._user_id, self._tenancy)
        cluster = self._driver.patch_cluster(cluster, params, ctx)
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
