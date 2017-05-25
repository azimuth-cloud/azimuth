"""
This module contains the provider implementation for OpenStack.
"""

import functools, time, logging, re, collections

import dateutil.parser
import requests
from openstack import connection, profile, exceptions

from . import base, errors, dto


logger = logging.getLogger(__name__)


class Provider(base.Provider):
    """
    Provider implementation for OpenStack.

    Args:
        auth_url: The Keystone v2.0 authentication URL.
    """
    provider_name = 'openstack'

    def __init__(self, auth_url):
        # Strip any trailing slashes from the auth URL
        self.auth_url = auth_url.rstrip('/')

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
            self.auth_url + '/tokens',
            json = {
                "auth" : {
                    "passwordCredentials" : {
                        "username" : username,
                        "password" : password,
                    },
                },
            }
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
            return UnscopedSession(
                self.auth_url, username, res.json()['access']['token']['id']
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
    """
    provider_name = 'openstack'

    def __init__(self, auth_url, username, token):
        self.auth_url = auth_url
        self.username = username
        self.token = token

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
            self.auth_url + '/tenants',
            headers = { 'X-Auth-Token' : self.token }
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
            tenancies = res.json()['tenants']
            logger.info('[%s] Found %s tenancies', self.username, len(tenancies))
            return tuple(dto.Tenancy(t['id'], t['name']) for t in tenancies)
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
        prof.set_version('identity', 'v2')
        try:
            return ScopedSession(
                self.username,
                tenancy,
                connection.Connection(
                    auth_url = self.auth_url,
                    profile = prof,
                    project_id = tenancy,
                    auth_plugin = 'token',
                    token = self.token
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
        quotas = {
            'cpus' : dto.Quota(
                'cpus',
                None,
                compute_limits.total_cores,
                compute_limits.total_cores_used
            ),
            'ram' : dto.Quota(
                'ram',
                'MB',
                compute_limits.total_ram,
                compute_limits.total_ram_used
            ),
            'machines' : dto.Quota(
                'machines',
                None,
                compute_limits.instances,
                compute_limits.instances_used
            ),
        }
        # For block storage and floating IPs, use the API directly
        network_ep = self.connection.session.get_endpoint(service_type = 'network')
        network_quotas = self.connection.session.get(
            network_ep + '/quotas/' + self.tenancy
        ).json()
        quotas['external_ips'] = dto.Quota(
            'external_ips',
            None,
            network_quotas['quota']['floatingip'],
            len(list(self.connection.network.ips()))
        )
        volume_ep = self.connection.session.get_endpoint(service_type = 'volume')
        volume_limits = self.connection.session.get(volume_ep + '/limits').json()
        quotas['storage'] = dto.Quota(
            'storage',
            'GB',
            volume_limits['limits']['absolute']['maxTotalVolumeGigabytes'],
            volume_limits['limits']['absolute']['totalGigabytesUsed']
        )
        quotas['volumes'] = dto.Quota(
            'volumes',
            None,
            volume_limits['limits']['absolute']['maxTotalVolumes'],
            volume_limits['limits']['absolute']['totalVolumesUsed']
        )
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
        images = list(self.connection.image.images())
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

    def _tenant_network(self):
        """
        Returns the ID of the tenant network connected to the tenant router.
        Assumes a single router with a single tenant network connected.
        Return ``None`` if the tenant network cannot be located.
        """
        try:
            port = next(
                self.connection.network.ports(device_owner = 'network:router_interface')
            )
            return self.connection.network.find_network(port.network_id)
        except StopIteration:
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
    @functools.lru_cache()
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
        image = self.find_image(sdk_server['image']['id'])
        try:
            nat_allowed = bool(int(sdk_server['metadata']['jasmin:nat_allowed']))
        except (TypeError, KeyError):
            nat_allowed = image.nat_allowed
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
            image,
            self.find_size(sdk_server['flavor']['id']),
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
            tuple(
                self.find_volume(sdk_server['id'], v['id'])
                for v in sdk_server['os-extended-volumes:volumes_attached']
            ),
            sdk_server['user_id'],
            dateutil.parser.parse(sdk_server['created'])
        )

    @convert_sdk_exceptions
    def create_machine(self, name, image, size):
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
        server = self.connection.compute.create_server(
            name = name,
            image_id = image.id,
            flavor_id = size,
            networks = [{ 'uuid' : network.id }],
            # TODO: Sort out what to do with key pairs
            # Set the nat_allowed metadata based on the image
            metadata = { 'jasmin:nat_allowed' : '1' if image.nat_allowed else '0' }
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
        return True

    @convert_sdk_exceptions
    def stop_machine(self, machine):
        """
        See :py:meth:`.base.ScopedSession.stop_machine`.
        """
        machine = machine.id if isinstance(machine, dto.Machine) else machine
        self._log("Stopping machine '%s'", machine)
        self.connection.compute.stop_server(machine)
        return True

    @convert_sdk_exceptions
    def restart_machine(self, machine):
        """
        See :py:meth:`.base.ScopedSession.restart_machine`.
        """
        machine = machine.id if isinstance(machine, dto.Machine) else machine
        self._log("Restarting machine '%s'", machine)
        self.connection.compute.reboot_server(machine, 'SOFT')
        return True

    @convert_sdk_exceptions
    def delete_machine(self, machine):
        """
        See :py:meth:`.base.ScopedSession.delete_machine`.
        """
        machine = machine if isinstance(machine, dto.Machine) else self.find_machine(machine)
        self._log("Deleting machine '%s'", machine.id)
        # Remove any attached volumes from the machine before deleting
        for volume in machine.attached_volumes:
            self.detach_volume(machine, volume)
        self.connection.compute.delete_server(machine.id)
        return True

    def _from_sdk_floatingip(self, sdk_floatingip):
        """
        Converts an OpenStack SDK floatingip object into a :py:class:`.dto.ExternalIp`.
        """
        return dto.ExternalIp(
            sdk_floatingip.floating_ip_address,
            sdk_floatingip.fixed_ip_address
        )

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
        try:
            router = next(self.connection.network.routers())
        except StopIteration:
            raise errors.ImproperlyConfiguredError('Could not find tenancy router.')
        extnet = router.external_gateway_info['network_id']
        # Create a new floating IP on that network
        fip = self.connection.network.create_ip(floating_network_id = extnet)
        self._log("Allocated new floating ip '%s'", fip.floating_ip_address)
        return self._from_sdk_floatingip(fip)

    @convert_sdk_exceptions
    def attach_external_ip(self, machine, ip):
        """
        See :py:meth:`.base.ScopedSession.attach_external_ip`.
        """
        machine = machine if isinstance(machine, dto.Machine) else self.find_machine(machine)
        ip = ip.external_ip if isinstance(machine, dto.ExternalIp) else ip
        # If NATing is not allowed for the machine, bail
        if not machine.nat_allowed:
            raise errors.InvalidOperationError(
                'Machine is not allowed to have an external IP address'
            )
        self._log("Attaching floating ip '%s' to server '%s'", ip, machine.id)
        # Get the fixed IP of the machine on the tenant network
        tenant_net = self._tenant_network()
        if not tenant_net:
            raise errors.ImproperlyConfiguredError('Could not find tenancy network.')
        try:
            port = next(
                self.connection.network.ports(device_id = machine.id,
                                              network_id = tenant_net.id)
            )
        except StopIteration:
            raise errors.ImproperlyConfiguredError(
                'Machine is not connected to tenancy network.'
            )
        fixed_ip = port.fixed_ips[0]['ip_address']
        self.connection.compute.add_floating_ip_to_server(machine.id, ip, fixed_ip)
        return True

    @convert_sdk_exceptions
    def detach_external_ips(self, machine):
        """
        See :py:meth:`.base.ScopedSession.detach_external_ips`.
        """
        machine = machine if isinstance(machine, dto.Machine) else self.find_machine(machine)
        for ip in machine.external_ips:
            self._log("Detaching floating ip '%s' from server '%s'", ip, machine.id)
            self.connection.compute.remove_floating_ip_from_server(machine.id, ip)
        return True

    def _from_sdk_volume(self, machine, sdk_volume):
        """
        Converts an OpenStack SDK volume object into a :py:class:`.dto.Volume`.
        """
        return dto.Volume(
            sdk_volume.id,
            machine,
            # If there is no name, use part of the ID
            sdk_volume.name or sdk_volume.id[:13],
            sdk_volume.size,
            # Find the attachment for the given machine and get the device name
            next(
                (
                    attachment['device']
                    for attachment in sdk_volume.attachments
                    if attachment['server_id'] == machine
                ),
                None
            )
        )

    @convert_sdk_exceptions
    def volumes(self, machine):
        """
        See :py:meth:`.base.ScopedSession.volumes`.
        """
        machine = machine.id if isinstance(machine, dto.Machine) else machine
        self._log('Fetching available volumes')
        volumes = list(self.connection.block_store.volumes())
        self._log('Found %s volumes', len(volumes))
        self._log("Filtering volumes for machine '%s'", machine)
        volumes = tuple(
            self._from_sdk_volume(machine, v) for v in volumes
            if any(a['server_id'] == machine for a in v.attachments)
        )
        self._log("Found %s volumes for machine '%s'", len(volumes), machine)
        return volumes

    @convert_sdk_exceptions
    @functools.lru_cache()
    def find_volume(self, machine, id):
        """
        See :py:meth:`.base.ScopedSession.find_volume`.
        """
        machine = machine.id if isinstance(machine, dto.Machine) else machine
        self._log("Fetching volume with id '%s'", id)
        volume = self.connection.block_store.get_volume(id)
        # If the volume is not attached to the machine, treat it as not found
        if not any(a['server_id'] == machine for a in volume.attachments):
            raise errors.ObjectNotFoundError(
                'Could not find volume with ID {}'.format(id)
            )
        return self._from_sdk_volume(machine, volume)

    @convert_sdk_exceptions
    def attach_volume(self, machine, size):
        """
        See :py:meth:`.base.ScopedSession.attach_volume`.
        """
        machine = machine.id if isinstance(machine, dto.Machine) else machine
        self._log('Creating new volume of size %s', size)
        volume = self.connection.block_store.create_volume(size = size)
        # Wait for the volume to become available for attaching it
        #   We wait for a maximum of 5 minutes
        deadline = time.time() + (5 * 60)
        while True:
            time.sleep(1)
            volume = self.connection.block_store.get_volume(volume.id)
            status = volume.status.lower()
            if status == 'available': break
            if status == 'error':
                raise errors.Error('Error during volume creation.')
            if time.time() > deadline:
                raise errors.OperationTimedOutError(
                    'Timed out waiting for volume to be created.'
                )
        self._log("Attaching volume '%s' to server '%s'", volume.id, machine)
        # It is not clear how to do this through the SDK, so use the API
        compute_ep = self.connection.session.get_endpoint(service_type = 'compute')
        r = self.connection.session.post(
            compute_ep + '/servers/' + machine + '/os-volume_attachments',
            json = { "volumeAttachment" : { "volumeId" : volume.id } }
        )
        # Wait for the volume to become attached
        #   We wait for a maximum of 5 minutes
        deadline = time.time() + (5 * 60)
        while True:
            time.sleep(1)
            volume = self.connection.block_store.get_volume(volume.id)
            status = volume.status.lower()
            if status == 'in-use': break
            if time.time() > deadline:
                raise errors.OperationTimedOutError(
                    'Timed out waiting for volume to attach.'
                )
        return self.find_volume(machine, volume.id)

    @convert_sdk_exceptions
    def detach_volume(self, machine, volume):
        """
        See :py:meth:`.base.ScopedSession.detach_volume`.
        """
        machine = machine.id if isinstance(machine, dto.Machine) else machine
        volume = volume.id if isinstance(volume, dto.Volume) else volume
        self._log("Detaching volume '%s' from server '%s'", volume, machine)
        # If the volume has any attachments to the machine, remove them
        # It is not obvious how to do this through the SDK, so use the API
        compute_ep = self.connection.session.get_endpoint(service_type = 'compute')
        self.connection.session.delete(
            '{}/servers/{}/os-volume_attachments/{}'.format(
                compute_ep,
                machine,
                volume
            )
        )
        # First, make sure the volume has detached from the machine by checking
        # the attachments until there are none for the machine
        #   Check every 5s for a maximum of 1m
        vinfo = None
        deadline = time.time() + (5 * 60)
        while True:
            time.sleep(1)
            vinfo = self.connection.block_store.get_volume(volume)
            if not any(a['server_id'] == machine for a in vinfo.attachments):
                break
            if time.time() > deadline:
                raise errors.OperationTimedOutError(
                    'Timed out waiting for volume to detach.'
                )
        # If there no attachments to other machines, delete the volume
        if not vinfo.attachments:
            self._log("Deleting volume '%s'", volume)
            self.connection.block_store.delete_volume(volume)
        return True
