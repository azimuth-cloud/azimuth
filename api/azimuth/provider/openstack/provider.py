"""
This module contains the provider implementation for OpenStack.
"""

import base64
import dataclasses
import functools
import hashlib
import logging
import os
import random
import re
import time

import certifi

import dateutil.parser

import rackit

import yaml

from .. import base, errors, dto

from . import api


logger = logging.getLogger(__name__)


class Lazy:
    """
    Wrapper around a function invocation that lazily evaluates the result
    and caches it for future invocations.
    """
    def __init__(self, func, *args, **kwargs):
        self.func = func
        self.args = args
        self.kwargs = kwargs

    def __call__(self):
        if not hasattr(self, "result"):
            self.result = self.func(*self.args, **self.kwargs)
        return self.result


_REPLACEMENTS = [
    ("instance", "machine"),
    ("Instance", "Machine"),
    ("flavorRef", "size"),
    ("flavor", "size"),
    ("Flavor", "Size"),
    ("Security group rule", "Firewall rule"),
    ("Floating IP", "External IP"),
]
def _replace_resource_names(message):
    return functools.reduce(
        lambda a, x: a.replace(x[0], x[1]),
        _REPLACEMENTS,
        message
    )


def sanitise_username(username):
    """
    Sanitise a username for use in a keypair name.
    """
    return re.sub("[^a-zA-Z0-9]+", "-", username)


def convert_exceptions(f):
    """
    Decorator that converts OpenStack API exceptions into errors from :py:mod:`..errors`.
    """
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except api.ServiceNotSupported as exc:
            # Convert service not supported from the API module into unsupported operation
            raise errors.UnsupportedOperationError(str(exc))
        except rackit.ApiError as exc:
            # Extract the status code and message
            status_code = exc.status_code
            # Replace the OpenStack resource names with ours
            message = _replace_resource_names(str(exc))
            if status_code == 400:
                raise errors.BadInputError(message)
            elif status_code == 401:
                raise errors.AuthenticationError("Your session has expired.")
            elif status_code == 403:
                # Some quota exceeded errors get reported as permission denied (WHY???!!!)
                # So report them as quota exceeded instead
                if "exceeded" in message.lower():
                    raise errors.QuotaExceededError(
                        "Requested operation would exceed at least one quota. "
                        "Please check your tenancy quotas."
                    )
                raise errors.PermissionDeniedError("Permission denied.")
            elif status_code == 404:
                raise errors.ObjectNotFoundError(message)
            elif status_code == 409:
                # 409 (Conflict) has a lot of different sub-errors depending on
                # the actual error text
                if "exceeded" in message.lower():
                    raise errors.QuotaExceededError(
                        "Requested operation would exceed at least one quota. "
                        "Please check your tenancy quotas."
                    )
                raise errors.InvalidOperationError(message)
            elif status_code == 413:
                # The volume service uses 413 (Payload too large) for quota errors
                if "exceedsavailablequota" in message.lower():
                    raise errors.QuotaExceededError(
                        "Requested operation would exceed at least one quota. "
                        "Please check your tenancy quotas."
                    )
                raise errors.CommunicationError("Unknown error with OpenStack API.")
            else:
                raise errors.CommunicationError("Unknown error with OpenStack API.")
        except rackit.RackitError as exc:
            logger.exception("Could not connect to OpenStack API.")
            raise errors.CommunicationError("Could not connect to OpenStack API.")
    return wrapper


class Provider(base.Provider):
    """
    Provider implementation for OpenStack.

    Args:
        auth_url: The Keystone v3 authentication URL.
        domain: The domain to authenticate with (default ``Default``).
        interface: The OpenStack interface to connect using (default ``public``).
        metadata_prefix: The prefix to use for all Azimuth-related metadata (default ``azimuth_``).
        internal_net_template: Template for the name of the internal network to use
                               (default ``None``).
                               The current tenancy name can be templated in using the
                               fragment ``{tenant_name}``.
        external_net_template: Template for the name of the external network to use
                               (default ``None``).
                               The current tenancy name can be templated in using the
                               fragment ``{tenant_name}``.
        create_internal_net: If ``True`` (the default), then the internal network is auto-created
                             when a tagged network or templated network cannot be found.
        manila_project_share_gb: If >0 (the default is 0), then
                             manila project share is auto created with specified size.
        internal_net_cidr: The CIDR for the internal network when it is
                           auto-created (default ``192.168.3.0/24``).
        internal_net_dns_nameservers: The DNS nameservers for the internal network when it is
                           auto-created (default ``None``).
        az_backdoor_net_map: Mapping of availability zone to the UUID of the backdoor network
                             for that availability zone (default ``None``).
                             The backdoor network will only be attached if the image specifically
                             requests it. At that point, an availability zone will be randomly
                             selected, and if the network is not available an error will be raised.
        backdoor_vnic_type: The ``binding:vnic_type`` for the backdoor network. If not given,
                            no vNIC type will be specified (default ``None``).
        verify_ssl: If ``True`` (the default), verify SSL certificates. If ``False``
                    SSL certificates are not verified.
    """
    provider_name = "openstack"

    def __init__(self, auth_url,
                       domain = "Default",
                       interface = "public",
                       metadata_prefix = "azimuth_",
                       internal_net_template = None,
                       external_net_template = None,
                       create_internal_net = True,
                       manila_project_share_gb = 0,
                       internal_net_cidr = "192.168.3.0/24",
                       internal_net_dns_nameservers = None,
                       az_backdoor_net_map = None,
                       backdoor_vnic_type = None,
                       verify_ssl = True):
        # Strip any trailing slashes from the auth URL
        self._auth_url = auth_url.rstrip("/")
        self._domain = domain
        self._interface = interface
        self._metadata_prefix = metadata_prefix
        self._internal_net_template = internal_net_template
        self._external_net_template = external_net_template
        self._create_internal_net = create_internal_net
        self._manila_project_share_gb = 0
        if manila_project_share_gb:
            self._manila_project_share_gb = int(manila_project_share_gb)
        self._internal_net_cidr = internal_net_cidr
        self._internal_net_dns_nameservers = internal_net_dns_nameservers
        self._az_backdoor_net_map = az_backdoor_net_map or dict()
        self._backdoor_vnic_type = backdoor_vnic_type
        self._verify_ssl = verify_ssl

    @convert_exceptions
    def from_token(self, token):
        """
        See :py:meth:`.base.Provider.from_token`.
        """
        logger.info("Authenticating token with OpenStack")
        try:
            conn = api.Connection(self._auth_url, token, self._interface, self._verify_ssl)
        except (rackit.Unauthorized, rackit.NotFound):
            logger.info("Authentication failed for token")
            # Failing to validate a token is a 404 for some reason
            raise errors.AuthenticationError("Your session has expired.")
        else:
            logger.info("Successfully authenticated user '%s'", conn.username)
            return UnscopedSession(
                conn,
                metadata_prefix = self._metadata_prefix,
                internal_net_template = self._internal_net_template,
                external_net_template = self._external_net_template,
                create_internal_net = self._create_internal_net,
                manila_project_share_gb = self._manila_project_share_gb,
                internal_net_cidr = self._internal_net_cidr,
                internal_net_dns_nameservers = self._internal_net_dns_nameservers,
                az_backdoor_net_map = self._az_backdoor_net_map,
                backdoor_vnic_type = self._backdoor_vnic_type
            )


