"""
This module contains the provider implementation for OpenStack.
"""

import functools, logging, base64, hashlib

import dateutil.parser
import requests
from openstack import connection, profile, exceptions

from . import base, errors, dto


logger = logging.getLogger(__name__)


class Provider(base.Provider):
    """
    Provider implementation for OpenStack.

    Args:
        auth_url: The Keystone v3 authentication URL.
        domain: The domain to authenticate with.
        verify_ssl: If ``True`` (the default), verify SSL certificates. If ``False``
                    SSL certificates are not verified.
    """
    provider_name = 'openstack'

    def __init__(self, auth_url, domain = 'Default', verify_ssl = True):
        # Strip any trailing slashes from the auth URL
        self.auth_url = auth_url.rstrip('/')
        self.domain = domain
        self.verify_ssl = verify_ssl

    def authenticate(self, username, password):
        """
        See :py:meth:`.base.Provider.authenticate`.
        """
        logger.info(
            '[%s] Authenticating with OpenStack at %s',
            username, self.auth_url
        )
        # Getting an unscoped token and then retrieving tenancies later seems to
        # be **really** hard to do through the SDK.
        # So we use the API directly
        res = requests.post(
            self.auth_url + '/auth/tokens',
            json = {
                "auth": {
                    "identity": {
                        "methods": [ "password" ],
                        "password": {
                            "user": {
                                "name": username,
                                "domain": {
                                    "name": self.domain,
                                },
                                "password": password,
                            },
                        },
                    },
                },
            },
            verify = self.verify_ssl
        )
        try:
            res.raise_for_status()
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 401:
                raise errors.AuthenticationError('Invalid username or password')
            else:
                raise errors.CommunicationError('Unexpected response from OpenStack')
        except requests.exceptions.ConnectionError:
            raise errors.CommunicationError('Error with HTTP connection')
        try:
            logger.info('[%s] Creating unscoped session', username)
            # The token is in a header
            return UnscopedSession(
                self.auth_url, username, res.headers['X-Subject-Token'], self.verify_ssl
            )
        except KeyError:
            raise errors.CommunicationError('Unable to extract token from response')


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


def convert_sdk_exceptions(f):
    """
    Decorator that converts OpenStack SDK exceptions into errors from :py:mod:`.errors`.
    """
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except exceptions.ResourceNotFound as e:
            message = _replace_resource_names(e.details.replace('404 Not Found: ', ''))
            raise errors.ObjectNotFoundError(message)
        except exceptions.HttpException as e:
            message = _replace_resource_names(e.details)
            if e.http_status == 400:
                raise errors.BadInputError(message)
            elif e.http_status == 401:
                raise errors.AuthenticationError('Your session has expired')
            elif e.http_status == 403:
                # Some quota exceeded errors get reported as permission denied (WHY???!!!)
                # So report them as quota exceeded instead
                if 'quota exceeded' in message.lower():
                    raise errors.QuotaExceededError(
                        'Requested operation would exceed at least one quota. '
                        'Please check your tenancy quotas.'
                    )
                raise errors.PermissionDeniedError('Permission denied')
            elif e.http_status == 404:
                raise errors.ObjectNotFoundError(message)
            elif e.http_status == 409:
                # 409 (Conflict) has a lot of different sub-errors depending on
                # the actual error text
                if 'quota exceeded' in message.lower():
                    raise errors.QuotaExceededError(
                        'Requested operation would exceed at least one quota. '
                        'Please check your tenancy quotas.'
                    )
                raise errors.InvalidOperationError(message)
            else:
                raise errors.CommunicationError('Error communicating with OpenStack API')
        except exceptions.SDKException as e:
            logger.exception('Unknown error in OpenStack SDK')
            raise errors.Error('Unknown error in OpenStack SDK')
    return wrapper


