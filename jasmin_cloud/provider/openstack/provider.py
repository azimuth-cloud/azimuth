"""
This module contains the provider implementation for OpenStack.
"""

import functools
import logging
import base64
import hashlib
import json
import random

import dateutil.parser

import rackit

from . import api
from .. import base, errors, dto


logger = logging.getLogger(__name__)


_NET_DEVICE_OWNER = 'network:router_interface'
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


def convert_exceptions(f):
    """
    Decorator that converts OpenStack API exceptions into errors from :py:mod:`..errors`.
    """
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        try:
            return f(*args, **kwargs)
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


class Provider(base.Provider):
    """
    Provider implementation for OpenStack.

    Args:
        auth_url: The Keystone v3 authentication URL.
        domain: The domain to authenticate with (default ``Default``).
        interface: The OpenStack interface to connect using (default ``public``).
        az_backdoor_net_map: Mapping of availability zone to the UUID of the backdoor network
                             for that availability zone (default ``None``).
                             The backdoor network will only be attached if the image specifically
                             requests it. At that point, an availability zone will be randomly
                             selected, and if the network is not available an error will be raised.
        backdoor_vnic_type: The ``binding:vnic_type`` for the backdoor network. If not given,
                            no vNIC type will be specified (default ``None``).
        verify_ssl: If ``True`` (the default), verify SSL certificates. If ``False``
                    SSL certificates are not verified.
        cluster_engine: The :py:class:`~..cluster.base.Engine` to use for clusters.
                        If not given, clusters are disabled.
    """
    provider_name = 'openstack'

    def __init__(self, auth_url,
                       domain = 'Default',
                       interface = 'public',
                       az_backdoor_net_map = dict(),
                       net_device_owner = None,
                       backdoor_vnic_type = None,
                       verify_ssl = True,
                       cluster_engine = None):
        # Strip any trailing slashes from the auth URL
        self._auth_url = auth_url.rstrip('/')
        self._domain = domain
        self._interface = interface
        self._az_backdoor_net_map = az_backdoor_net_map or dict()
        self._net_device_owner = net_device_owner
        self._backdoor_vnic_type = backdoor_vnic_type
        self._verify_ssl = verify_ssl
        self._cluster_engine = cluster_engine

    @convert_exceptions
    def authenticate(self, username, password):
        """
        See :py:meth:`.base.Provider.authenticate`.
        """
        logger.info('Authenticating user %s with OpenStack', username)
        # Create an API connection using the username and password
        auth_params = api.AuthParams().use_password(self._domain, username, password)
        try:
            conn = api.Connection(self._auth_url, auth_params, self._interface, self._verify_ssl)
        except rackit.Unauthorized:
            # We want to use a different error message to convert_exceptions
            raise errors.AuthenticationError('Invalid username or password.')
        else:
            logger.info('[%s] Sucessfully authenticated user against OpenStack', username)
            return UnscopedSession(
                conn,
                az_backdoor_net_map = self._az_backdoor_net_map,
                backdoor_vnic_type = self._backdoor_vnic_type,
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
            # Failing to validate a token is a 404 for some reason
            raise errors.AuthenticationError('Your session has expired.')
        else:
            return UnscopedSession(
                conn,
                az_backdoor_net_map = self._az_backdoor_net_map,
                backdoor_vnic_type = self._backdoor_vnic_type,
                cluster_engine = self._cluster_engine
            )


class UnscopedSession(base.UnscopedSession):
    """
    Unscoped session implementation for OpenStack.

    Args:
        connection: An unscoped :py:mod:`.api.Connection`.
        az_backdoor_net_map: Mapping of availability zone to the UUID of the backdoor network
                             for that availability zone (default ``None``).
                             The backdoor network will only be attached if the image specifically
                             requests it. At that point, an availability zone will be randomly
                             selected, and if the network is not available an error will be raised.
        backdoor_vnic_type: The ``binding:vnic_type`` for the backdoor network. If not given,
                            no vNIC type will be specified (default ``None``).
        cluster_engine: The :py:class:`~..cluster.base.Engine` to use for clusters.
                        If not given, clusters are disabled.
    """
    provider_name = 'openstack'

    def __init__(self, connection,
                       net_device_owner = None,
                       az_backdoor_net_map = None,
                       backdoor_vnic_type = None,
                       cluster_engine = None):
        self._connection = connection
        self._az_backdoor_net_map = az_backdoor_net_map or dict()
        self._net_device_owner = net_device_owner,
        self._backdoor_vnic_type = backdoor_vnic_type
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

    @convert_exceptions
    def tenancies(self):
        """
        See :py:meth:`.base.UnscopedSession.tenancies`.
        """
        logger.info('[%s] Fetching available tenancies', self.username())
        projects = tuple(self._connection.projects.all())
        logger.info('[%s] Found %s projects', self.username(), len(projects))
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
                    'Could not find tenancy with ID {}'.format(tenancy)
                )
        logger.info('[%s] [%s] Creating scoped session', self.username(), tenancy.name)
        try:
            return ScopedSession(
                self.username(),
                tenancy,
                self._connection.scoped_connection(tenancy.id),
                az_backdoor_net_map = self._az_backdoor_net_map,
                net_device_owner = self._net_device_owner,
                backdoor_vnic_type = self._backdoor_vnic_type,
                cluster_engine = self._cluster_engine
            )
        except (rackit.Unauthorized, rackit.Forbidden):
            raise errors.ObjectNotFoundError(
                'Could not find tenancy with ID {}'.format(tenancy.id)
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

    Args:
        username: The username of the OpenStack user.
        tenancy: The :py:class:`~.dto.Tenancy`.
        connection: An ``openstack.connection.Connection`` for the tenancy.
        az_backdoor_net_map: Mapping of availability zone to the UUID of the backdoor network
                             for that availability zone (default ``None``).
                             The backdoor network will only be attached if the image specifically
                             requests it. At that point, an availability zone will be randomly
                             selected, and if the network is not available an error will be raised.
        backdoor_vnic_type: The ``binding:vnic_type`` for the backdoor network. If not given,
                            no vNIC type will be specified (default ``None``).
        cluster_engine: The :py:class:`~.cluster_engine.base.ClusterEngine` to use for clusters.
                        If not given, clusters are disabled.
    """
    provider_name = 'openstack'

    def __init__(self, username,
                       tenancy,
                       connection,
                       az_backdoor_net_map = None,
                       net_device_owner = None,
                       backdoor_vnic_type = None,
                       cluster_engine = None):
        self._username = username
        self._tenancy = tenancy
        self._connection = connection
        self._az_backdoor_net_map = az_backdoor_net_map or dict()
        self._net_device_owner = net_device_owner
        self._backdoor_vnic_type = backdoor_vnic_type
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

    def _tenant_network(self):
        """
        Returns the network connected to the tenant router.
        Assumes a single router with a single tenant network connected.
        """
        net_device_owner = self._net_device_owner or _NET_DEVICE_OWNER
        port = self._connection.network.ports.find_by_device_owner(net_device_owner)
        if port:
            return self._connection.network.networks.get(port.network_id)
        else:
            raise errors.ImproperlyConfiguredError('Could not find tenancy network')

    def _external_network(self):
        """
        Returns the external network that connects the tenant router to the outside world.
        """
        try:
            router = next(self._connection.network.routers.all())
        except StopIteration:
            raise errors.ImproperlyConfiguredError('Could not find tenancy router.')
        return self._connection.network.networks.get(router.external_gateway_info['network_id'])

    _POWER_STATES = {
        0: 'Unknown',
        1: 'Running',
        3: 'Paused',
        4: 'Shut down',
        6: 'Crashed',
        7: 'Suspended',
    }

    def _from_api_server(self, api_server):
        """
        See :py:meth:`.base.ScopedSession.find_machine`.
        """
        # Make sure we can find the image and flavor specified
        try:
            image = self.find_image(api_server.image.id)
        except (AttributeError, errors.ObjectNotFoundError):
            image = None
        try:
            size = self.find_size(api_server.flavor.id)
        except (AttributeError, errors.ObjectNotFoundError):
            size = None
        # Try to get nat_allowed from the machine metadata
        # If the nat_allowed metadata is not present, use the image
        # If the image does not exist anymore, assume it is allowed
        try:
            nat_allowed = bool(int(api_server.metadata['jasmin_nat_allowed']))
        except (KeyError, TypeError):
            nat_allowed = image.nat_allowed if image else True
        status = api_server.status
        fault = api_server.fault.get('message', None)
        task = api_server.task_state
        # Find IP addresses specifically on the tenant network that is connected
        # to the router
        network = self._tenant_network()
        # Function to get the first IP of a particular type on the tenant network
        def ip_of_type(ip_type):
            return next(
                (
                    a['addr']
                    for a in api_server.addresses.get(network.name, [])
                    if a['version'] == 4 and a['OS-EXT-IPS:type'] == ip_type
                ),
                None
            )
        return dto.Machine(
            api_server.id,
            api_server.name,
            image,
            size,
            dto.Machine.Status(
                getattr(dto.Machine.Status.Type, status, dto.Machine.Status.Type.OTHER),
                status,
                _replace_resource_names(fault) if fault else None
            ),
            self._POWER_STATES[api_server.power_state],
            task.capitalize() if task else None,
            ip_of_type('fixed'),
            ip_of_type('floating'),
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
        # In order to get fault info, we need to use a custom resource definition
        servers = tuple(
            self._from_api_server(s)
            for s in self._connection.compute.servers.all()
        )
        self._log('Found %s servers', len(servers))
        return servers

    @convert_exceptions
    def find_machine(self, id):
        """
        See :py:meth:`.base.ScopedSession.find_machine`.
        """
        # In order to get fault info, we need to use a custom resource definition
        self._log("Fetching server with id '%s'", id)
        return self._from_api_server(self._connection.compute.servers.get(id))

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
                raise errors.BadInputError('Invalid image provided')
        params.update(image_id = str(image.id))
        # To find the metadata elements, we need the raw API image
        # This will load from the cache
        api_image = self._connection.image.images.get(image.id)
        size = size.id if isinstance(size, dto.Size) else size
        params.update(flavor_id = size)
        self._log("Creating machine '%s' (image: %s, size: %s)", name, api_image.name, size)
        # Get the networks to use
        # Always use the tenant network that is attached to the router
        params.update(networks = [{ 'uuid': self._tenant_network().id }])
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
            # Keypairs are immutable, i.e. once created cannot be changed
            # We create keys with names of the form "<username>-<fingerprint>", which
            # allows for us to recognise when a user has changed their key and create
            # a new one
            fingerprint = hashlib.md5(base64.b64decode(ssh_key.split()[1])).hexdigest()
            key_name = '{}-{}'.format(self._username, fingerprint)
            try:
                # We need to force a fetch so that the keypair is resolved
                keypair = self._connection.compute.keypairs.get(key_name, force = True)
            except rackit.NotFound:
                keypair = self._connection.compute.keypairs.create(
                    name = key_name,
                    public_key = ssh_key
                )
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

    def _from_api_floatingip(self, api_floatingip):
        """
        Converts an OpenStack API floatingip object into a :py:class:`.dto.ExternalIp`.
        """
        if api_floatingip.port_id:
            port = self._connection.network.ports.get(api_floatingip.port_id)
            machine_id = port.device_id
        else:
            machine_id = None
        return dto.ExternalIp(api_floatingip.floating_ip_address, machine_id)

    @convert_exceptions
    def external_ips(self):
        """
        See :py:meth:`.base.ScopedSession.external_ips`.
        """
        self._log("Fetching floating ips")
        fips = tuple(
            self._from_api_floatingip(fip)
            for fip in self._connection.network.floatingips.all()
        )
        self._log("Found %s floating ips", len(fips))
        return fips

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
        self._log("Fetching floating IP details for '%s'", ip)
        fip = self._connection.network.floatingips.find_by_floating_ip_address(ip)
        if not fip:
            raise errors.ObjectNotFoundError("Could not find external IP '{}'".format(ip))
        return self._from_api_floatingip(fip)

    @convert_exceptions
    def attach_external_ip(self, ip, machine):
        """
        See :py:meth:`.base.ScopedSession.attach_external_ip`.
        """
        machine = machine if isinstance(machine, dto.Machine) else self.find_machine(machine)
        ip = ip.external_ip if isinstance(ip, dto.ExternalIp) else ip
        # If NATing is not allowed for the machine, bail
        if not machine.nat_allowed:
            raise errors.InvalidOperationError(
                'Machine is not allowed to have an external IP address.'
            )
        self._log("Attaching floating ip '%s' to server '%s'", ip, machine.id)
        # Get the port that attaches the machine to the tenant network
        tenant_net = self._tenant_network()
        port = next(
            self._connection.network.ports.all(
                device_id = machine.id,
                network_id = tenant_net.id
            ),
            None
        )
        if not port:
            raise errors.ImproperlyConfiguredError(
                'Machine is not connected to tenancy network.'
            )
        # If there is already a floating IP associated with the port, detach it
        current = self._connection.network.floatingips.find_by_port_id(port.id)
        if current:
            current._update(port_id = None)
        # Find the floating IP instance for the given address
        fip = self._connection.network.floatingips.find_by_floating_ip_address(ip)
        if not fip:
            raise errors.ObjectNotFoundError("Could not find external IP '{}'".format(ip))
        # Associate the floating IP with the port
        return self._from_api_floatingip(fip._update(port_id = port.id))

    @convert_exceptions
    def detach_external_ip(self, ip):
        """
        See :py:meth:`.base.ScopedSession.detach_external_ip`.
        """
        ip = ip.external_ip if isinstance(ip, dto.ExternalIp) else ip
        self._log("Detaching floating ip '%s'", ip)
        # Find the floating IP instance for the given address
        fip = self._connection.network.floatingips.find_by_floating_ip_address(ip)
        if not fip:
            raise errors.ObjectNotFoundError("Could not find external IP '{}'".format(ip))
        # Remove any association for the floating IP
        return self._from_api_floatingip(fip._update(port_id = None))

    _VOLUME_STATUSES = {
        'creating': dto.Volume.Status.CREATING,
        'available': dto.Volume.Status.AVAILABLE,
        'reserved': dto.Volume.Status.ATTACHING,
        'attaching': dto.Volume.Status.ATTACHING,
        'detaching': dto.Volume.Status.DETACHING,
        'in-use': dto.Volume.Status.IN_USE,
        'deleting': dto.Volume.Status.DELETING,
        'error': dto.Volume.Status.ERROR,
        'error_deleting': dto.Volume.Status.ERROR,
        'error_backing-up': dto.Volume.Status.ERROR,
        'error_restoring': dto.Volume.Status.ERROR,
        'error_extending': dto.Volume.Status.ERROR,
    }

    def _from_api_volume(self, api_volume):
        """
        Converts an OpenStack SDK volume object into a :py:class:`.dto.Volume`.
        """
        # Work out the volume status
        status = self._VOLUME_STATUSES.get(
            api_volume.status.lower(),
            dto.Volume.Status.OTHER
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
        if volume.status not in [dto.Volume.Status.AVAILABLE, dto.Volume.Status.ERROR]:
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
        if volume.status != dto.Volume.Status.AVAILABLE:
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
        return cluster._replace(
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
        return self._fixup_cluster(
            self.cluster_manager.find_cluster(id)
        )

    def _cluster_credential(self):
        return dict(
            auth_url = self._connection.auth_url,
            project_id = self._connection.project_id,
            token = self._connection.token
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
            cluster_network = self._tenant_network().name
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