class UnscopedSession(base.UnscopedSession):
    """
    Unscoped session implementation for OpenStack.
    """
    provider_name = "openstack"

    def __init__(self, connection,
                       metadata_prefix = "azimuth_",
                       internal_net_template = None,
                       external_net_template = None,
                       create_internal_net = True,
                       manila_project_share_gb = 0,
                       internal_net_cidr = "192.168.3.0/24",
                       internal_net_dns_nameservers = None,
                       az_backdoor_net_map = None,
                       backdoor_vnic_type = None):
        self._connection = connection
        self._metadata_prefix = metadata_prefix
        self._internal_net_template = internal_net_template
        self._external_net_template = external_net_template
        self._create_internal_net = create_internal_net
        self._manila_project_share_gb = manila_project_share_gb
        self._internal_net_cidr = internal_net_cidr
        self._internal_net_dns_nameservers = internal_net_dns_nameservers
        self._az_backdoor_net_map = az_backdoor_net_map or dict()
        self._backdoor_vnic_type = backdoor_vnic_type

    def token(self):
        """
        See :py:meth:`.base.UnscopedSession.token`.
        """
        return self._connection.token

    def user_id(self) -> str:
        """
        See :py:meth:`.base.UnscopedSession.user_id`.
        """
        return self._connection.user_id

    def username(self):
        """
        See :py:meth:`.base.UnscopedSession.username`.
        """
        return self._connection.username

    def user_email(self):
        """
        See :py:meth:`.base.UnscopedSession.user_email`.
        """
        # If the username looks like an email address, just return that
        if "@" in self._connection.username:
            return self._connection.username
        # Otherwise, return a fake email address consisting of the username and domain
        return f"{self._connection.username}@{self._connection.domain_name.lower()}.openstack"

    def _log(self, message, *args, level = logging.INFO, **kwargs):
        logger.log(level, "[%s] " + message, self.username(), *args, **kwargs)

    def _scoped_connection_for_first_project(self):
        """
        Returns a scoped connection for the user's first project.
        """
        try:
            project = next(self._connection.projects.all())
        except StopIteration:
            raise errors.InvalidOperationError("User does not belong to any projects.")
        return self._connection.scoped_connection(project)

    def capabilities(self):
        """
        See :py:meth:`.base.UnscopedSession.capabilities`.
        """
        # We need a scoped connection to query the service catalog
        # If the user does not belong to any projects, use the default capabilties
        try:
            conn = self._scoped_connection_for_first_project()
        except errors.InvalidOperationError:
            return dto.Capabilities()
        # Check if the relevant services are available to the project
        try:
            _ = conn.block_store
        except api.ServiceNotSupported:
            supports_volumes = False
        else:
            supports_volumes = True
        return dto.Capabilities(supports_volumes = supports_volumes)

    @convert_exceptions
    def ssh_public_key(self, key_name):
        """
        See :py:meth:`.base.UnscopedSession.ssh_public_key`.
        """
        # Sanitise the requested name and try to find a keypair with that name
        keypair_name = sanitise_username(key_name)
        self._log("Attempting to locate keypair '%s'", keypair_name)
        # In OpenStack, SSH keys are shared between projects
        # So get a scoped connection for the user's first project to use
        connection = self._scoped_connection_for_first_project()
        keypair = connection.compute.keypairs.get(keypair_name)
        # Return the public key associated with that key
        return keypair.public_key

    @convert_exceptions
    def update_ssh_public_key(self, key_name, public_key):
        """
        See :py:meth:`.base.UnscopedSession.update_ssh_public_key`.
        """
        # Use the sanitised username as the keypair name
        keypair_name = sanitise_username(key_name)
        # In OpenStack, SSH keys are shared between projects
        # So get a scoped connection for the user's first project to use
        connection = self._scoped_connection_for_first_project()
        # Keypairs are immutable in OpenStack, so we first remove the existing keypair
        # If it doesn't exist, we can ignore that
        try:
            connection.compute.keypairs.delete(keypair_name)
        except rackit.NotFound:
            pass
        else:
            self._log("Deleted previous keypair '%s'", keypair_name)
        # Create a new keypair with the same name but the new key
        self._log("Creating keypair '%s'", keypair_name)
        keypair = connection.compute.keypairs.create(
            name = keypair_name,
            public_key = public_key
        )
        return keypair.public_key

    @convert_exceptions
    def tenancies(self):
        """
        See :py:meth:`.base.UnscopedSession.tenancies`.
        """
        self._log("Fetching available tenancies")
        projects = tuple(self._connection.projects.all())
        self._log("Found %s projects", len(projects))
        return tuple(dto.Tenancy(p.id, p.name) for p in projects if p.enabled)

    @convert_exceptions
    def scoped_session(self, tenancy):
        """
        See :py:meth:`.base.UnscopedSession.scoped_session`.
        """
        # Make sure we have a tenancy id
        if not isinstance(tenancy, dto.Tenancy):
            # There is no (obvious) way to list individual auth projects, so traverse the list
            try:
                tenancy = next(t for t in self.tenancies() if t.id == tenancy)
            except StopIteration:
                raise errors.ObjectNotFoundError(
                    "Could not find tenancy with ID {}.".format(tenancy)
                )
        self._log("Creating scoped session for project '%s'", tenancy.name)
        try:
            return ScopedSession(
                self.username(),
                tenancy,
                self._connection.scoped_connection(tenancy.id),
                metadata_prefix = self._metadata_prefix,
                internal_net_template = self._internal_net_template,
                external_net_template = self._external_net_template,
                create_internal_net = self._create_internal_net,
                manila_project_share_gb = self._manila_project_share_gb,
                internal_net_cidr = self._internal_net_cidr,
                internal_net_dns_nameservers = self._internal_net_dns_nameservers,
                az_backdoor_net_map = self._az_backdoor_net_map,
                backdoor_vnic_type = self._backdoor_vnic_type
            )
        except (rackit.Unauthorized, rackit.Forbidden):
            raise errors.ObjectNotFoundError(
                "Could not find tenancy with ID {}.".format(tenancy.id)
            )

    def close(self):
        """
        See :py:meth:`.base.UnscopedSession.close`.
        """
        # Just close the underlying connection
        self._connection.close()