class UnscopedSession(base.UnscopedSession):
    """
    Unscoped session implementation for OpenStack.

    Args:
        auth_url: The Keystone v2.0 authentication URL.
        username: The username of the OpenStack user.
        token: An unscoped user token for the OpenStack user.
        verify_ssl: If ``True`` (the default), verify SSL certificates. If ``False``
                    SSL certificates are not verified.
    """
    provider_name = 'openstack'

    def __init__(self, auth_url, username, token, verify_ssl = True):
        self.auth_url = auth_url
        self.username = username
        self.token = token
        self.verify_ssl = verify_ssl

    def __repr__(self):
        return "openstack.UnscopedSession({}, {}, {})".format(
            repr(self.auth_url), repr(self.username), repr(self.token)
        )

    def tenancies(self):
        """
        See :py:meth:`.base.UnscopedSession.tenancies`.
        """
        logger.info('[%s] Fetching available tenancies', self.username)
        # Getting an unscoped token and then retrieving tenancies later seems to
        # be **really** hard to do through the SDK.
        # So we use the API directly
        res = requests.get(
            self.auth_url + '/auth/projects',
            headers = { 'X-Auth-Token' : self.token },
            verify = self.verify_ssl
        )
        try:
            res.raise_for_status()
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 401:
                raise errors.AuthenticationError('Your session has expired')
            elif e.response.status_code == 403:
                raise errors.PermissionDeniedError('Permission denied')
            else:
                raise errors.CommunicationError('Unexpected response from OpenStack')
        except requests.exceptions.ConnectionError:
            raise errors.CommunicationError('Error with HTTP connection')
        try:
            projects = res.json()['projects']
            logger.info('[%s] Found %s projects', self.username, len(projects))
            return tuple(dto.Tenancy(p['id'], p['name']) for p in projects if p['enabled'])
        except KeyError:
            raise errors.CommunicationError(
                'Unable to extract tenancy information from response'
            )

    @convert_sdk_exceptions
    def scoped_session(self, tenancy):
        """
        See :py:meth:`.base.UnscopedSession.scoped_session`.
        """
        tenancy = tenancy.id if isinstance(tenancy, dto.Tenancy) else tenancy
        logger.info('[%s] [%s] Creating scoped session', self.username, tenancy)
        prof = profile.Profile()
        prof.set_version('identity', 'v3')
        try:
            return ScopedSession(
                self.username,
                tenancy,
                connection.Connection(
                    auth_url = self.auth_url,
                    profile = prof,
                    project_id = tenancy,
                    auth_plugin = 'token',
                    token = self.token,
                    verify = self.verify_ssl
                )
            )
        except exceptions.HttpException as e:
            # If creating the session fails with an auth error, convert that to
            # not found to avoid revealing details about valid tenancies
            if e.status_code in { 401, 403 }:
                raise errors.ObjectNotFoundError(
                    'Could not find tenancy with ID {}'.format(tenancy)
                )
            else:
                raise e


