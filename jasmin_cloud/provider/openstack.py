"""
This module contains the provider implementation for OpenStack.
"""

import functools, time, logging

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
                raise errors.CommunicationError('Unexpected response from server')
        except requests.exceptions.ConnectionError:
            raise errors.CommunicationError('Error with HTTP connection')
        try:
            logger.info('[%s] Creating unscoped session', username)
            return UnscopedSession(
                self.auth_url, username, res.json()['access']['token']['id']
            )
        except KeyError:
            raise errors.CommunicationError('Unable to extract token from response')


def convert_sdk_exceptions(f):
    """
    Decorator that converts OpenStack SDK exceptions into errors from :py:mod:`.errors`.
    """
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except exceptions.ResourceNotFound as e:
            raise errors.ObjectNotFoundError
        except exceptions.HttpException as e:
            if e.http_status == 401:
                raise errors.AuthenticationError('Session has expired')
            elif e.http_status == 403:
                raise errors.PermissionDeniedError('Permission denied')
            elif e.http_status == 404:
                raise errors.ObjectNotFoundError
            elif e.http_status == 409:
                # 409 (Conflict) has a lot of different sub-errors depending on
                # the actual error text
                if 'quota exceeded' in e.details.lower():
                    raise errors.QuotaExceededError('Quota exceeded')
                raise errors.InvalidOperationError(e.details)
            else:
                raise errors.CommunicationError('Error communicating with OpenStack API')
        except exceptions.SDKException as e:
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
    def __init__(self, auth_url, username, token):
        self.auth_url = auth_url
        self.username = username
        self.token = token

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
                raise errors.AuthenticationError('Session has expired')
            elif e.response.status_code == 403:
                raise errors.PermissionDeniedError('Permission denied')
            else:
                raise errors.CommunicationError('Unexpected response from server')
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