class ScopedSession(base.ScopedSession):
    """
    Tenancy-scoped session implementation for OpenStack.
    """
    provider_name = "openstack"

    def __init__(self, username,
                       tenancy,
                       connection,
                       metadata_prefix = "azimuth_",
                       internal_net_template = None,
                       external_net_template = None,
                       create_internal_net = True,
                       manila_project_share_gb = 0,
                       internal_net_cidr = "192.168.3.0/24",
                       internal_net_dns_nameservers = None,
                       az_backdoor_net_map = None,
                       backdoor_vnic_type = None):
        self._username = username
        self._tenancy = tenancy
        self._connection = connection
        self._metadata_prefix = metadata_prefix
        self._internal_net_template = internal_net_template
        self._external_net_template = external_net_template
        self._create_internal_net = create_internal_net
        self._manila_project_share_gb = manila_project_share_gb
        self._internal_net_cidr = internal_net_cidr
        self._internal_net_dns_nameservers = internal_net_dns_nameservers
        self._az_backdoor_net_map = az_backdoor_net_map or dict()
        self._backdoor_vnic_type = backdoor_vnic_type

        # TODO(johngarbutt): consider moving some of this to config
        # and/or hopefully having this feature on by default
        # and auto detecting when its available, which is not currently
        # feasible.
        self._project_share_name = "azimuth-project-share"
        prefix = "proj"
        project_id_safe = self._connection.project_id.replace("-", "")
        self._project_share_user = prefix + project_id_safe

    def _log(self, message, *args, level = logging.INFO, **kwargs):
        logger.log(
            level,
            "[%s] [%s] " + message,
            self._username, self._tenancy.name, *args, **kwargs
        )

    def user_id(self) -> str:
        """
        See :py:meth:`.base.ScopedSession.user_id`.
        """
        return self._connection.user_id

    def username(self):
        """
        See :py:meth:`.base.ScopedSession.username`.
        """
        return self._username

    def tenancy(self):
        """
        See :py:meth:`.base.ScopedSession.tenancy`.
        """
        return self._tenancy

    @convert_exceptions
    def quotas(self):
        """
        See :py:meth:`.base.ScopedSession.quotas`.
        """
        self._log("Fetching tenancy quotas")
        # Compute provides a way to fetch this information through the SDK, but
        # the floating IP quota obtained through it is rubbish...
        compute_limits = self._connection.compute.limits.absolute
        quotas = [
            dto.Quota(
                "cpus",
                "CPUs",
                None,
                compute_limits.total_cores,
                compute_limits.total_cores_used
            ),
            dto.Quota(
                "ram",
                "RAM",
                "MB",
                compute_limits.total_ram,
                compute_limits.total_ram_used
            ),
            dto.Quota(
                "machines",
                "Machines",
                None,
                compute_limits.instances,
                compute_limits.instances_used
            ),
        ]
        # Get the floating ip quota
        network_quotas = self._connection.network.quotas
        quotas.append(
            dto.Quota(
                "external_ips",
                "External IPs",
                None,
                network_quotas.floatingip,
                # Just get the length of the list of IPs
                len(list(self._connection.network.floatingips.all()))
            )
        )
        # The volume service is optional
        # In the case where the service is not enabled, just don't add the quotas
        try:
            volume_limits = self._connection.block_store.limits.absolute
            quotas.extend([
                dto.Quota(
                    "storage",
                    "Volume Storage",
                    "GB",
                    volume_limits.total_volume_gigabytes,
                    volume_limits.total_gigabytes_used
                ),
                dto.Quota(
                    "volumes",
                    "Volumes",
                    None,
                    volume_limits.volumes,
                    volume_limits.volumes_used
                )
            ])
        except api.ServiceNotSupported:
            pass
        return quotas

    def _from_api_image(self, api_image):
        """
        Converts an OpenStack API image object into a :py:class:`.dto.Image`.
        """
        # Gather the metadata items with the specified prefix
        # As well as the image metadata, we also treat tags with the specified prefix
        # as metadata items with a value of "1"
        metadata = {
            key.removeprefix(self._metadata_prefix): value
            for key, value in api_image._data.items()
            if key.startswith(self._metadata_prefix)
        }
        metadata.update({
            tag.removeprefix(self._metadata_prefix): "1"
            for tag in getattr(api_image, "tags") or []
            if tag.startswith(self._metadata_prefix)
        })
        return dto.Image(
            api_image.id,
            api_image.name,
            api_image.visibility == "public",
            # The image size is specified in bytes. Convert to MB.
            float(api_image.size) / 1024.0 / 1024.0,
            metadata = metadata
        )

    @convert_exceptions
    def images(self):
        """
        See :py:meth:`.base.ScopedSession.images`.
        """
        self._log("Fetching available images")
        # Fetch from the SDK using our custom image resource
        images = list(self._connection.image.images.all(
            status = "active",
            # Only show shared images that have been accepted
            member_status = "accepted"
        ))
        self._log("Found %s images", len(images))
        return tuple(self._from_api_image(i) for i in images)

    @convert_exceptions
    def find_image(self, id):
        """
        See :py:meth:`.base.ScopedSession.find_image`.
        """
        self._log("Fetching image with id '%s'", id)
        # Just convert the SDK image to a DTO image
        return self._from_api_image(self._connection.image.images.get(id))

    def _from_api_flavor(self, api_flavor):
        """
        Converts an OpenStack API flavor object into a :py:class:`.dto.Size`.
        """
        return dto.Size(
            api_flavor.id,
            api_flavor.name,
            getattr(api_flavor, "description", None),
            api_flavor.vcpus,
            api_flavor.ram,
            api_flavor.disk,
            getattr(api_flavor, "ephemeral_disk", 0),
            getattr(api_flavor, "extra_specs", None) or {}
        )

    @convert_exceptions
    def sizes(self):
        """
        See :py:meth:`.base.ScopedSession.sizes`.
        """
        self._log("Fetching available flavors")
        flavors = tuple(
            self._from_api_flavor(flavor)
            for flavor in self._connection.compute.flavors.all()
            if not flavor.is_disabled
        )
        self._log("Found %s flavors", len(flavors))
        return flavors

    @convert_exceptions
    def find_size(self, id):
        """
        See :py:meth:`.base.ScopedSession.find_size`.
        """
        self._log("Fetching flavor with id '%s'", id)
        return self._from_api_flavor(self._connection.compute.flavors.get(id))

    def _tagged_network(self, net_type):
        """
        Returns the first network with the given tag, or None if there is not one.
        """
        tag = "portal-{}".format(net_type)
        # By default, networks.all() will only return networks that belong to the project
        # For the internal network this is what we want, but for all other types of network
        # (e.g. external, storage) we want to allow shared networks from other projects to
        # be selected - setting "project_id = None" allows this to happen
        kwargs = {} if net_type == "internal" else {"project_id": None}
        networks = list(self._connection.network.networks.all(tags = tag, **kwargs))
        if len(networks) == 1:
            self._log("Using tagged %s network '%s'", net_type, networks[0].name)
            return networks[0]
        elif len(networks) > 1:
            self._log("Found multiple networks with tag '%s'.", tag, level = logging.ERROR)
            raise errors.InvalidOperationError(f"Found multiple networks with tag '{tag}'.")
        else:
            self._log("Failed to find tagged %s network.", net_type, level = logging.WARN)
            return None

    def _templated_network(self, template, net_type):
        """
        Returns the network specified by the template, after interpolating with the tenant name.

        If the network does not exist, that is a config error and an exception is raised.
        """
        net_name = template.format(tenant_name = self._tenancy.name)
        # By default, networks.all() will only return networks that belong to the project
        # For the internal network this is what we want, but for all other types of network
        # (e.g. external, storage) we want to allow shared networks from other projects to
        # be selected - setting "project_id = None" allows this to happen
        kwargs = {} if net_type == "internal" else {"project_id": None}
        networks = list(self._connection.network.networks.all(name = net_name, **kwargs))
        if len(networks) == 1:
            self._log("Found %s network '%s' using template.", net_type, networks[0].name)
            return networks[0]
        elif len(networks) > 1:
            self._log("Found multiple networks named '%s'.", net_name, level = logging.ERROR)
            raise errors.InvalidOperationError(f"Found multiple networks named '{net_name}'.")
        else:
            self._log(
                "Failed to find %s network '%s' from template.",
                net_type,
                net_name,
                level = logging.ERROR
            )
            raise errors.InvalidOperationError("Could not find {} network.".format(net_type))

    def _tenant_network(self, create_network = False):
        """
        Returns the tenant internal network.

        If create_network = True then an attempt is made to auto-create the networking.
        If this fails then an exception is raised.

        If create_network = False then None is returned when the network is not found.
        """
        # First, try to find a network that is tagged as the portal internal network
        tagged_network = self._tagged_network("internal")
        if tagged_network:
            return tagged_network
        # Next, attempt to use the name template
        if self._internal_net_template:
            return self._templated_network(self._internal_net_template, "internal")
        # If we get to here and are not creating a network, return
        if not create_network:
            return None
        if self._create_internal_net:
            # Unfortunately, the tags cannot be set in the POST request
            self._log("Creating internal network")
            network = self._connection.network.networks.create(name = "portal-internal")
            network._update_tags(["portal-internal"])
            # Create a subnet for the network
            self._log("Creating subnet for network '%s'", network.name)
            subnet_create_args = {
                "name": "portal-internal",
                "network_id": network.id,
                "ip_version": 4,
                "cidr": self._internal_net_cidr
            }
            # When internal_net_dns_nameservers is set, add it to the subnet.
            if self._internal_net_dns_nameservers is not None:
                subnet_create_args['dns_nameservers'] = self._internal_net_dns_nameservers
            subnet = self._connection.network.subnets.create(**subnet_create_args)
            # If we can find an external network, create a router that links the two
            try:
                external_network = self._external_network()
            except errors.InvalidOperationError:
                self._log(
                    "Failed to find external network",
                    level = logging.WARN,
                    exc_info = True
                )
            else:
                self._log("Creating tenant router")
                router = self._connection.network.routers.create(
                    name = "portal-router",
                    external_gateway_info = dict(network_id = external_network.id)
                )
                self._log("Attaching router to network '%s'", network.name)
                router._add_interface(subnet_id = subnet.id)
            return network
        else:
            raise errors.InvalidOperationError("Could not find internal network.")

    def _project_share(self, create_share=True):
        """
        Returns the project specific Manila share.

        If we are not configured to create the project share,
        we do nothing here, and return None.

        If we are configured to create the project share,
        we look to see if a valid share is already created.
        If we find a valid share, we return that object.

        Finally, we look to create the share dynamically,
        then return that share.

        If this project has not available share type in
        Manila, we simply log that we can't create a share
        for this project, and return None.
        """
        if not self._manila_project_share_gb:
            return

        # find if project share exists
        project_share = None
        current_shares = self._connection.share.shares.all()
        for share in current_shares:
            if share.name == self._project_share_name:
                project_share = share
        if project_share:
            # double check share has the correct protocol and is available
            share_details = self._connection.share.shares.get(project_share.id)
            self._log(f"Got share details f{share_details}")
            if share_details.share_proto.upper() != "CEPHFS":
                raise errors.ImproperlyConfiguredError(
                    "Currently only support CephFS shares!")
            if share_details.status.lower() != "available":
                raise errors.ImproperlyConfiguredError(
                    "Project share is not available!")
            if share_details.access_rules_status.lower() != "active":
                raise errors.ImproperlyConfiguredError(
                    "Project share has a problem with its access rules!")

            access_list = list(self._connection.share.access.all(
                share_id=project_share.id))
            found_expected_access = False
            for access in access_list:
                if access.access_to == self._project_share_user:
                    found_expected_access = True
                    break
            if not found_expected_access:
                raise errors.ImproperlyConfiguredError("can't find the expected access rule!")
            self._log(f"Found project share for: {self._connection.project_id}")

        # no share found, create if required
        if not project_share and create_share:
            self._log(f"Creating project share for: {self._connection.project_id}")

            # Find share type
            default_share_type = None
            all_types = list(self._connection.share.types.all())
            if len(all_types) == 1:
                default_share_type = all_types[0]
            else:
                for share_type in all_types:
                    if share_type.is_default:
                        default_share_type = share_type
                        break
            if not default_share_type:
                # Silent ignore here, as it usually means project
                # has not been setup for manila
                self._log("Unable to find valid share type!")
                return

            # TODO(johngarbutt) need to support non-ceph types eventually
            project_share = self._connection.share.shares.create(
                share_proto="CephFS",
                size=self._manila_project_share_gb,
                name=self._project_share_name,
                description="Project share auto-created by Azimuth.",
                share_type=default_share_type.id)

            # wait for share to be available before trying to grant access
            for _ in range(10):
                latest = self._connection.share.shares.get(project_share.id)
                if latest.status.lower() == "available":
                    break
                if latest.status.lower() == "error":
                    raise errors.Error("Unable to create project share.")
                time.sleep(0.1)

            project_share.grant_rw_access(self._project_share_user)
            # TODO(johngarbutt) should we wait for access to be granted?
            self._log(f"Created new project share: {project_share.id}")

        return project_share

    def _external_network(self):
        """
        Returns the external network that connects the tenant router to the outside world.
        """
        # First, try to find a network that is tagged as the portal external network
        tagged_network = self._tagged_network("external")
        if tagged_network:
            return tagged_network
        # Next, attempt to use the name template
        if self._external_net_template:
            return self._templated_network(self._external_net_template, "external")
        # If there is exactly one external network available, use that
        params = { "router:external": True }
        networks = (
            list(self._connection.network.networks.all(**params)) +
            list(self._connection.network.networks.all(**params, project_id = None))
        )
        if len(networks) == 1:
            return networks[0]
        elif len(networks) > 1:
            raise errors.InvalidOperationError("Multiple external networks found.")
        else:
            raise errors.InvalidOperationError("Could not find external network.")
    
    def _storage_network(self):
        """
        Returns the direct storage network.
        """
        # Try to find a network that is tagged as the portal storage network
        tagged_network = self._tagged_network("storage")
        
        return tagged_network

    def _get_or_create_keypair(self, ssh_key):
        """
        Returns a Nova keypair for the given SSH key.
        """
        # Keypairs are immutable, i.e. once created cannot be changed
        # We create keys with names of the form "<username>-<truncated fingerprint>",
        # which allows for us to recognise when a user has changed their key and create
        # a new one
        fingerprint = hashlib.md5(base64.b64decode(ssh_key.split()[1])).hexdigest()
        key_name = "{username}-{fingerprint}".format(
            # Sanitise the username by replacing non-alphanumerics with -
            username = sanitise_username(self._username),
            # Truncate the fingerprint to 8 characters
            fingerprint = fingerprint[:8]
        )
        try:
            # We need to force a fetch so that the keypair is resolved
            return self._connection.compute.keypairs.get(key_name, force = True)
        except rackit.NotFound:
            return self._connection.compute.keypairs.create(
                name = key_name,
                public_key = ssh_key
            )

    _POWER_STATES = {
        0: "Unknown",
        1: "Running",
        3: "Paused",
        4: "Shut down",
        6: "Crashed",
        7: "Suspended",
    }

    def _from_api_server(self, api_server, flavors, get_tenant_network):
        """
        Returns a machine DTO for the given API server representation.
        """
        flavor_name = getattr(api_server, "flavor", {}).get("original_name")
        flavor_id = flavors.get(flavor_name) if flavor_name else None
        status = api_server.status
        fault = api_server.fault.get("message", None)
        task = api_server.task_state
        # Function to get the first IP of a particular type for a machine
        # We prefer to get an IP on the specified tenant network, but if the machine is
        # not connected to that network we just return the first IP
        def ip_of_type(ip_type):
            addresses_of_type = {}
            for net, addresses in api_server.addresses.items():
                for address in addresses:
                    if address["version"] == 4 and address["OS-EXT-IPS:type"] == ip_type:
                        addresses_of_type[net] = address["addr"]
                        break
            # If the machine has more than one IP, attempt to select the one on the tenant net
            if len(addresses_of_type) > 1:
                tenant_network = get_tenant_network()
                if tenant_network and tenant_network.name in addresses_of_type:
                    return addresses_of_type[tenant_network.name]
            # Otherwise just return the first one
            return next(iter(addresses_of_type.values()), None)
        return dto.Machine(
            api_server.id,
            api_server.name,
            (getattr(api_server, "image", None) or {}).get("id"),
            flavor_id,
            dto.MachineStatus(
                getattr(dto.MachineStatusType, status, dto.MachineStatusType.OTHER),
                status,
                _replace_resource_names(fault) if fault else None
            ),
            self._POWER_STATES[api_server.power_state],
            task.capitalize() if task else None,
            ip_of_type("fixed"),
            ip_of_type("floating"),
            tuple(v["id"] for v in api_server.attached_volumes),
            # Return only the metadata items with the specified prefix
            {
                key.removeprefix(self._metadata_prefix): value
                for key, value in api_server.metadata.items()
                if key.startswith(self._metadata_prefix)
            },
            api_server.user_id,
            dateutil.parser.parse(api_server.created)
        )

    @convert_exceptions
    def machines(self):
        """
        See :py:meth:`.base.ScopedSession.machines`.
        """
        self._log("Fetching available servers")
        api_servers = tuple(self._connection.compute.servers.all())
        self._log("Found %s servers", len(api_servers))
        # We need to be able to look up the flavor ID from the name, which is all that is reported
        # To avoid multiple queries, we look up all the flavors and index them by name
        flavors = { f.name: f.id for f in self._connection.compute.flavors.all() }
        # Note that this will (a) only load the network if required and (b)
        # reuse the network once loaded
        get_tenant_network = Lazy(self._tenant_network)
        return tuple(self._from_api_server(s, flavors, get_tenant_network) for s in api_servers)

    @convert_exceptions
    def find_machine(self, id):
        """
        See :py:meth:`.base.ScopedSession.find_machine`.
        """
        self._log("Fetching server with id '%s'", id)
        server = self._connection.compute.servers.get(id)
        # We need to be able to look up the flavor from the name
        # It is not possible to filter the query by name using GET params, so the best
        # we can do it query the list and index it
        flavors = { f.name: f.id for f in self._connection.compute.flavors.all() }
        # Don't discover the tenant network unless the server is found
        get_tenant_network = Lazy(self._tenant_network)
        return self._from_api_server(server, flavors, get_tenant_network)

    @convert_exceptions
    def fetch_logs_for_machine(self, machine):
        """
        See :py:meth:`.base.ScopedSession.fetch_logs_for_machine`.
        """
        machine = machine.id if isinstance(machine, dto.Machine) else machine
        self._log("Fetching logs for machine '%s'", machine)
        logs = self._connection.compute.servers.get(machine).logs()
        # Split the logs into lines before returning them
        return logs.splitlines()

    @convert_exceptions
    def create_machine(self, name, image, size, ssh_key = None, metadata = None, userdata = None):
        """
        See :py:meth:`.base.ScopedSession.create_machine`.
        """
        # Start building the server params
        params = dict(name = name)
        # If an id was given, resolve it to an image
        if not isinstance(image, dto.Image):
            try:
                image = self.find_image(image)
            except errors.ObjectNotFoundError:
                raise errors.BadInputError("Invalid image provided.")
        params.update(image_id = str(image.id))
        size = size.id if isinstance(size, dto.Size) else size
        params.update(flavor_id = size)
        self._log("Creating machine '%s' (image: %s, size: %s)", name, image.name, size)
        # Get the networks to use
        # Always use the tenant network, creating it if required
        params.update(networks = [{ "uuid": self._tenant_network(True).id }])
        # If the image asks for the backdoor network, attach it
        if image.metadata.get(self._metadata_prefix + "private_if"):
            if not self._az_backdoor_net_map:
                raise errors.ImproperlyConfiguredError(
                    "Backdoor network required by image but not configured."
                )
            # Pick an availability zone at random
            #   random.choice needs something that supports indexing
            choices = list(self._az_backdoor_net_map.items())
            availability_zone, backdoor_net = random.choice(choices)
            # If the availability zone is "nova" don't specify it, as per the advice
            # in the OpenStack API documentation
            if availability_zone != "nova":
                params.update(availability_zone = availability_zone)
            # Create a port on the backdoor network
            port_params = dict(network_id = backdoor_net)
            # If a vNIC type is specified, add it to the port parameters
            if self._backdoor_vnic_type:
                port_params["binding:vnic_type"] = self._backdoor_vnic_type
            port = self._connection.network.ports.create(port_params)
            params["networks"].append({ "port": port.id })
        # Get the keypair to inject
        if ssh_key:
            keypair = self._get_or_create_keypair(ssh_key)
            params.update(key_name = keypair.name)
        # Build the machine metadata, starting with the tenant name
        machine_metadata = { self._metadata_prefix + "tenant_name": self._tenancy.name }
        # Copy metadata from the image
        machine_metadata.update({
            self._metadata_prefix + key: value
            for key, value in image.metadata.items()
        })
        # Add any provided metadata to the default metadata
        if metadata:
            machine_metadata.update({
                self._metadata_prefix + key: str(value)
                for key, value in metadata.items()
            })
        params.update(metadata = machine_metadata)
        # Add any user data script that was given - it must be base64-encoded
        if userdata:
            # The user data must be base64-encoded
            userdata_b64 = base64.b64encode(userdata.encode()).decode()
            params.update(user_data = userdata_b64)
        server = self._connection.compute.servers.create(params)
        return self.find_machine(server.id)

    @convert_exceptions
    def start_machine(self, machine):
        """
        See :py:meth:`.base.ScopedSession.start_machine`.
        """
        machine = machine.id if isinstance(machine, dto.Machine) else machine
        self._log("Starting machine '%s'", machine)
        self._connection.compute.servers.get(machine).start()
        return self.find_machine(machine)

    @convert_exceptions
    def stop_machine(self, machine):
        """
        See :py:meth:`.base.ScopedSession.stop_machine`.
        """
        machine = machine.id if isinstance(machine, dto.Machine) else machine
        self._log("Stopping machine '%s'", machine)
        self._connection.compute.servers.get(machine).stop()
        return self.find_machine(machine)

    @convert_exceptions
    def restart_machine(self, machine):
        """
        See :py:meth:`.base.ScopedSession.restart_machine`.
        """
        machine = machine.id if isinstance(machine, dto.Machine) else machine
        self._log("Restarting machine '%s'", machine)
        self._connection.compute.servers.get(machine).reboot("SOFT")
        return self.find_machine(machine)

    @convert_exceptions
    def delete_machine(self, machine):
        """
        See :py:meth:`.base.ScopedSession.delete_machine`.
        """
        machine = machine.id if isinstance(machine, dto.Machine) else machine
        self._log("Deleting machine '%s'", machine)
        # First, delete any associated ports
        for port in self._connection.network.ports.all(device_id = machine):
            port._delete()
        self._connection.compute.servers.delete(machine)
        # Once the machine is deleted, delete the instance security group
        secgroup_name = "instance-{}".format(machine)
        secgroup = self._connection.network.security_groups.find_by_name(secgroup_name)
        if secgroup:
            secgroup._delete()
        try:
            return self.find_machine(machine)
        except errors.ObjectNotFoundError:
            return None

    def _api_rule_is_supported(self, api_rule):
        # Only consider IPv4 rules for protocols we recognise
        return (
            api_rule["ethertype"] == "IPv4" and
            (
                api_rule["protocol"] is None or
                api_rule["protocol"].upper() in { p.name for p in dto.FirewallRuleProtocol }
            )
        )

    def _from_api_security_group_rule(self, secgroup_names, api_rule):
        params = dict(
            id = api_rule["id"],
            direction = dto.FirewallRuleDirection[api_rule["direction"].upper()],
            protocol = (
                dto.FirewallRuleProtocol[api_rule["protocol"].upper()]
                if api_rule["protocol"] is not None
                else dto.FirewallRuleProtocol.ANY
            )
        )
        if api_rule["port_range_max"]:
            params.update(
                port_range = (
                    api_rule["port_range_min"],
                    api_rule["port_range_max"]
                )
            )
        if api_rule["remote_group_id"]:
            params.update(remote_group = secgroup_names[api_rule["remote_group_id"]])
        else:
            params.update(remote_cidr = api_rule["remote_ip_prefix"] or "0.0.0.0/0")
        return dto.FirewallRule(**params)

    @convert_exceptions
    def fetch_firewall_rules_for_machine(self, machine):
        machine = machine.id if isinstance(machine, dto.Machine) else machine
        # All we get from the machine is security group names
        # This means that we need to load all the security groups to find them
        self._log("Fetching security groups")
        security_groups = list(self._connection.network.security_groups.all())
        # Index the names of the security groups so we can easily resolve them later
        secgroup_names = { s.id: s.name for s in security_groups }
        self._log("Filtering machine security groups for '%s'", machine)
        # Filter the security groups that apply to the machine
        machine = self._connection.compute.servers.get(machine)
        machine_security_groups = [
            group
            for group in security_groups
            if group.name in { sg["name"] for sg in machine.security_groups }
        ]
        # The instance security group is the only editable one
        instance_secgroup = "instance-{}".format(machine.id)
        return [
            dto.FirewallGroup(
                name = group.name,
                editable = group.name == instance_secgroup,
                rules = [
                    self._from_api_security_group_rule(secgroup_names, rule)
                    for rule in group.security_group_rules
                    if self._api_rule_is_supported(rule)
                ]
            )
            for group in machine_security_groups
        ]

    @convert_exceptions
    def add_firewall_rule_to_machine(
        self,
        machine,
        direction,
        protocol,
        port = None,
        remote_cidr = None
    ):
        machine = machine.id if isinstance(machine, dto.Machine) else machine
        self._log("Finding instance security group for '%s'", machine)
        secgroup_name = "instance-{}".format(machine)
        secgroup = self._connection.network.security_groups.find_by_name(secgroup_name)
        if secgroup:
            self._log("Found existing security group '%s'", secgroup_name)
        else:
            self._log("Creating security group '%s'", secgroup_name)
            secgroup = self._connection.network.security_groups.create(
                name = secgroup_name,
                description = "Instance rules for {}".format(machine)
            )
            # Delete the default rules
            for rule in secgroup.security_group_rules:
                self._connection.network.security_group_rules.delete(rule["id"])
            self._connection.compute.servers.get(machine).add_security_group(secgroup.name)
        # Now we have the group, we can add the rule
        params = dict(
            security_group_id = secgroup.id,
            ethertype = "IPv4",
            direction = "ingress" if direction is dto.FirewallRuleDirection.INBOUND else "egress"
        )
        if protocol != dto.FirewallRuleProtocol.ANY:
            params.update(protocol = protocol.name.lower())
        # Only use the port when protocol is UDP or TCP
        if protocol.requires_port() and port:
            params.update(port_range_min = port, port_range_max = port)
        if remote_cidr:
            params.update(remote_ip_prefix = remote_cidr)
        _ = self._connection.network.security_group_rules.create(**params)
        return self.fetch_firewall_rules_for_machine(machine)

    @convert_exceptions
    def remove_firewall_rule_from_machine(self, machine, rule):
        machine = machine.id if isinstance(machine, dto.Machine) else machine
        rule = rule.id if isinstance(rule, dto.FirewallRule) else rule
        self._connection.network.security_group_rules.delete(rule)
        return self.fetch_firewall_rules_for_machine(machine)

    def _from_api_floatingip(self, api_floatingip, ports = None):
        """
        Converts an OpenStack API floatingip object into a :py:class:`.dto.ExternalIp`.
        """
        if api_floatingip.port_id:
            if ports:
                port = ports[api_floatingip.port_id]
            else:
                port = self._connection.network.ports.get(api_floatingip.port_id)
        else:
            port = None

        return dto.ExternalIp(
            api_floatingip.id,
            api_floatingip.floating_ip_address,
            not port,
            getattr(port, "device_id", "") or None
        )

    @convert_exceptions
    def external_ips(self):
        """
        See :py:meth:`.base.ScopedSession.external_ips`.
        """
        self._log("Fetching floating ips")
        # Only consider FIPs on the specified external network
        extnet = self._external_network()
        fips = list(self._connection.network.floatingips.all(floating_network_id = extnet.id))
        self._log("Found %s floating ips", len(fips))
        # If any floating IPs were found, fetch all the ports in one go and index them
        # by ID so we can locate the attached machines without making one request per port
        if fips:
            self._log("Fetching ports")
            ports = { p.id: p for p in self._connection.network.ports.all() }
        else:
            ports = {}
        return tuple(self._from_api_floatingip(fip, ports) for fip in fips)

    @convert_exceptions
    def allocate_external_ip(self):
        """
        See :py:meth:`.base.ScopedSession.allocate_external_ip`.
        """
        self._log("Allocating new floating ip")
        # Get the external network to allocate IPs on
        extnet = self._external_network()
        # Create a new floating IP on that network
        fip = self._connection.network.floatingips.create(floating_network_id = extnet.id)
        self._log("Allocated new floating ip '%s'", fip.floating_ip_address)
        return self._from_api_floatingip(fip)

    @convert_exceptions
    def find_external_ip(self, ip):
        """
        See :py:meth:`.base.ScopedSession.find_external_ip`.
        """
        self._log("Fetching floating IP with id '%s'", ip)
        fip = self._connection.network.floatingips.get(ip)
        # Check that the FIP belongs to the correct external network
        extnet = self._external_network()
        if fip.floating_network_id == extnet.id:
            return self._from_api_floatingip(fip)
        else:
            raise errors.ObjectNotFoundError("External IP {} could not be found".format(ip))

    @convert_exceptions
    def find_external_ip_by_ip_address(self, ip_address):
        """
        See :py:meth:`.base.ScopedSession.find_external_ip_by_ip_address`.
        """
        self._log("Fetching floating IP '%s'", ip_address)
        # Only consider FIPs on the correct network
        extnet = self._external_network()
        fips = self._connection.network.floatingips.all(
            floating_network_id = extnet.id,
            floating_ip_address = ip_address
        )
        try:
            return self._from_api_floatingip(next(fips))
        except StopIteration:
            raise errors.ObjectNotFoundError(
                "External IP {} could not be found".format(ip_address)
            )

    @convert_exceptions
    def attach_external_ip(self, ip, machine):
        """
        See :py:meth:`.base.ScopedSession.attach_external_ip`.
        """
        machine = machine.id if isinstance(machine, dto.Machine) else machine
        # If the IP is given as an ID, make sure it belongs to the correct extnet
        ip = ip if isinstance(ip, dto.ExternalIp) else self.find_external_ip(ip)
        self._log("Attaching floating ip '%s' to server '%s'", ip.id, machine)
        # Get the port that attaches the machine to the tenant network
        tenant_network = self._tenant_network()
        if tenant_network:
            port = next(
                self._connection.network.ports.all(
                    device_id = machine,
                    network_id = tenant_network.id
                ),
                None
            )
        else:
            port = None
        if not port:
            raise errors.InvalidOperationError("Machine is not connected to tenant network.")
        # If there is already a floating IP associated with the port, detach it
        current = self._connection.network.floatingips.find_by_port_id(port.id)
        if current:
            current._update(port_id = None)
        # Find the floating IP instance and associate the floating IP with the port
        fip = self._connection.network.floatingips.get(ip.id)
        return self._from_api_floatingip(fip._update(port_id = port.id))

    @convert_exceptions
    def detach_external_ip(self, ip):
        """
        See :py:meth:`.base.ScopedSession.detach_external_ip`.
        """
        ip = ip.id if isinstance(ip, dto.ExternalIp) else ip
        self._log("Detaching floating ip '%s'", ip)
        # Remove any association for the floating IP
        fip = self._connection.network.floatingips.get(ip)
        return self._from_api_floatingip(fip._update(port_id = None))

    _VOLUME_STATUSES = {
        "creating": dto.VolumeStatus.CREATING,
        "available": dto.VolumeStatus.AVAILABLE,
        "reserved": dto.VolumeStatus.ATTACHING,
        "attaching": dto.VolumeStatus.ATTACHING,
        "detaching": dto.VolumeStatus.DETACHING,
        "in-use": dto.VolumeStatus.IN_USE,
        "deleting": dto.VolumeStatus.DELETING,
        "error": dto.VolumeStatus.ERROR,
        "error_deleting": dto.VolumeStatus.ERROR,
        "error_backing-up": dto.VolumeStatus.ERROR,
        "error_restoring": dto.VolumeStatus.ERROR,
        "error_extending": dto.VolumeStatus.ERROR,
    }

    def _from_api_volume(self, api_volume):
        """
        Converts an OpenStack API volume object into a :py:class:`.dto.Volume`.
        """
        # Work out the volume status
        status = self._VOLUME_STATUSES.get(
            api_volume.status.lower(),
            dto.VolumeStatus.OTHER
        )
        try:
            attachment = api_volume.attachments[0]
        except IndexError:
            attachment = None
        return dto.Volume(
            api_volume.id,
            # If there is no name, use part of the ID
            api_volume.name or api_volume.id[:13],
            status,
            api_volume.size,
            attachment["server_id"] if attachment else None,
            attachment["device"] if attachment else None
        )

    @convert_exceptions
    def volumes(self):
        """
        See :py:meth:`.base.ScopedSession.volumes`.
        """
        self._log("Fetching available volumes")
        volumes = tuple(
            self._from_api_volume(v)
            for v in self._connection.block_store.volumes.all()
        )
        self._log("Found %s volumes", len(volumes))
        return volumes

    @convert_exceptions
    def find_volume(self, id):
        """
        See :py:meth:`.base.ScopedSession.find_volume`.
        """
        self._log("Fetching volume with id '%s'", id)
        volume = self._connection.block_store.volumes.get(id)
        return self._from_api_volume(volume)

    @convert_exceptions
    def create_volume(self, name, size):
        """
        See :py:meth:`.base.ScopedSession.create_volume`.
        """
        self._log("Creating volume '%s' (size: %s)", name, size)
        volume = self._connection.block_store.volumes.create(name = name, size = size)
        return self.find_volume(volume.id)

    @convert_exceptions
    def delete_volume(self, volume):
        """
        See :py:meth:`.base.ScopedSession.delete_volume`.
        """
        volume = volume if isinstance(volume, dto.Volume) else self.find_volume(volume)
        if volume.status not in [dto.VolumeStatus.AVAILABLE, dto.VolumeStatus.ERROR]:
            raise errors.InvalidOperationError(
                "Cannot delete volume with status {}.".format(volume.status.name)
            )
        self._log("Deleting volume '%s'", volume.id)
        self._connection.block_store.volumes.delete(volume.id)
        try:
            return self.find_volume(volume.id)
        except errors.ObjectNotFoundError:
            return None

    @convert_exceptions
    def attach_volume(self, volume, machine):
        """
        See :py:meth:`.base.ScopedSession.attach_volume`.
        """
        volume = volume if isinstance(volume, dto.Volume) else self.find_volume(volume)
        machine = machine.id if isinstance(machine, dto.Machine) else machine
        # If the volume is already attached to the machine there is nothing to do
        if volume.machine_id == machine:
            return volume
        # The volume must be available before attaching
        if volume.status != dto.VolumeStatus.AVAILABLE:
            raise errors.InvalidOperationError(
                "Volume must be AVAILABLE before attaching."
            )
        self._log("Attaching volume '%s' to server '%s'", volume.id, machine)
        server = self._connection.compute.servers.get(machine)
        server.volume_attachments.create(volume_id = volume.id)
        # Refresh the volume in the cache
        self._connection.block_store.volumes.get(volume.id, force = True)
        return self.find_volume(volume.id)

    @convert_exceptions
    def detach_volume(self, volume):
        """
        See :py:meth:`.base.ScopedSession.detach_volume`.
        """
        volume = volume if isinstance(volume, dto.Volume) else self.find_volume(volume)
        # If the volume is already detached, we are done
        if not volume.machine_id:
            return volume
        self._log("Detaching volume '%s' from '%s'", volume.id, volume.machine_id)
        server = self._connection.compute.servers.get(volume.machine_id)
        server.volume_attachments.find_by_volume_id(volume.id, as_params = False)._delete()
        # Refresh the volume in the cache
        self._connection.block_store.volumes.get(volume.id, force = True)
        return self.find_volume(volume.id)

    @convert_exceptions
    def cloud_credential(self, name, description):
        """
        See :py:meth:`.base.ScopedSession.cloud_credential`.
        """
        # Create an app cred and return a clouds.yaml for it
        # If an app cred already exists with the same name, delete it
        user = self._connection.identity.current_user
        app_cred_roles = [
            {"name": role["name"]}
            for role in self._connection.roles
            if role["name"] != "admin"
        ]
        app_cred = user.application_credentials.create(
            name = name,
            description = description,
            roles = app_cred_roles,
            # TODO(mkjpryor)
            # This is currently required to allow app creds to delete themselves
            # However it also allows the app cred to make and delete other app creds
            # which is much more power than we would ideally like the app cred to have
            # We need to look at allowing restricted app creds to delete only themselves,
            # either via policy or code changes depending on what is possible
            unrestricted = True
        )
        # Create the data for the credential object
        data = {
            "clouds.yaml": yaml.safe_dump(
                {
                    "clouds": {
                        "openstack": {
                            "identity_api_version": 3,
                            "interface": "public",
                            "auth_type": "v3applicationcredential",
                            "auth": {
                                "auth_url": self._connection.endpoints["identity"],
                                "application_credential_id": app_cred.id,
                                "application_credential_secret": app_cred.secret,
                            },
                            "verify": self._connection.verify,
                        }
                    }
                }
            ),
            "user_info.yaml": yaml.safe_dump(
                {
                    "project_id": self._connection.project_id,
                    "project_name": self._connection.project_name,
                    "username": self._connection.username,
                    "user_id": self._connection.user_id,
                }
            ),
        }
        # Decide if we need to add any CA certs to the data
        if self._connection.verify:
            # Use the cert file set by azimuth-entrypoint, which may contain custom certs
            # If the envvar is not set, just use the certs provided by certifi
            cacert_path = os.environ.get("SSL_CERT_FILE", certifi.where())
            with open(cacert_path, "r") as cacert_fh:
                data["cacert"] = cacert_fh.read()
        return dto.Credential("openstack_application_credential", data)

    def cluster_parameters(self):
        """
        See :py:meth:`.base.ScopedSession.cluster_parameters`.
        """
        # Inject information about the networks to use
        external_network = self._external_network().name
        params = dict(
            # Legacy name
            cluster_floating_network = external_network,
            # New name
            cluster_external_network = external_network,
            cluster_network = self._tenant_network(True).name
        )

        # Inject storage direct network, if exists
        storage_network = self._storage_network()
        if storage_network:
            params['cluster_storage_network'] = storage_network.name

        # If configured to, find if we can have a project share
        project_share = self._project_share(True)
        if project_share:
            params["cluster_project_manila_share"] = True
            params["cluster_project_manila_share_name"] = project_share.name
            user = self._project_share_user
            params["cluster_project_manila_share_user"] = user
        else:
            params["cluster_project_manila_share"] = False

        return params

    def cluster_modify(self, cluster):
        """
        See :py:meth:`.base.ScopedSession.cluster_modify`.
        """
        # Remove injected parameters from the cluster params
        params = {
            k: v
            for k, v in cluster.parameter_values.items()
            if k not in {"cluster_floating_network", "cluster_network"}
        }
        original_error = (cluster.error_message or "").lower()
        # Convert quota-related error messages based on known OpenStack errors
        if any(m in original_error for m in {"quota exceeded", "exceedsavailablequota"}):
            if "floatingip" in original_error:
                error_message = (
                    "Could not find an external IP for deployment. "
                    "Please ensure an external IP is available and try again."
                )
            else:
                error_message = (
                    "Requested resources exceed at least one quota. "
                    "Please check your tenancy quotas and try again."
                )
        elif cluster.error_message:
            error_message = _replace_resource_names(cluster.error_message)
        else:
            error_message = None
        return dataclasses.replace(
            cluster,
            parameter_values = params,
            error_message = error_message
        )

    @convert_exceptions
    def close(self):
        """
        See :py:meth:`.base.ScopedSession.close`.
        """
        # Make sure the underlying api connection is closed
        self._connection.close()