class ScopedSession(base.ScopedSession):
    """
    Tenancy-scoped session implementation for OpenStack.

    Args:
        username: The username of the OpenStack user.
        tenancy: The tenancy id.
        connection: An ``openstack.connection.Connection`` for the tenancy.
    """
    provider_name = 'openstack'

    def __init__(self, username, tenancy, connection):
        self.username = username
        self.tenancy = tenancy
        self.connection = connection

    def _log(self, message, *args, level = logging.INFO, **kwargs):
        logger.info(
            '[%s] [%s] ' + message,
            self.username, self.tenancy, *args, **kwargs
        )

    @convert_sdk_exceptions
    def quotas(self):
        """
        See :py:meth:`.base.ScopedSession.quotas`.
        """
        self._log('Fetching tenancy quotas')
        # Compute provides a way to fetch this information through the SDK, but
        # the floating IP quota obtained through it is rubbish...
        compute_limits = self.connection.compute.get_limits().absolute
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
        # For block storage and floating IPs, use the API directly
        network_ep = self.connection.session.get_endpoint(service_type = 'network')
        network_quotas = self.connection.session.get(
            network_ep + '/quotas/' + self.tenancy
        ).json()
        quotas.append(
            dto.Quota(
                'external_ips',
                None,
                network_quotas['quota']['floatingip'],
                len(list(self.connection.network.ips()))
            )
        )
        volume_ep = self.connection.session.get_endpoint(service_type = 'volume')
        volume_limits = self.connection.session.get(volume_ep + '/limits').json()
        quotas.extend([
            dto.Quota(
                'storage',
                'GB',
                volume_limits['limits']['absolute']['maxTotalVolumeGigabytes'],
                volume_limits['limits']['absolute']['totalGigabytesUsed']
            ),
            dto.Quota(
                'volumes',
                None,
                volume_limits['limits']['absolute']['maxTotalVolumes'],
                volume_limits['limits']['absolute']['totalVolumesUsed']
            )
        ])
        return quotas

    def _from_sdk_image(self, sdk_image):
        """
        Converts an OpenStack SDK image object into a :py:class:`.dto.Image`.
        """
        return dto.Image(
            sdk_image.id,
            sdk_image.name,
            sdk_image.visibility == 'public',
            # Unless specifically disallowed by a flag, NAT is allowed
            bool(int((sdk_image.metadata or {}).get('jasmin:nat_allowed', '1'))),
            # The image size is specified in bytes. Convert to MB.
            float(sdk_image.size) / 1024.0 / 1024.0
        )

    @convert_sdk_exceptions
    def images(self):
        """
        See :py:meth:`.base.ScopedSession.images`.
        """
        self._log('Fetching available images')
        images = list(self.connection.image.images(status = 'active'))
        self._log('Found %s images', len(images))
        return tuple(self._from_sdk_image(i) for i in images)

    @convert_sdk_exceptions
    @functools.lru_cache()
    def find_image(self, id):
        """
        See :py:meth:`.base.ScopedSession.find_image`.
        """
        self._log("Fetching image with id '%s'", id)
        return self._from_sdk_image(self.connection.image.get_image(id))

    def _from_sdk_flavor(self, sdk_flavor):
        """
        Converts an OpenStack SDK flavor object into a :py:class:`.dto.Size`.
        """
        return dto.Size(
            sdk_flavor.id,
            sdk_flavor.name,
            sdk_flavor.vcpus,
            sdk_flavor.ram,
            sdk_flavor.disk
        )

    @convert_sdk_exceptions
    def sizes(self):
        """
        See :py:meth:`.base.ScopedSession.sizes`.
        """
        self._log('Fetching available flavors')
        flavors = list(self.connection.compute.flavors(is_disabled = False))
        self._log('Found %s flavors', len(flavors))
        return tuple(self._from_sdk_flavor(f) for f in flavors)

    @convert_sdk_exceptions
    @functools.lru_cache()
    def find_size(self, id):
        """
        See :py:meth:`.base.ScopedSession.find_size`.
        """
        self._log("Fetching flavor with id '%s'", id)
        return self._from_sdk_flavor(self.connection.compute.get_flavor(id))

    @functools.lru_cache()
    def _tenant_network(self):
        """
        Returns the ID of the tenant network connected to the tenant router.
        Assumes a single router with a single tenant network connected.
        Return ``None`` if the tenant network cannot be located.
        """
        port = next(self.connection.network.ports(device_owner = 'network:router_interface'))
        if port:
            return self.connection.network.find_network(port.network_id)
        else:
            return None

    @convert_sdk_exceptions
    def machines(self):
        """
        See :py:meth:`.base.ScopedSession.machines`.
        """
        # There doesn't seem to be a way to get the fault info for a server through
        # the OpenStack SDK. So we use the API directly.
        self._log('Fetching available servers')
        compute_ep = self.connection.session.get_endpoint(service_type = 'compute')
        servers = self.connection.session.get(compute_ep + '/servers').json()['servers']
        self._log('Found %s servers', len(servers))
        # The API only returns objects with a name and an ID
        # So fetch the full server for each machine
        return tuple(self.find_machine(s['id']) for s in servers)

    _POWER_STATES = {
        0 : 'Unknown',
        1 : 'Running',
        3 : 'Paused',
        4 : 'Shut down',
        6 : 'Crashed',
        7 : 'Suspended',
    }

    @convert_sdk_exceptions
    def find_machine(self, id):
        """
        See :py:meth:`.base.ScopedSession.find_machine`.
        """
        # There doesn't seem to be a way to get the fault info for a server through
        # the OpenStack SDK. So we use the API directly.
        self._log("Fetching server with id '%s'", id)
        compute_ep = self.connection.session.get_endpoint(service_type = 'compute')
        response = self.connection.session.get(compute_ep + '/servers/' + id)
        sdk_server = response.json()['server']
        # Try to get nat_allowed from the machine metadata
        # If the nat_allowed metadata is not present, try to get it from the image
        try:
            nat_allowed = bool(int(sdk_server['metadata']['jasmin:nat_allowed']))
        except (TypeError, KeyError):
            nat_allowed = self.find_image(sdk_server['image']['id']).nat_allowed
        status = sdk_server['status']
        fault = sdk_server.get('fault', {}).get('message', None)
        task = sdk_server.get('OS-EXT-STS:task_state', None)
        # Find IP addresses
        network = self._tenant_network()
        # Function to get the first IP of a particular type on the tenant network
        def ip_of_type(ip_type):
            return next(
                (
                    a['addr']
                    for a in sdk_server['addresses'].get(network.name, [])
                    if a['version'] == 4 and a['OS-EXT-IPS:type'] == ip_type
                ),
                None
            )
        return dto.Machine(
            sdk_server['id'],
            sdk_server['name'],
            sdk_server['image']['id'],
            sdk_server['flavor']['id'],
            dto.Machine.Status(
                getattr(dto.Machine.Status.Type, status, dto.Machine.Status.Type.OTHER),
                status,
                _replace_resource_names(fault) if fault else None
            ),
            self._POWER_STATES[sdk_server['OS-EXT-STS:power_state']],
            task.capitalize() if task else None,
            ip_of_type('fixed'),
            ip_of_type('floating'),
            nat_allowed,
            tuple(v['id'] for v in sdk_server['os-extended-volumes:volumes_attached']),
            sdk_server['user_id'],
            dateutil.parser.parse(sdk_server['created'])
        )

    def _get_or_create_keypair(self, ssh_key):
        # Keypairs are immutable, i.e. once created cannot be changed
        # We create keys with names of the form "<username>-<fingerprint>", which
        # allows for us to recognise when a user has changed their key and create
        # a new one
        fingerprint = hashlib.md5(base64.b64decode(ssh_key.split()[1])).hexdigest()
        key_name = '{}-{}'.format(self.username, fingerprint)
        try:
            return self.connection.compute.find_keypair(key_name, False)
        except exceptions.ResourceNotFound:
            return self.connection.compute.create_keypair(
                name = key_name,
                public_key = ssh_key
            )

    @convert_sdk_exceptions
    def create_machine(self, name, image, size, ssh_key = None):
        """
        See :py:meth:`.base.ScopedSession.create_machine`.
        """
        # Convert the ObjectNotFound into an InvalidOperation
        try:
            image = image if isinstance(image, dto.Image) else self.find_image(image)
        except errors.ObjectNotFoundError:
            raise errors.BadInputError('Invalid image provided')
        size = size.id if isinstance(size, dto.Size) else size
        self._log("Creating machine '%s' (image: %s, size: %s)", name, image.name, size)
        # Get the network id to use
        network = self._tenant_network()
        if not network:
            raise errors.ImproperlyConfiguredError('Could not find tenancy network')
        # Get the keypair to inject
        keypair = self._get_or_create_keypair(ssh_key) if ssh_key else None
        server = self.connection.compute.create_server(
            name = name,
            image_id = image.id,
            flavor_id = size,
            networks = [{ 'uuid' : network.id }],
            # Set the nat_allowed metadata based on the image
            metadata = { 'jasmin:nat_allowed' : '1' if image.nat_allowed else '0' },
            # The SDK doesn't like it if None is given for keypair, but behaves
            # correctly if it is not given at all
            **({ 'key_name': keypair.name } if keypair else {})
        )
        return self.find_machine(server.id)

    @convert_sdk_exceptions
    def start_machine(self, machine):
        """
        See :py:meth:`.base.ScopedSession.start_machine`.
        """
        machine = machine.id if isinstance(machine, dto.Machine) else machine
        self._log("Starting machine '%s'", machine)
        self.connection.compute.start_server(machine)
        return self.find_machine(machine)

    @convert_sdk_exceptions
    def stop_machine(self, machine):
        """
        See :py:meth:`.base.ScopedSession.stop_machine`.
        """
        machine = machine.id if isinstance(machine, dto.Machine) else machine
        self._log("Stopping machine '%s'", machine)
        self.connection.compute.stop_server(machine)
        return self.find_machine(machine)

    @convert_sdk_exceptions
    def restart_machine(self, machine):
        """
        See :py:meth:`.base.ScopedSession.restart_machine`.
        """
        machine = machine.id if isinstance(machine, dto.Machine) else machine
        self._log("Restarting machine '%s'", machine)
        self.connection.compute.reboot_server(machine, 'SOFT')
        return self.find_machine(machine)

    @convert_sdk_exceptions
    def delete_machine(self, machine):
        """
        See :py:meth:`.base.ScopedSession.delete_machine`.
        """
        machine = machine.id if isinstance(machine, dto.Machine) else machine
        self._log("Deleting machine '%s'", machine)
        self.connection.compute.delete_server(machine)
        try:
            return self.find_machine(machine)
        except errors.ObjectNotFoundError:
            return None

    def _from_sdk_floatingip(self, sdk_floatingip):
        """
        Converts an OpenStack SDK floatingip object into a :py:class:`.dto.ExternalIp`.
        """
        if sdk_floatingip.port_id:
            port = self.connection.network.find_port(sdk_floatingip.port_id)
            machine_id = port.device_id
        else:
            machine_id = None
        return dto.ExternalIp(sdk_floatingip.floating_ip_address, machine_id)

    @convert_sdk_exceptions
    def external_ips(self):
        """
        See :py:meth:`.base.ScopedSession.external_ips`.
        """
        self._log("Fetching floating ips")
        fips = list(self.connection.network.ips())
        self._log("Found %s floating ips", len(fips))
        return tuple(self._from_sdk_floatingip(fip) for fip in fips)

    @convert_sdk_exceptions
    def allocate_external_ip(self):
        """
        See :py:meth:`.base.ScopedSession.allocate_external_ip`.
        """
        self._log("Allocating new floating ip")
        # Get the external network being used by the tenancy router
        router = next(self.connection.network.routers(), None)
        if not router:
            raise errors.ImproperlyConfiguredError('Could not find tenancy router.')
        extnet = router.external_gateway_info['network_id']
        # Create a new floating IP on that network
        fip = self.connection.network.create_ip(floating_network_id = extnet)
        self._log("Allocated new floating ip '%s'", fip.floating_ip_address)
        return self._from_sdk_floatingip(fip)

    @convert_sdk_exceptions
    def find_external_ip(self, ip):
        """
        See :py:meth:`.base.ScopedSession.find_external_ip`.
        """
        self._log("Fetching floating IP details for '%s'", ip)
        fip = next(self.connection.network.ips(floating_ip_address = ip), None)
        if not fip:
            raise errors.ObjectNotFoundError("Could not find external IP '{}'".format(ip))
        return self._from_sdk_floatingip(fip)

    @convert_sdk_exceptions
    def attach_external_ip(self, ip, machine):
        """
        See :py:meth:`.base.ScopedSession.attach_external_ip`.
        """
        machine = machine if isinstance(machine, dto.Machine) else self.find_machine(machine)
        ip = ip.external_ip if isinstance(ip, dto.ExternalIp) else ip
        # If NATing is not allowed for the machine, bail
        if not machine.nat_allowed:
            raise errors.InvalidOperationError(
                'Machine is not allowed to have an external IP address.'
            )
        self._log("Attaching floating ip '%s' to server '%s'", ip, machine.id)
        # Get the port that attaches the machine to the tenant network
        tenant_net = self._tenant_network()
        if not tenant_net:
            raise errors.ImproperlyConfiguredError('Could not find tenancy network.')
        port = next(
            self.connection.network.ports(device_id = machine.id,
                                          network_id = tenant_net.id),
            None
        )
        if not port:
            raise errors.ImproperlyConfiguredError(
                'Machine is not connected to tenancy network.'
            )
        # If there is already a floating IP associated with the port, detach it
        current = next(self.connection.network.ips(port_id = port.id), None)
        if current:
            self.connection.network.update_ip(current, port_id = None)
        # Find the floating IP instance for the given address
        fip = next(self.connection.network.ips(floating_ip_address = ip), None)
        if not fip:
            raise errors.ObjectNotFoundError("Could not find external IP '{}'".format(ip))
        # Associate the floating IP with the port
        return self._from_sdk_floatingip(
            self.connection.network.update_ip(fip, port_id = port.id)
        )

    @convert_sdk_exceptions
    def detach_external_ip(self, ip):
        """
        See :py:meth:`.base.ScopedSession.detach_external_ip`.
        """
        ip = ip.external_ip if isinstance(ip, dto.ExternalIp) else ip
        self._log("Detaching floating ip '%s'", ip)
        # Find the floating IP instance for the given address
        fip = next(self.connection.network.ips(floating_ip_address = ip), None)
        if not fip:
            raise errors.ObjectNotFoundError("Could not find external IP '{}'".format(ip))
        # Remove any association for the floating IP
        return self._from_sdk_floatingip(
            self.connection.network.update_ip(fip, port_id = None)
        )

    _VOLUME_STATUSES = {
        'creating': dto.Volume.Status.CREATING,
        'available': dto.Volume.Status.AVAILABLE,
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

    def _from_sdk_volume(self, sdk_volume):
        """
        Converts an OpenStack SDK volume object into a :py:class:`.dto.Volume`.
        """
        # Work out the volume status
        status = self._VOLUME_STATUSES.get(
            sdk_volume.status.lower(),
            dto.Volume.Status.OTHER
        )
        try:
            attachment = sdk_volume.attachments[0]
        except IndexError:
            attachment = None
        return dto.Volume(
            sdk_volume.id,
            # If there is no name, use part of the ID
            sdk_volume.name or sdk_volume.id[:13],
            status,
            sdk_volume.size,
            attachment['server_id'] if attachment else None,
            attachment['device'] if attachment else None
        )

    @convert_sdk_exceptions
    def volumes(self):
        """
        See :py:meth:`.base.ScopedSession.volumes`.
        """
        self._log('Fetching available volumes')
        volumes = list(self.connection.block_store.volumes())
        self._log('Found %s volumes', len(volumes))
        return tuple(self._from_sdk_volume(v) for v in volumes)

    @convert_sdk_exceptions
    def find_volume(self, id):
        """
        See :py:meth:`.base.ScopedSession.find_volume`.
        """
        self._log("Fetching volume with id '%s'", id)
        volume = self.connection.block_store.get_volume(id)
        return self._from_sdk_volume(volume)

    @convert_sdk_exceptions
    def create_volume(self, name, size):
        """
        See :py:meth:`.base.ScopedSession.create_volume`.
        """
        self._log("Creating machine '%s' (size: %s)", name, size)
        volume = self.connection.block_store.create_volume(name = name, size = size)
        return self.find_volume(volume.id)

    @convert_sdk_exceptions
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
        self.connection.block_store.delete_volume(volume.id)
        try:
            return self.find_volume(volume.id)
        except errors.ObjectNotFoundError:
            return None

    @convert_sdk_exceptions
    def attach_volume(self, volume, machine):
        """
        See :py:meth:`.base.ScopedSession.attach_volume`.
        """
        volume = volume if isinstance(volume, dto.Volume) else self.find_volume(volume)
        machine = machine.id if isinstance(machine, dto.Machine) else machine
        # If the volume is already attached to the machine there is nothing to do
        if volume.machine_id == machine:
            return volume
        # The volume must be available before attaching
        if volume.status != dto.Volume.Status.AVAILABLE:
            raise errors.InvalidOperationError(
                "Volume must be AVAILABLE before attaching."
            )
        self._log("Attaching volume '%s' to server '%s'", volume.id, machine)
        self.connection.compute.create_volume_attachment(
            machine,
            volume_id = volume.id
        )
        return self.find_volume(volume.id)

    @convert_sdk_exceptions
    def detach_volume(self, volume):
        """
        See :py:meth:`.base.ScopedSession.detach_volume`.
        """
        volume = volume if isinstance(volume, dto.Volume) else self.find_volume(volume)
        # If the volume is already detached, we are done
        if not volume.machine_id:
            return volume
        self._log("Detaching volume '%s' from '%s'", volume.id, volume.machine_id)
        self.connection.compute.delete_volume_attachment(volume.id, volume.machine_id)
        return self.find_volume(volume.id)