class ScopedSession(base.ScopedSession):
    """
    Tenancy-scoped session implementation for OpenStack.

    Args:
        username: The username of the OpenStack user.
        tenancy: The tenancy id.
        connection: An ``openstack.connection.Connection`` for the tenancy.
    """
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
            bool(int((sdk_image.metadata or {}).get('jasmin:nat_allowed', '1')))
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
            sdk_flavor.ram
        )

    @convert_sdk_exceptions
    def sizes(self):
        """
        See :py:meth:`.base.ScopedSession.sizes`.
        """
        self._log('Fetching available flavors')
        flavors = list(self.connection.compute.flavors())
        self._log('Found %s flavors', len(flavors))
        return tuple(self._from_sdk_flavor(f) for f in flavors)

    @convert_sdk_exceptions
    def find_size(self, id):
        """
        See :py:meth:`.base.ScopedSession.find_size`.
        """
        self._log("Fetching flavor with id '%s'", id)
        return self._from_sdk_flavor(self.connection.compute.get_flavor(id))

    def _from_sdk_volume(self, sdk_volume):
        """
        Converts an OpenStack SDK volume object into a :py:class:`.dto.Volume`.
        """
        return dto.Volume(
            sdk_volume.id,
            # If there is no name, use part of the ID
            sdk_volume.name or sdk_volume.id[:13],
            sdk_volume.size
        )

    @convert_sdk_exceptions
    def volumes(self):
        """
        Lists the volumes available to the tenancy.

        .. note:: This is OpenStack specific and *not* part of the core interface.

        Returns:
            An iterable of :py:class:`~.dto.Volume` objects.
        """
        self._log('Fetching available volumes')
        volumes = list(self.connection.block_store.volumes())
        self._log('Found %s volumes', len(volumes))
        return tuple(self._from_sdk_volume(v) for v in volumes)

    @convert_sdk_exceptions
    def find_volume(self, id):
        """
        Finds a volume by id.

        Args:
            id: The id of the volume to find.

        .. note:: This is OpenStack specific and *not* part of the core interface.

        Returns:
            An :py:class:`~.dto.Volume` object.
        """
        self._log("Fetching volume with id '%s'", id)
        return self._from_sdk_volume(self.connection.block_store.get_volume(id))

    _POWER_STATES = {
        0 : 'Unknown',
        1 : 'Running',
        3 : 'Paused',
        4 : 'Shut down',
        6 : 'Crashed',
        7 : 'Suspended',
    }
    def _from_sdk_server(self, sdk_server):
        """
        Converts an OpenStack SDK server object into a :py:class:`.dto.Machine`.
        """
        # Use proxies for the image and size, so they are only fetched if needed
        image = dto.Proxy(
            lambda: self.find_image(sdk_server.image['id']),
            id = sdk_server.image['id']
        )
        size = dto.Proxy(
            lambda: self.find_size(sdk_server.flavor['id']),
            id = sdk_server.flavor['id']
        )
        # Also use proxies for the attached volumes
        def volumes():
            def volume_lambda(id):
                return lambda: self.find_volume(id)
            for v in sdk_server.attached_volumes:
                yield dto.Proxy(volume_lambda(v['id']), id = v['id'])
        # Generator to produce the IPs of a certain type
        def ips(type):
            for y in sdk_server.addresses.values():
                for x in y:
                    if x['version'] == 4 and x['OS-EXT-IPS:type'] == type:
                        yield x['addr']
        # If the jasmin:nat_allowed metadata is not present, use the value from
        # the image
        try:
            nat_allowed = bool(int(sdk_server.metadata['jasmin:nat_allowed']))
        except (TypeError, KeyError):
            nat_allowed = image.nat_allowed
        return dto.Machine(
            sdk_server.id,
            sdk_server.name,
            image,
            size,
            sdk_server.status,
            self._POWER_STATES[sdk_server.power_state],
            tuple(ips('fixed')),
            tuple(ips('floating')),
            nat_allowed,
            tuple(volumes()),
            sdk_server.user_id,
            dateutil.parser.parse(sdk_server.created_at)
        )

    @convert_sdk_exceptions
    def machines(self):
        """
        See :py:meth:`.base.ScopedSession.machines`.
        """
        self._log('Fetching available servers')
        servers = list(self.connection.compute.servers())
        self._log('Found %s servers', len(servers))
        return tuple(self._from_sdk_server(s) for s in servers)

    @convert_sdk_exceptions
    def find_machine(self, id):
        """
        See :py:meth:`.base.ScopedSession.find_machine`.
        """
        self._log("Fetching server with id '%s'", id)
        return self._from_sdk_server(self.connection.compute.get_server(id))

    @convert_sdk_exceptions
    def create_machine(self, name, image, size):
        """
        See :py:meth:`.base.ScopedSession.create_machine`.
        """
        image = image if isinstance(image, dto.Image) else self.find_image(image)
        size = size.id if isinstance(size, dto.Size) else size
        self._log("Creating machine '%s' (image: %s, size: %s)", name, image.name, size)
        # Get the network id to use
        # This assumes there is one tenancy router with a single tenant network
        # attached to it
        ports = self.connection.network.ports(device_owner = 'network:router_interface')
        network = next(ports).network_id
        server = self.connection.compute.create_server(
            name = name,
            image_id = image.id,
            flavor_id = size,
            networks = [{ 'uuid' : network }],
            # TODO: Sort out what to do with key pairs
            # Set the nat_allowed metadata based on the image
            metadata = { 'jasmin:nat_allowed' : '1' if image.nat_allowed else '0' }
        )
        return dto.Proxy(lambda: self.find_machine(server.id), id = server.id)

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

    @convert_sdk_exceptions
    def available_external_ips(self):
        """
        See :py:meth:`.base.ScopedSession.available_external_ips`.
        """
        self._log("Fetching available floating ips")
        ips = tuple(
            ip.floating_ip_address
            for ip in self.connection.network.ips()
            if ip.fixed_ip_address is None
        )
        self._log("Found %s available floating ips", len(ips))
        return ips

    @convert_sdk_exceptions
    def allocate_external_ip(self, machine):
        """
        See :py:meth:`.base.ScopedSession.allocate_external_ip`.
        """
        machine = machine if isinstance(machine, dto.Machine) else self.find_machine(machine)
        # If NATing is not allowed for the machine, bail
        if not machine.nat_allowed:
            raise errors.InvalidOperationError(
                'This machine is not allowed to have an external IP address'
            )
        self._log("Allocating new floating ip")
        # Get the external network being used by the tenancy router
        router = next(self.connection.network.routers())
        extnet = router.external_gateway_info['network_id']
        # Create a new floating IP on that network
        fip = self.connection.network.create_ip(floating_network_id = extnet)
        self._log("Allocated new floating ip '%s'", fip.floating_ip_address)
        return self.attach_external_ip(machine, fip.floating_ip_address)

    @convert_sdk_exceptions
    def attach_external_ip(self, machine, ip):
        """
        See :py:meth:`.base.ScopedSession.attach_external_ip`.
        """
        machine = machine if isinstance(machine, dto.Machine) else self.find_machine(machine)
        # If NATing is not allowed for the machine, bail
        if not machine.nat_allowed:
            raise errors.InvalidOperationError(
                'This machine is not allowed to have an external IP address'
            )
        self._log("Attaching floating ip '%s' to server '%s'", ip, machine.id)
        # Get the fixed IP of the machine on the tenant network
        ports = list(self.connection.network.ports())
        # The tenant network is the only network attached to the router
        tenant_net = next(
            p for p in ports if p.device_owner == 'network:router_interface'
        ).network_id
        machine_port = next(
            p for p in ports
            if p.device_id == machine.id and p.network_id == tenant_net
        )
        fixed_ip = machine_port.fixed_ips[0]['ip_address']
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

    @convert_sdk_exceptions
    def attach_volume(self, machine, size):
        """
        See :py:meth:`.base.ScopedSession.attach_volume`.
        """
        machine = machine.id if isinstance(machine, dto.Machine) else machine
        self._log('Creating new volume of size %s', size)
        volume = self.connection.block_store.create_volume(size = size)
        # Wait for the volume to become available for attaching it
        #   Wait for 5s at a time for a maximum of 1m
        for _ in range(12):
            time.sleep(5)
            volume = self.connection.block_store.get_volume(volume.id)
            if volume.status.lower() == 'available': break
        else:
            raise errors.OperationTimedOutError(
                'Timed out waiting for volume to be created'
            )
        self._log("Attaching volume '%s' to server '%s'", volume.id, machine)
        # It is not clear how to do this through the SDK, so use the API
        compute_ep = self.connection.session.get_endpoint(service_type = 'compute')
        r = self.connection.session.post(
            compute_ep + '/servers/' + machine + '/os-volume_attachments',
            json = { "volumeAttachment" : { "volumeId" : volume.id } }
        )
        return True

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
        for _ in range(12):
            time.sleep(5)
            vinfo = self.connection.block_store.get_volume(volume)
            if not any(a['server_id'] == machine for a in vinfo.attachments):
                break
        else:
            raise errors.OperationTimedOutError(
                'Timed out waiting for volume to become detach'
            )
        # If there no attachments to other machines, delete the volume
        if not vinfo.attachments:
            self._log("Deleting volume '%s'", volume)
            self.connection.block_store.delete_volume(volume)
        return True
