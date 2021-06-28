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

from .. import base, errors, dto
from ..cluster_engine.base import Credential

from . import api


logger = logging.getLogger(__name__)


_REPLACEMENTS = [
    ('instance', 'machine'),
    ('Instance', 'Machine'),
    ('flavorRef', 'size'),
    ('flavor', 'size'),
    ('Flavor', 'Size')
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
    return re.sub('[^a-zA-Z0-9]+', '-', username)


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
                raise errors.AuthenticationError('Your session has expired.')
            elif status_code == 403:
                # Some quota exceeded errors get reported as permission denied (WHY???!!!)
                # So report them as quota exceeded instead
                if 'exceeded' in message.lower():
                    raise errors.QuotaExceededError(
                        'Requested operation would exceed at least one quota. '
                        'Please check your tenancy quotas.'
                    )
                raise errors.PermissionDeniedError('Permission denied.')
            elif status_code == 404:
                raise errors.ObjectNotFoundError(message)
            elif status_code == 409:
                # 409 (Conflict) has a lot of different sub-errors depending on
                # the actual error text
                if 'exceeded' in message.lower():
                    raise errors.QuotaExceededError(
                        'Requested operation would exceed at least one quota. '
                        'Please check your tenancy quotas.'
                    )
                raise errors.InvalidOperationError(message)
            elif status_code == 413:
                # The volume service uses 413 (Payload too large) for quota errors
                if 'exceedsavailablequota' in message.lower():
                    raise errors.QuotaExceededError(
                        'Requested operation would exceed at least one quota. '
                        'Please check your tenancy quotas.'
                    )
                raise errors.CommunicationError('Unknown error with OpenStack API.')
            else:
                raise errors.CommunicationError('Unknown error with OpenStack API.')
        except rackit.RackitError as exc:
            logger.exception('Could not connect to OpenStack API.')
            raise errors.CommunicationError('Could not connect to OpenStack API.')
    return wrapper


class LazyRewindableGenerator:
    """
    Class for a lazily-initialised, rewindable generator.
    """
    def __init__(self, generator, *args, **kwargs):
        def internal_generator():
            yield from generator(*args, **kwargs)
        self._generator = internal_generator
        self._iterator = None

    def __iter__(self):
        if not self._iterator:
            self._iterator = self._generator()
        self._iterator, result = itertools.tee(self._iterator)
        return result


class Provider(base.Provider):
    """
    Provider implementation for OpenStack.

    Args:
        auth_url: The Keystone v3 authentication URL.
        domain: The domain to authenticate with (default ``Default``).
        interface: The OpenStack interface to connect using (default ``public``).
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
        cluster_app_cred_name: The name to use for the application credential that is given
                               to the cluster engine for creating OpenStack resources.
        cluster_engine: The :py:class:`~..cluster.base.Engine` to use for clusters.
                        If not given, clusters are disabled.
    """
    provider_name = 'openstack'

    def __init__(self, auth_url,
                       domain = 'Default',
                       interface = 'public',
                       internal_net_cidr = '192.168.3.0/24',
                       az_backdoor_net_map = dict(),
                       backdoor_vnic_type = None,
                       verify_ssl = True,
                       cluster_app_cred_name = "caas-awx",
                       cluster_engine = None):
        # Strip any trailing slashes from the auth URL
        self._auth_url = auth_url.rstrip('/')
        self._domain = domain
        self._interface = interface
        self._internal_net_cidr = internal_net_cidr
        self._az_backdoor_net_map = az_backdoor_net_map or dict()
        self._backdoor_vnic_type = backdoor_vnic_type
        self._verify_ssl = verify_ssl
        self._cluster_app_cred_name = cluster_app_cred_name
        self._cluster_engine = cluster_engine

    @convert_exceptions
    def authenticate(self, username, password):
        """
        See :py:meth:`.base.Provider.authenticate`.
        """
        logger.info("Authenticating user '%s' with OpenStack", username)
        # Create an API connection using the username and password
        auth_params = api.AuthParams().use_password(self._domain, username, password)
        try:
            conn = api.Connection(self._auth_url, auth_params, self._interface, self._verify_ssl)
        except rackit.Unauthorized:
            logger.info("Authentication failed for user '%s'", username)
            # We want to use a different error message to convert_exceptions
            raise errors.AuthenticationError('Invalid username or password.')
        else:
            logger.info("Sucessfully authenticated user '%s'", username)
            return UnscopedSession(
                conn,
                internal_net_cidr = self._internal_net_cidr,
                az_backdoor_net_map = self._az_backdoor_net_map,
                backdoor_vnic_type = self._backdoor_vnic_type,
                cluster_app_cred_name = self._cluster_app_cred_name,
                cluster_engine = self._cluster_engine
            )

    @convert_exceptions
    def from_token(self, token):
        """
        See :py:meth:`.base.Provider.from_token`.
        """
        logger.info('Authenticating token with OpenStack')
        auth_params = api.AuthParams().use_token(token)
        try:
            conn = api.Connection(self._auth_url, auth_params, self._interface, self._verify_ssl)
        except (rackit.Unauthorized, rackit.NotFound):
            logger.info("Authentication failed for token")
            # Failing to validate a token is a 404 for some reason
            raise errors.AuthenticationError('Your session has expired.')
        else:
            logger.info("Sucessfully authenticated user '%s'", conn.username)
            return UnscopedSession(
                conn,
                internal_net_cidr = self._internal_net_cidr,
                az_backdoor_net_map = self._az_backdoor_net_map,
                backdoor_vnic_type = self._backdoor_vnic_type,
                cluster_app_cred_name = self._cluster_app_cred_name,
                cluster_engine = self._cluster_engine
            )


class UnscopedSession(base.UnscopedSession):
    """
    Unscoped session implementation for OpenStack.
    """
    provider_name = 'openstack'

    def __init__(self, connection,
                       internal_net_cidr = '192.168.3.0/24',
                       az_backdoor_net_map = None,
                       backdoor_vnic_type = None,
                       cluster_app_cred_name = "caas-awx",
                       cluster_engine = None):
        self._connection = connection
        self._internal_net_cidr = internal_net_cidr
        self._az_backdoor_net_map = az_backdoor_net_map or dict()
        self._backdoor_vnic_type = backdoor_vnic_type
        self._cluster_app_cred_name = cluster_app_cred_name
        self._cluster_engine = cluster_engine

    def token(self):
        """
        See :py:meth:`.base.UnscopedSession.token`.
        """
        return self._connection.token

    def username(self):
        """
        See :py:meth:`.base.UnscopedSession.username`.
        """
        return self._connection.username

    def _log(self, message, *args, level = logging.INFO, **kwargs):
        logger.log(level, '[%s] ' + message, self.username(), *args, **kwargs)

    def _scoped_connection_for_first_project(self):
        """
        Returns a scoped connection for the user's first project.
        """
        try:
            project = next(self._connection.projects.all())
        except StopIteration:
            raise errors.InvalidOperationError("User does not belong to any projects.")
        return self._connection.scoped_connection(project)

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
        self._log('Fetching available tenancies')
        projects = tuple(self._connection.projects.all())
        self._log('Found %s projects', len(projects))
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
                    'Could not find tenancy with ID {}.'.format(tenancy)
                )
        self._log("Creating scoped session for project '%s'", tenancy.name)
        try:
            return ScopedSession(
                self.username(),
                tenancy,
                self._connection.scoped_connection(tenancy.id),
                internal_net_cidr = self._internal_net_cidr,
                az_backdoor_net_map = self._az_backdoor_net_map,
                backdoor_vnic_type = self._backdoor_vnic_type,
                cluster_app_cred_name = self._cluster_app_cred_name,
                cluster_engine = self._cluster_engine
            )
        except (rackit.Unauthorized, rackit.Forbidden):
            raise errors.ObjectNotFoundError(
                'Could not find tenancy with ID {}.'.format(tenancy.id)
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
    provider_name = 'openstack'

    def __init__(self, username,
                       tenancy,
                       connection,
                       internal_net_cidr = '192.168.3.0/24',
                       az_backdoor_net_map = None,
                       backdoor_vnic_type = None,
                       cluster_app_cred_name = "caas-awx",
                       cluster_engine = None):
        self._username = username
        self._tenancy = tenancy
        self._connection = connection
        self._internal_net_cidr = internal_net_cidr
        self._az_backdoor_net_map = az_backdoor_net_map or dict()
        self._backdoor_vnic_type = backdoor_vnic_type
        self._cluster_app_cred_name = cluster_app_cred_name
        self._cluster_engine = cluster_engine

    def _log(self, message, *args, level = logging.INFO, **kwargs):
        logger.log(
            level,
            '[%s] [%s] ' + message,
            self._username, self._tenancy.name, *args, **kwargs
        )

    @convert_exceptions
    def quotas(self):
        """
        See :py:meth:`.base.ScopedSession.quotas`.
        """
        self._log('Fetching tenancy quotas')
        # Compute provides a way to fetch this information through the SDK, but
        # the floating IP quota obtained through it is rubbish...
        compute_limits = self._connection.compute.limits.absolute
        quotas = [
            dto.Quota(
                'cpus',
                None,
                compute_limits.total_cores,
                compute_limits.total_cores_used
            ),
            dto.Quota(
                'ram',
                'MB',
                compute_limits.total_ram,
                compute_limits.total_ram_used
            ),
            dto.Quota(
                'machines',
                None,
                compute_limits.instances,
                compute_limits.instances_used
            ),
        ]
        # Get the floating ip quota
        network_quotas = self._connection.network.quotas
        quotas.append(
            dto.Quota(
                'external_ips',
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
                    'storage',
                    'GB',
                    volume_limits.total_volume_gigabytes,
                    volume_limits.total_gigabytes_used
                ),
                dto.Quota(
                    'volumes',
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
        return dto.Image(
            api_image.id,
            getattr(api_image, 'jasmin_type', 'UNKNOWN'),
            api_image.name,
            api_image.visibility == 'public',
            # Unless specifically disallowed by a flag, NAT is allowed
            bool(int(getattr(api_image, 'jasmin_nat_allowed', '1'))),
            # The image size is specified in bytes. Convert to MB.
            float(api_image.size) / 1024.0 / 1024.0
        )

    @convert_exceptions
    def images(self):
        """
        See :py:meth:`.base.ScopedSession.images`.
        """
        self._log('Fetching available images')
        # Fetch from the SDK using our custom image resource
        # Exclude cluster images from the returned list
        images = list(
            image
            for image in self._connection.image.images.all(status = 'active')
            if not int(getattr(image, 'jasmin_cluster_image', '0'))
        )
        self._log('Found %s images', len(images))
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
            api_flavor.vcpus,
            api_flavor.ram,
            api_flavor.disk
        )

    @convert_exceptions
    def sizes(self):
        """
        See :py:meth:`.base.ScopedSession.sizes`.
        """
        self._log('Fetching available flavors')
        flavors = tuple(
            self._from_api_flavor(flavor)
            for flavor in self._connection.compute.flavors.all()
            if not flavor.is_disabled
        )
        self._log('Found %s flavors', len(flavors))
        return flavors

    @convert_exceptions
    def find_size(self, id):
        """
        See :py:meth:`.base.ScopedSession.find_size`.
        """
        self._log("Fetching flavor with id '%s'", id)
        return self._from_api_flavor(self._connection.compute.flavors.get(id))

    def _tagged_network(self, tag):
        """
        Returns the first network with the given tag, or None if there is not one.
        """
        return next(self._connection.network.networks.all(tags = tag), None)

    def _tenant_network(self, create_network = False):
        """
        Returns the network connected to the tenant router.
        Assumes a single router with a single tenant network connected.
        If create_network = True, a network will be created if one cannot be found.
        """
        # First, try to find a network that is tagged as the portal internal network
        tagged_network = self._tagged_network('portal-internal')
        if tagged_network:
            self._log("Using tagged internal network '%s'", tagged_network.name)
            return tagged_network
        else:
            self._log("Failed to find tagged internal network.")
        # If there are no networks with that tag, try to find the network using the tenancy router
        # Find the port that connects the tenancy network to a router
        port = self._connection.network.ports.find_by_device_owner('network:router_interface')
        if port:
            # Get the network that is attached to that port
            network = self._connection.network.networks.get(port.network_id)
            self._log("Found internal network '%s' via router.", network.name)
            return network
        else:
            self._log("Failed to find internal network via router.")
        # If we get this far, we either create and return a network or return None
        if create_network:
            # Unfortunately, the tags cannot be set in the POST request
            self._log("Creating internal network")
            network = self._connection.network.networks.create(name = "portal-internal")
            network._update_tags(["portal-internal"])
            # Create a subnet for the network
            self._log("Creating subnet for network '%s'", network.name)
            self._connection.network.subnets.create(
                network_id = network.id,
                ip_version = 4,
                cidr = self._internal_net_cidr
            )
            return network

    def _external_network(self):
        """
        Returns the external network that connects the tenant router to the outside world.
        """
        # First, try to find a network that is tagged as the portal external network
        tagged_network = self._tagged_network('portal-external')
        if tagged_network:
            self._log("Using tagged external network '%s'", tagged_network.name)
            return tagged_network
        else:
            self._log("Failed to find tagged external network.")
        # Otherwise find the external gateway for the tenancy router
        router = next(self._connection.network.routers.all(), None)
        if router and router.external_gateway_info:
            external_network_id = router.external_gateway_info['network_id']
            network = self._connection.network.networks.get(external_network_id)
            self._log("Found external network '%s' via router", network.name)
            return network
        else:
            self._log("Failed to find external network")
            raise errors.InvalidOperationError('Could not find external network.')

    def _get_or_create_keypair(self, ssh_key):
        """
        Returns a Nova keypair for the given SSH key.
        """
        # Keypairs are immutable, i.e. once created cannot be changed
        # We create keys with names of the form "<username>-<truncated fingerprint>",
        # which allows for us to recognise when a user has changed their key and create
        # a new one
        fingerprint = hashlib.md5(base64.b64decode(ssh_key.split()[1])).hexdigest()
        key_name = '{username}-{fingerprint}'.format(
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
        0: 'Unknown',
        1: 'Running',
        3: 'Paused',
        4: 'Shut down',
        6: 'Crashed',
        7: 'Suspended',
    }

    def _from_api_server(self, api_server, tenant_network, images = None):
        """
        Returns a machine DTO for the given API server representation.

        The additional arguments are the tenant network and an optional iterable of
        the images for the tenancy (used to save fetching each image individually
        when listing machines).
        """
        # Try to get nat_allowed from the machine metadata
        # If the nat_allowed metadata is not present, use the image
        # If the image does not exist anymore, assume it is allowed
        try:
            nat_allowed = bool(int(api_server.metadata['jasmin_nat_allowed']))
        except (KeyError, TypeError):
            if images:
                image = next((i for i in images if i.id == api_server.image['id']), None)
            else:
                try:
                    image = self._connection.image.images.get(api_server.image['id'])
                except errors.ObjectNotFoundError:
                    image = None
            nat_allowed = bool(int(getattr(image, 'jasmin_nat_allowed', '1')))
        status = api_server.status
        fault = api_server.fault.get('message', None)
        task = api_server.task_state
        # Function to get the first IP of a particular type on the tenant network
        def ip_of_type(ip_type):
            return next(
                (
                    a['addr']
                    for a in api_server.addresses.get(tenant_network.name, [])
                    if a['version'] == 4 and a['OS-EXT-IPS:type'] == ip_type
                ),
                None
            )
        return dto.Machine(
            api_server.id,
            api_server.name,
            api_server.image['id'],
            api_server.flavor['id'],
            dto.MachineStatus(
                getattr(dto.MachineStatusType, status, dto.MachineStatusType.OTHER),
                status,
                _replace_resource_names(fault) if fault else None
            ),
            self._POWER_STATES[api_server.power_state],
            task.capitalize() if task else None,
            ip_of_type('fixed') if tenant_network else None,
            ip_of_type('floating') if tenant_network else None,
            nat_allowed,
            tuple(v['id'] for v in api_server.attached_volumes),
            api_server.user_id,
            dateutil.parser.parse(api_server.created)
        )

    @convert_exceptions
    def machines(self):
        """
        See :py:meth:`.base.ScopedSession.machines`.
        """
        self._log('Fetching available servers')
        api_servers = tuple(self._connection.compute.servers.all())
        self._log('Found %s servers', len(api_servers))
        # If no servers loaded, we don't need to discover the tenant network
        # We also include a generator of images, so that they are only loaded once
        if api_servers:
            # Load the tenant network once and reuse it
            tenant_network = self._tenant_network()
            # Pass the images in a way that they are only loaded the first
            # time that they are iterated over
            images = LazyRewindableGenerator(self._connection.image.images.all)
        else:
            tenant_network = None
            images = []
        return tuple(self._from_api_server(s, tenant_network, images) for s in api_servers)

    @convert_exceptions
    def find_machine(self, id):
        """
        See :py:meth:`.base.ScopedSession.find_machine`.
        """
        self._log("Fetching server with id '%s'", id)
        server = self._connection.compute.servers.get(id)
        # Don't discover the tenant network unless the server is found
        tenant_network = self._tenant_network()
        return self._from_api_server(server, tenant_network)

    @convert_exceptions
    def create_machine(self, name, image, size, ssh_key = None):
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
                raise errors.BadInputError('Invalid image provided.')
        params.update(image_id = str(image.id))
        # To find the metadata elements, we need the raw API image
        # This will load from the cache
        api_image = self._connection.image.images.get(image.id)
        size = size.id if isinstance(size, dto.Size) else size
        params.update(flavor_id = size)
        self._log("Creating machine '%s' (image: %s, size: %s)", name, api_image.name, size)
        # Get the networks to use
        # Always use the tenant network that is attached to the router
        params.update(networks = [{ 'uuid': self._tenant_network(True).id }])
        # If the image asks for the backdoor network, attach it
        if getattr(api_image, 'jasmin_private_if', None):
            if not self._az_backdoor_net_map:
                raise errors.ImproperlyConfiguredError(
                    'Backdoor network required by image but not configured.'
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
                port_params['binding:vnic_type'] = self._backdoor_vnic_type
            port = self._connection.network.ports.create(port_params)
            params['networks'].append({ 'port': port.id })
        # Get the keypair to inject
        if ssh_key:
            keypair = self._get_or_create_keypair(ssh_key)
            params.update(key_name = keypair.name)
        # Pass metadata onto the machine from the image if present
        metadata = dict(jasmin_organisation = self._tenancy.name)
        metadata.update({
            item : getattr(api_image, item)
            for item in {
                'jasmin_nat_allowed',
                'jasmin_type',
                'jasmin_private_if',
                'jasmin_activ_ver'
            }
            if getattr(api_image, item, None) is not None
        })
        params.update(metadata = metadata)
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
        self._connection.compute.servers.get(machine).reboot('SOFT')
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
        try:
            return self.find_machine(machine)
        except errors.ObjectNotFoundError:
            return None

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
        machine = machine if isinstance(machine, dto.Machine) else self.find_machine(machine)
        ip = ip.id if isinstance(ip, dto.ExternalIp) else ip
        # If NATing is not allowed for the machine, bail
        if not machine.nat_allowed:
            raise errors.InvalidOperationError(
                'Machine is not allowed to have an external IP address.'
            )
        self._log("Attaching floating ip '%s' to server '%s'", ip, machine.id)
        # Get the port that attaches the machine to the tenant network
        tenant_network = self._tenant_network()
        if tenant_network:
            port = next(
                self._connection.network.ports.all(
                    device_id = machine.id,
                    network_id = tenant_network.id
                ),
                None
            )
        else:
            port = None
        if not port:
            raise errors.ImproperlyConfiguredError(
                'Machine is not connected to tenancy network.'
            )
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
        'creating': dto.VolumeStatus.CREATING,
        'available': dto.VolumeStatus.AVAILABLE,
        'reserved': dto.VolumeStatus.ATTACHING,
        'attaching': dto.VolumeStatus.ATTACHING,
        'detaching': dto.VolumeStatus.DETACHING,
        'in-use': dto.VolumeStatus.IN_USE,
        'deleting': dto.VolumeStatus.DELETING,
        'error': dto.VolumeStatus.ERROR,
        'error_deleting': dto.VolumeStatus.ERROR,
        'error_backing-up': dto.VolumeStatus.ERROR,
        'error_restoring': dto.VolumeStatus.ERROR,
        'error_extending': dto.VolumeStatus.ERROR,
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
            attachment['server_id'] if attachment else None,
            attachment['device'] if attachment else None
        )

    @convert_exceptions
    def volumes(self):
        """
        See :py:meth:`.base.ScopedSession.volumes`.
        """
        self._log('Fetching available volumes')
        volumes = tuple(
            self._from_api_volume(v)
            for v in self._connection.block_store.volumes.all()
        )
        self._log('Found %s volumes', len(volumes))
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

    def _from_api_coe_cluster_template(self, template):
        """
        Converts a COE cluster template into a :py:class:`.dto.KubernetesClusterTemplate`.
        """
        return dto.KubernetesClusterTemplate(
            template.uuid,
            template.name,
            template.labels.get('kube_tag', 'default'),
            template.master_lb_enabled,
            template.public,
            template.hidden,
            dateutil.parser.parse(template.created_at),
            dateutil.parser.parse(template.updated_at) if template.updated_at else None
        )

    @convert_exceptions
    def kubernetes_cluster_templates(self):
        """
        See :py:meth:`.base.ScopedSession.kubernetes_cluster_templates`.
        """
        self._log('Fetching available COE cluster templates')
        templates = list(self._connection.coe.cluster_templates.all())
        self._log('Found %s COE cluster templates', len(templates))
        # Return only the templates that have Kubernetes as a COE and are not hidden
        return tuple(
            self._from_api_coe_cluster_template(template)
            for template in templates
            if template.coe == "kubernetes" and not template.hidden
        )

    @convert_exceptions
    def find_kubernetes_cluster_template(self, id):
        """
        See :py:meth:`.base.ScopedSession.find_kubernetes_cluster_template`.
        """
        self._log("Fetching COE cluster template with id '%s'", id)
        template = self._connection.coe.cluster_templates.get(id)
        # Check that the COE is Kubernetes and bail if not
        if template.coe != "kubernetes":
            raise errors.ObjectNotFoundError('ClusterTemplate {} could not be found.'.format(id))
        return self._from_api_coe_cluster_template(template)

    def _from_api_coe_cluster(self, cluster):
        """
        Converts a COE cluster into a :py:class:`.dto.KubernetesCluster`.
        """
        return dto.KubernetesCluster(
            cluster.uuid,
            cluster.name,
            cluster.cluster_template_id,
            cluster.coe_version,
            dto.KubernetesClusterStatus(cluster.status),
            cluster.status_reason or None,
            dto.KubernetesClusterHealthStatus(cluster.health_status)
                if getattr(cluster, 'health_status', None)
                else None,
            cluster.health_status_reason,
            cluster.api_address,
            cluster.master_count,
            cluster.node_count,
            cluster.master_flavor_id,
            cluster.flavor_id,
            cluster.labels.get("auto_scaling_enabled", "False") == "True",
            cluster.labels.get("min_node_count"),
            cluster.labels.get("max_node_count"),
            cluster.labels.get("auto_healing_enabled", "False") == "True",
            cluster.labels.get("monitoring_enabled", "False") == "True",
            cluster.labels.get("grafana_admin_password"),
            dateutil.parser.parse(cluster.created_at),
            dateutil.parser.parse(cluster.updated_at) if cluster.updated_at else None
        )

    @convert_exceptions
    def kubernetes_clusters(self):
        """
        See :py:meth:`.base.ScopedSession.kubernetes_clusters`.
        """
        self._log('Fetching available COE clusters')
        clusters = list(self._connection.coe.clusters.all())
        self._log('Found %s COE clusters', len(clusters))
        # If we didn't find any clusters, we are done
        if not clusters:
            return clusters
        # Load the cluster templates and index them by ID so that we can check the COE
        # This means fewer requests than fetching each cluster template as needed
        template_coes = {
            template.uuid: template.coe
            for template in self._connection.coe.cluster_templates.all()
        }
        # Return only the clusters that have Kubernetes as a COE
        return tuple(
            self._from_api_coe_cluster(cluster)
            for cluster in clusters
            if template_coes[cluster.cluster_template_id] == "kubernetes"
        )

    @convert_exceptions
    def find_kubernetes_cluster(self, id):
        """
        See :py:meth:`.base.ScopedSession.find_kubernetes_cluster`.
        """
        self._log("Fetching COE cluster with id '%s'", id)
        cluster = self._connection.coe.clusters.get(id)
        # Check that the COE is Kubernetes and bail if not
        if cluster.cluster_template.coe != "kubernetes":
            raise errors.ObjectNotFoundError('Cluster {} could not be found.'.format(id))
        return self._from_api_coe_cluster(cluster)

    @convert_exceptions
    def create_kubernetes_cluster(
        self,
        name,
        template_id,
        master_size_id,
        worker_size_id,
        worker_count = None,
        min_worker_count = None,
        max_worker_count = None,
        auto_healing_enabled = False,
        auto_scaling_enabled = False,
        monitoring_enabled = False,
        grafana_admin_password = None,
        ssh_key = None
    ):
        """
        See :py:meth:`.base.ScopedSession.create_kubernetes_cluster`.
        """
        self._log("Creating Kubernetes cluster '%s'", name)
        params = dict(
            name = name,
            cluster_template_id = template_id,
            master_flavor_id = master_size_id,
            flavor_id = worker_size_id,
            # If auto-scaling is enabled, min/max worker count will be set
            # If not, then worker count will be set
            # Use the worker count or the minimum worker count, depending which is set
            node_count = worker_count or min_worker_count,
            labels = dict(
                auto_healing_enabled = auto_healing_enabled,
                auto_scaling_enabled = auto_scaling_enabled,
                monitoring_enabled = monitoring_enabled
            )
        )
        if auto_scaling_enabled:
            params['labels'].update(
                min_node_count = min_worker_count,
                max_node_count = max_worker_count
            )
        if monitoring_enabled:
            params['labels'].update(grafana_admin_password = grafana_admin_password)
        if ssh_key:
            keypair = self._get_or_create_keypair(ssh_key)
            params.update(keypair = keypair.name)
        cluster = self._connection.coe.clusters.create(**params)
        return self._from_api_coe_cluster(cluster)

    @convert_exceptions
    def update_kubernetes_cluster(self, cluster, template):
        """
        See :py:meth:`.base.ScopedSession.update_kubernetes_cluster`.
        """
        return super().update_kubernetes_cluster(cluster, template)

    @convert_exceptions
    def delete_kubernetes_cluster(self, cluster):
        """
        See :py:meth:`.base.ScopedSession.delete_kubernetes_cluster`.
        """
        cluster = cluster.id if isinstance(cluster, dto.KubernetesCluster) else cluster
        self._log("Deleting Kubernetes cluster '%s'", cluster)
        self._connection.coe.clusters.delete(cluster)
        try:
            # The state doesn't change straight away, so replace it
            return dataclasses.replace(
                self.find_kubernetes_cluster(cluster),
                status = dto.KubernetesClusterStatus.DELETE_IN_PROGRESS
            )
        except errors.ObjectNotFoundError:
            return None

    @property
    def cluster_manager(self):
        """
        Returns the cluster manager for the tenancy.
        """
        # Lazily instantiate the cluster manager the first time it is asked for.
        if not hasattr(self, '_cluster_manager'):
            if self._cluster_engine:
                self._cluster_manager = self._cluster_engine.create_manager(
                    self._username,
                    self._tenancy
                )
            else:
                self._cluster_manager = None
        # If there is still no cluster manager, clusters are not supported
        if not self._cluster_manager:
            raise errors.UnsupportedOperationError(
                'Clusters are not supported for this tenancy.'
            )
        return self._cluster_manager

    @convert_exceptions
    def cluster_types(self):
        """
        See :py:meth:`.base.ScopedSession.cluster_types`.
        """
        return self.cluster_manager.cluster_types()

    @convert_exceptions
    def find_cluster_type(self, name):
        """
        See :py:meth:`.base.ScopedSession.find_cluster_type`.
        """
        return self.cluster_manager.find_cluster_type(name)

    def _fixup_cluster(self, cluster):
        """
        Fix up the cluster with any OpenStack-specific changes.
        """
        # Remove injected parameters from the cluster params
        params = {
            k: v
            for k, v in cluster.parameter_values.items()
            if k != 'cluster_network'
        }
        # Add any tags attached to the stack
        try:
            stack = self._connection.orchestration.stacks.find_by_stack_name(cluster.name)
        except rackit.NotFound:
            stack = None
        # We use this format because tags might exist on the stack but be None
        stack_tags = tuple(getattr(stack, 'tags', None) or [])
        original_error = (cluster.error_message or '').lower()
        # Convert quota-related error messages based on known OpenStack errors
        if any(m in original_error for m in {'quota exceeded', 'exceedsavailablequota'}):
            if 'floatingip' in original_error:
                error_message = (
                    'Could not find an external IP for deployment. '
                    'Please ensure an external IP is available and try again.'
                )
            else:
                error_message = (
                    'Requested resources exceed at least one quota. '
                    'Please check your tenancy quotas and try again.'
                )
        elif cluster.error_message:
            error_message = (
                'Error during cluster configuration. '
                'Please contact support.'
            )
        else:
            error_message = None
        return dataclasses.replace(
            cluster,
            parameter_values = params,
            tags = cluster.tags + stack_tags,
            error_message = error_message
        )

    @convert_exceptions
    def clusters(self):
        """
        See :py:meth:`.base.ScopedSession.clusters`.
        """
        return tuple(
            self._fixup_cluster(c)
            for c in self.cluster_manager.clusters()
        )

    @convert_exceptions
    def find_cluster(self, id):
        """
        See :py:meth:`.base.ScopedSession.find_cluster`.
        """
        return self._fixup_cluster(self.cluster_manager.find_cluster(id))

    def _cluster_credential(self):
        """
        Returns a credential to be used with the cluster engine for making OpenStack resources.

        It attempts to use application credentials if they are supported, but falls back
        to using the short-lived token if not.

        Using the token can be a bit of a pain for cluster configuration, particularly if the
        tokens have a short TTL, which is why we favour application creds if possible.
        """
        # Try to get the application credentials for the user
        # If this fails for any reason, fallback to a token
        try:
            self._log("Fetching application credentials")
            # This is a lazy object that isn't actually fetched
            user = self._connection.identity.users.get(self._connection.user_id)
            app_creds = user.application_credentials.all()
        except rackit.ApiError:
            self._log("Application credentials not supported - falling back to token")
            return Credential(
                type = "openstack_token",
                persistent = False,
                data = dict(
                    auth_url = self._connection.auth_url,
                    project_id = self._connection.project_id,
                    token = self._connection.token
                )
            )
        # If we were able to retrieve the app creds, then they are supported
        # Search the discovered app creds for one that matches the current project
        # and required name
        app_cred_name = "{}-{}".format(self._tenancy.name, self._cluster_app_cred_name)
        if any(
            cred.name == app_cred_name and cred.project_id == self._connection.project_id
            for cred in app_creds
        ):
            self._log("Reusing existing application credential")
            # If the app cred exists, indicate to the cluster engine that it should
            # reuse the user's existing credential
            return Credential(
                type = "openstack_application_credential",
                persistent = True,
                data = {}
            )
        else:
            self._log("Creating application credential '%s'", app_cred_name)
            # If the app cred doesn't exist, create it
            app_cred = user.application_credentials.create(
                name = app_cred_name,
                # This application credential must be unrestricted because it
                # will be used with Heat which makes trusts
                unrestricted = True
            )
            # Return a credential containing the data
            return Credential(
                type = "openstack_application_credential",
                persistent = True,
                data = dict(
                    auth_url = self._connection.auth_url,
                    application_credential_id = app_cred.id,
                    application_credential_secret = app_cred.secret
                )
            )

    @convert_exceptions
    def create_cluster(self, name, cluster_type, params, ssh_key):
        """
        See :py:meth:`.base.ScopedSession.create_cluster`.
        """
        params = self.validate_cluster_params(cluster_type, params)
        # Inject information about the networks to use
        params.update(
            cluster_floating_network = self._external_network().name,
            cluster_network = self._tenant_network(True).name
        )
        return self._fixup_cluster(
            self.cluster_manager.create_cluster(
                name,
                cluster_type,
                params,
                ssh_key,
                self._cluster_credential()
            )
        )

    @convert_exceptions
    def update_cluster(self, cluster, params):
        """
        See :py:meth:`.base.ScopedSession.update_cluster`.
        """
        if not isinstance(cluster, dto.Cluster):
            cluster = self.find_cluster(cluster)
        return self._fixup_cluster(
            self.cluster_manager.update_cluster(
                cluster,
                self.validate_cluster_params(
                    cluster.cluster_type,
                    params,
                    cluster.parameter_values
                ),
                self._cluster_credential()
            )
        )

    @convert_exceptions
    def patch_cluster(self, cluster):
        """
        See :py:meth:`.base.ScopedSession.patch_cluster`.
        """
        return self._fixup_cluster(
            self.cluster_manager.patch_cluster(
                cluster,
                self._cluster_credential()
            )
        )

    @convert_exceptions
    def delete_cluster(self, cluster):
        """
        See :py:meth:`.base.ScopedSession.delete_cluster`.
        """
        return self._fixup_cluster(
            self.cluster_manager.delete_cluster(
                cluster,
                self._cluster_credential()
            )
        )

    @convert_exceptions
    def close(self):
        """
        See :py:meth:`.base.ScopedSession.close`.
        """
        # Make sure the underlying api connection is closed
        self._connection.close()
        # Also close the cluster manager if one has been created
        if getattr(self, '_cluster_manager', None):
            self._cluster_manager.close()
