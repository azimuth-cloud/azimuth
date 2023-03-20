"""
This module contains the provider implementation for OpenStack.
"""

import base64
import dataclasses
import functools
import hashlib
import itertools
import logging
import random
import re

import dateutil.parser

import rackit

from ...cluster_engine.dto import Credential

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
        internal_net_cidr: The CIDR for the internal network when it is
                           auto-created (default ``192.168.3.0/24``).
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
                       internal_net_cidr = "192.168.3.0/24",
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
        self._internal_net_cidr = internal_net_cidr
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
                internal_net_cidr = self._internal_net_cidr,
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
                       internal_net_cidr = "192.168.3.0/24",
                       az_backdoor_net_map = None,
                       backdoor_vnic_type = None):
        self._connection = connection
        self._metadata_prefix = metadata_prefix
        self._internal_net_template = internal_net_template
        self._external_net_template = external_net_template
        self._create_internal_net = create_internal_net
        self._internal_net_cidr = internal_net_cidr
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
        # Return a fake email address consisting of the username and domain
        return f"{self._connection.username}@{self._connection.domain_name.lower()}"

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
                internal_net_cidr = self._internal_net_cidr,
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
                       internal_net_cidr = "192.168.3.0/24",
                       az_backdoor_net_map = None,
                       backdoor_vnic_type = None):
        self._username = username
        self._tenancy = tenancy
        self._connection = connection
        self._metadata_prefix = metadata_prefix
        self._internal_net_template = internal_net_template
        self._external_net_template = external_net_template
        self._create_internal_net = create_internal_net
        self._internal_net_cidr = internal_net_cidr
        self._az_backdoor_net_map = az_backdoor_net_map or dict()
        self._backdoor_vnic_type = backdoor_vnic_type

    def _log(self, message, *args, level = logging.INFO, **kwargs):
        logger.log(
            level,
            "[%s] [%s] " + message,
            self._username, self._tenancy.name, *args, **kwargs
        )

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
                None,
                compute_limits.total_cores,
                compute_limits.total_cores_used
            ),
            dto.Quota(
                "ram",
                "MB",
                compute_limits.total_ram,
                compute_limits.total_ram_used
            ),
            dto.Quota(
                "machines",
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
                    "GB",
                    volume_limits.total_volume_gigabytes,
                    volume_limits.total_gigabytes_used
                ),
                dto.Quota(
                    "volumes",
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
            getattr(api_flavor, "ephemeral_disk", 0)
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
        # Only consider networks that belong to the project unless specifically told otherwise
        networks = self._connection.network.networks.all(tags = tag)
        if net_type == "external":
            networks = itertools.chain(
                networks,
                self._connection.network.networks.all(tags = tag, project_id = None)
            )
        network = next(networks, None)
        if network:
            self._log("Using tagged %s network '%s'", net_type, network.name)
        else:
            self._log("Failed to find tagged %s network.", net_type, level = logging.WARN)
        return network

    def _templated_network(self, template, net_type):
        """
        Returns the network specified by the template, after interpolating with the tenant name.

        If the network does not exist, that is a config error and an exception is raised.
        """
        net_name = template.format(tenant_name = self._tenancy.name)
        # Only consider networks that belong to the project unless specifically told otherwise
        networks = self._connection.network.networks.all(name = net_name)
        if net_type == "external":
            networks = itertools.chain(
                networks,
                self._connection.network.networks.all(name = net_name, project_id = None)
            )
        network = next(networks, None)
        if network:
            self._log("Found %s network '%s' using template.", net_type, network.name)
            return network
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
            subnet = self._connection.network.subnets.create(
                name = "portal-internal",
                network_id = network.id,
                ip_version = 4,
                cidr = self._internal_net_cidr
            )
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

    def _from_api_server(self, api_server, get_tenant_network):
        """
        Returns a machine DTO for the given API server representation.

        The additional arguments are the tenant network and an optional iterable of
        the images for the tenancy (used to save fetching each image individually
        when listing machines).
        """
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
            getattr(api_server.image, "id", None),
            getattr(api_server.flavor, "id", None),
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
        # Note that this will (a) only load the network if required and (b)
        # reuse the network once loaded
        get_tenant_network = Lazy(self._tenant_network)
        return tuple(self._from_api_server(s, get_tenant_network) for s in api_servers)

    @convert_exceptions
    def find_machine(self, id):
        """
        See :py:meth:`.base.ScopedSession.find_machine`.
        """
        self._log("Fetching server with id '%s'", id)
        server = self._connection.compute.servers.get(id)
        # Don't discover the tenant network unless the server is found
        get_tenant_network = Lazy(self._tenant_network)
        return self._from_api_server(server, get_tenant_network)

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
            machine_id = port.device_id
        else:
            machine_id = None
        return dto.ExternalIp(
            api_floatingip.id,
            api_floatingip.floating_ip_address,
            machine_id
        )

    @convert_exceptions
    def external_ips(self):
        """
        See :py:meth:`.base.ScopedSession.external_ips`.
        """
        self._log("Fetching floating ips")
        fips = list(self._connection.network.floatingips.all())
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
        return self._from_api_floatingip(fip)

    @convert_exceptions
    def attach_external_ip(self, ip, machine):
        """
        See :py:meth:`.base.ScopedSession.attach_external_ip`.
        """
        machine = machine.id if isinstance(machine, dto.Machine) else machine
        ip = ip.id if isinstance(ip, dto.ExternalIp) else ip
        self._log("Attaching floating ip '%s' to server '%s'", ip, machine)
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
        fip = self._connection.network.floatingips.get(ip)
        return self._from_api_floatingip(fip._update(port_id = port.id))

    @convert_exceptions
    def detach_external_ip(self, ip):
        """
        See :py:meth:`.base.ScopedSession.detach_external_ip`.
        """
        ip = ip.id if isinstance(ip, dto.ExternalIp) else ip
        self._log("Detaching floating ip '%s'", ip)
        # Find the floating IP instance for the given address
        fip = self._connection.network.floatingips.get(ip)
        # Remove any association for the floating IP
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

    def cluster_credential(self):
        """
        See :py:meth:`.base.ScopedSession.cluster_credential`.
        """
        # Return a credential that uses the current token to interact with OpenStack
        return Credential(
            type = "openstack_token",
            data = dict(
                auth_url = self._connection.auth_url,
                project_id = self._connection.project_id,
                token = self._connection.token,
                verify_ssl = self._connection.verify
            )
        )

    def cluster_parameters(self):
        """
        See :py:meth:`.base.ScopedSession.cluster_parameters`.
        """
        # Inject information about the networks to use
        return dict(
            cluster_floating_network = self._external_network().name,
            cluster_network = self._tenant_network(True).name
        )

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
        # Add any tags attached to the stack
        try:
            stack = self._connection.orchestration.stacks.find_by_stack_name(cluster.name)
        except (api.ServiceNotSupported, rackit.NotFound):
            tags = cluster.tags
        else:
            tags = list(cluster.tags)
            if stack:
                tags.extend(stack.tags or [])
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
            tags = tags,
            error_message = error_message
        )

    @convert_exceptions
    def close(self):
        """
        See :py:meth:`.base.ScopedSession.close`.
        """
        # Make sure the underlying api connection is closed
        self._connection.close()
