"""
This module defines an implementation of the cloud services interfaces for the
VMWare vCloud Director API vn5.5
"""

__author__ = "Matt Pryor"
__copyright__ = "Copyright 2015 UK Science and Technology Facilities Council"


import os, uuid, re
from ipaddress import IPv4Address, AddressValueError, summarize_address_range
from time import sleep
from datetime import datetime
import xml.etree.ElementTree as ET

import requests
from jinja2 import Environment, FileSystemLoader

from jasmin_portal.cloudservices import *


# Prefixes for vCD namespaces
_NS = {
    'vcd' : 'http://www.vmware.com/vcloud/v1.5',
    'ovf' : 'http://schemas.dmtf.org/ovf/envelope/1',
}

# Required headers for all requests
_REQUIRED_HEADERS = { 'Accept':'application/*+xml;version=5.5' }

# Map of vCD vApp status codes to MachineStatus instances
_STATUS_MAP = {
    -1 : MachineStatus.PROVISIONING_FAILED,
     0 : MachineStatus.PROVISIONING,
     1 : MachineStatus.UNKNOWN,
     3 : MachineStatus.SUSPENDED,
     4 : MachineStatus.POWERED_ON,
     5 : MachineStatus.WAITING_FOR_INPUT,
     6 : MachineStatus.UNKNOWN,
     7 : MachineStatus.UNRECOGNISED,
     8 : MachineStatus.POWERED_OFF,
     9 : MachineStatus.INCONSISTENT,
    10 : MachineStatus.UNKNOWN,
}

# Poll interval for checking tasks
_POLL_INTERVAL = 2

# Jinja2 environment for loading XML templates from the same directory as this
# script is in
_ENV = Environment(
    loader = FileSystemLoader(os.path.dirname(os.path.realpath(__file__)))
)

# Function to escape special chars in guest customisation script for XML
_escape_script = lambda s: s.replace(os.linesep, '&#13;').\
                             replace('"', '&quot;').\
                             replace('%', '&#37;').\
                             replace("'", '&apos;')


###############################################################################
###############################################################################


def check_response(res):
    """
    Checks a response from the vCD API, and throws a relevant exception if the
    status code is not 20x

    For the status codes returned by the vCD API, see
    http://pubs.vmware.com/vcd-55/topic/com.vmware.vcloud.api.doc_55/GUID-D2B2E6D4-7A92-4D1B-80C0-F32AE0CA3D11.html
    """
        
    # Check the status code
    if res.status_code == 503:
        # requests reports a 503 if it can't reach the server at all
        raise ProviderConnectionError('Cannot connect to vCloud Director API')
    if res.status_code >= 500:
        # Treat all other 5xx codes as if we connected but the server
        # encountered an error
        raise ProviderUnavailableError('vCloud Director API encountered an error')
    if res.status_code == 401:
        # 401 is reported if authentication failed
        raise AuthenticationError('Authentication failed')
    if res.status_code == 403:
        # 403 is reported if the authenticated user doesn't have adequate
        # permissions
        raise PermissionsError('Insufficient permissions')
    if res.status_code == 404:
        # 404 is reported if the resource doesn't exist
        raise NoSuchResourceError('Resource does not exist')
    if res.status_code >= 400:
        # For other 400 codes, check the body of the request to see if we can give some
        # more specific information
        error = ET.fromstring(res.text)
        error_code = error.attrib['minorErrorCode'].upper()
        # BAD_REQUEST is sent when an action is invalid given the current state
        # or when a badly formatted request is sent
        if error_code == 'BAD_REQUEST':
            # To distinguish, we need to check the message
            if 'validation error' in error.attrib['message'].lower():
                raise BadRequestError('Badly formatted request')
            else:
                raise InvalidActionError('Action is invalid for current state')
        # DUPLICATE_NAME is sent when a name is duplicated (surprise...!)
        if error_code == 'DUPLICATE_NAME':
            raise DuplicateNameError('Name is already in use')
        # Otherwise, assume the request was incorrectly specified by the implementation
        raise ImplementationError('Bad request')
    # Any 20x status codes are fine
    return res


###############################################################################
###############################################################################


class VCloudProvider(Provider):
    """
    Provider implementation for vCloud Director API vn5.5
    """
    def __init__(self, endpoint):
        self.__endpoint = endpoint.rstrip('/')
        
    def new_session(self, username, password):
        # Convert exceptions from requests into cloud service connection errors
        # Since we don't configure requests to throw HTTP exceptions (we deal
        # with status codes instead), if we see an exception it is a problem
        try:
            # Get an auth token for the session
            res = check_response(requests.post(
                '{}/sessions'.format(self.__endpoint),
                auth = (username, password), headers = _REQUIRED_HEADERS
            ))
        except requests.exceptions.RequestException:
            raise ProviderConnectionError('Could not connect to provider')
        auth_token = res.headers['x-vcloud-authorization']
        return VCloudSession(self.__endpoint, auth_token)
        

###############################################################################
###############################################################################


class VCloudSession(Session):
    """
    Session implementation using the vCloud Director API vn5.5
    """
    
    _GUEST_CUSTOMISATION = """#!/bin/sh
if [ x$1 == x"precustomization" ]; then
  echo "Pre-customisation tasks..."
elif [ x$1 == x"postcustomization" ]; then
  echo "Post-customisation tasks..."
  echo "{}" >> /root/.ssh/authorized_keys
fi
"""
    
    def __init__(self, endpoint, auth_token):
        self.__endpoint = endpoint.rstrip('/')
        
        # Create a requests session that can inject the required headers
        self.__session = requests.Session()
        self.__session.headers.update(_REQUIRED_HEADERS)
        self.__session.headers.update({ 'x-vcloud-authorization' : auth_token })
                
    def __getstate__(self):
        """
        Called when the object is pickled
        """
        # All we need to reconstruct the session is the endpoint and auth token
        state = { 'endpoint'   : self.__endpoint }
        if self.__session:
            state['auth_token'] = self.__session.headers['x-vcloud-authorization']
        return state 
        
    def __setstate__(self, state):
        """
        Called when the object is unpickled
        """
        self.__endpoint = state['endpoint']
        # Reconstruct the session object
        if 'auth_token' in state:
            self.__session = requests.Session()
            self.__session.headers.update(_REQUIRED_HEADERS)
            self.__session.headers.update({ 'x-vcloud-authorization' : state['auth_token'] })
        else:
            self.__session = None
                
    def api_request(self, method, path, *args, **kwargs):
        """
        Makes a request to the vCD API at the stored endpoint, injecting auth headers etc.,
        and returns the response if it has a 20x status code
        
        If the status code is not 20x, a relevant exception is thrown
        
        method is the HTTP method to use, and is case-insensitive
        
        path can be relative, in which case the endpoint is prepended, or fully-qualified
        """
        # Deduce the path to use
        if not re.match(r'https?://', path):
            path = '/'.join([self.__endpoint, path.strip('/')])
        # Make the request
        if self.__session is None:
            raise ImplementationError('Session has already been closed')
        func = getattr(self.__session, method.lower(), None)
        if func is None:
            raise ImplementationError('Invalid HTTP method - {}'.format(method))
        # Convert exceptions from requests into cloud service connection errors
        # Since we don't configure requests to throw HTTP exceptions (we deal
        # with status codes instead), if we see an exception it is a problem
        try:
            return check_response(func(path, *args, **kwargs))
        except requests.exceptions.RequestException:
            raise ProviderConnectionError('Could not connect to provider')
    
    def wait_for_task(self, task_href, exception_cls = CloudServiceError):
        """
        Takes a response that contains a task and waits for it to complete
        
        If the task fails to complete successfully, it throws an exception with
        a suitable message
        The exception constructor can be specified using the exception_cls argument
        """
        # Loop until we have success or failure
        while True:
            # Get the current status
            task = ET.fromstring(self.api_request('GET', task_href).text)
            status = task.attrib['status'].lower()
            # Decide if we can exit
            if status == 'success':
                break
            elif status == 'error':
                raise exception_cls('An error occured while performing the action')
            elif status == 'canceled':
                raise exception_cls('Action was cancelled')
            elif status == 'aborted':
                raise exception_cls('Action was aborted by an administrator')
            # Any other statuses, we sleep before fetching the task again
            sleep(_POLL_INTERVAL)
            
    def is_active(self):
        try:
            # Try making an API request
            self.api_request('GET', 'session')
            return True
        except (AuthenticationError, PermissionsError):
            # We only catch authentication-related errors
            return False
            
    def list_images(self):
        # Get a list of uris of catalogs available to the user
        results = ET.fromstring(self.api_request('GET', 'catalogs/query').text)
        cat_refs = [result.attrib['href'] for result in results.findall('vcd:CatalogRecord', _NS)]
        # Now we know the catalogs we have access to, we can get the items
        images = []
        for cat_ref in cat_refs:
            # Query the catalog to find its items
            catalog = ET.fromstring(self.api_request('GET', cat_ref).text)
            items = catalog.findall('.//vcd:CatalogItem', _NS)
            item_ids = [i.attrib['href'].rstrip('/').split('/').pop() for i in items]
            images.extend(self.get_image(id) for id in item_ids)
        return images
        
    def list_machines(self):
        # This will return all the VMs available to the user
        results = ET.fromstring(self.api_request('GET', 'vApps/query').text)
        apps = results.findall('vcd:VAppRecord', _NS)
        machine_ids = [app.attrib['href'].rstrip('/').split('/').pop() for app in apps]
        return [self.get_machine(id) for id in machine_ids]
        
    def get_image(self, image_id):
        # Image IDs are catalog item ids
        item = ET.fromstring(self.api_request('GET', 'catalogItem/{}'.format(image_id)).text)
        name = item.attrib['name']
        description = ''
        try:
            description = item.find('vcd:Description', _NS).text or ''
        except AttributeError:
            pass
        return Image(image_id, name, description)
    
    def __gateway_from_app(self, app):
        """
        Given an ET element representing a vApp, returns an ET element representing the
        edge device for the network to which the primary NIC of the first VM in the vApp
        is connected, or None
        """
        try:
            vdc_ref = app.find('./vcd:Link[@type="application/vnd.vmware.vcloud.vdc+xml"]', _NS)
            vdc = ET.fromstring(self.api_request('GET', vdc_ref.attrib['href']).text)
            gateways_ref = vdc.find('./vcd:Link[@rel="edgeGateways"]', _NS)
            gateways = ET.fromstring(self.api_request('GET', gateways_ref.attrib['href']).text)
            # Assume one gateway per vdc
            gateway_ref = gateways.find('./vcd:EdgeGatewayRecord', _NS)
            return ET.fromstring(self.api_request('GET', gateway_ref.attrib['href']).text)
        except AttributeError:
            return None
        
    def __primary_nic_from_app(self, app):
        """
        Given an ET element representing a vApp, returns an ET element representing the primary
        NIC of the first VM within the vApp, or None
        """
        try:
            vm = app.find('.//vcd:Vm', _NS)
            primary_net_idx = vm.find('.//vcd:PrimaryNetworkConnectionIndex', _NS).text
            return vm.find(
                './/vcd:NetworkConnection[vcd:NetworkConnectionIndex="{}"]'.format(primary_net_idx), _NS
            )
        except AttributeError:
            return None
        
    def __internal_ip_from_app(self, app):
        """
        Given an ET element representing a vApp, returns the internal IP of the primary
        NIC of the first VM within the vApp, or None
        """
        try:
            nic = self.__primary_nic_from_app(app)
            return IPv4Address(nic.find('vcd:IpAddress', _NS).text)
        except AttributeError:
            return None
        
    def get_machine(self, machine_id):
        app = ET.fromstring(self.api_request('GET', 'vApp/{}'.format(machine_id)).text)
        name = app.attrib['name']
        # Convert the integer status to one of the statuses in MachineStatus
        status = _STATUS_MAP.get(int(app.attrib['status']), MachineStatus.UNRECOGNISED)
        # Get the description
        try:
            description = app.find('vcd:Description', _NS).text or ''
        except AttributeError:
            description = ''
        # Convert the string creationDate to a datetime
        # For now, make no attempt to process timezone
        created = datetime.strptime(
            app.find('vcd:DateCreated', _NS).text[:19], '%Y-%m-%dT%H:%M:%S'
        )
        # For the OS, we use the value from the first VM
        try:
            os = app.find('.//vcd:Vm//ovf:OperatingSystemSection/ovf:Description', _NS).text
        except AttributeError:
            os = None
        os = os or 'Unknown'
        # For IP addresses, we use the values from the primary NIC of the first VM
        internal_ip = self.__internal_ip_from_app(app)
        external_ip = None
        # If there is no internal IP, don't even bother trying to find an external one...
        if internal_ip is not None:
            # Try the primary NIC first, since it potentially avoids extra API calls
            try:
                nic = self.__primary_nic_from_app(app)
                external_ip = IPv4Address(nic.find('vcd:ExternalIpAddress', _NS).text)
            except AttributeError:
                pass
            # If no external IP is set in the NIC, try to find a corresponding DNAT rule
            if not external_ip:
                try:
                    gateway = self.__gateway_from_app(app)
                    nat_rules = gateway.findall('.//vcd:NatRule', _NS)
                except AttributeError:
                    nat_rules = []
                for rule in nat_rules:
                    if rule.find('vcd:RuleType', _NS).text.upper() == 'DNAT':
                        # Check if this rule applies to our IP
                        translated = IPv4Address(rule.find('.//vcd:TranslatedIp', _NS).text)
                        if translated == internal_ip:
                            external_ip = IPv4Address(rule.find('.//vcd:OriginalIp', _NS).text)
                            break
        return Machine(machine_id, name, status, description, created, os, internal_ip, external_ip)
        
    def provision_machine(self, image_id, name, description, ssh_key):
        # Image id is the id of a catalog item, so we need to get the vAppTemplate from there
        item = ET.fromstring(self.api_request('GET', 'catalogItem/{}'.format(image_id)).text)
        entity = item.find('.//vcd:Entity[@type="application/vnd.vmware.vcloud.vAppTemplate+xml"]', _NS)
        if entity is None:
            raise ProvisioningError('No vAppTemplate associated with catalogue item')
        template = ET.fromstring(self.api_request('GET', entity.attrib['href']).text)
        # Format the guest customisation script
        # We escape the SSH key before inserting it, in case it has any dodgy characters
        ssh_key = _escape_script(ssh_key.strip())
        # We then escape the whole script again
        # Since the escape function doesn't insert any characters that it escapes, there
        # is no chance of double-escaping things
        script = _escape_script(self._GUEST_CUSTOMISATION.format(ssh_key))
        # Configure each VM contained in the vApp
        vm_configs = []
        # Track the maximum number of NICs for a VM
        # The caller is required to provide a network for each NIC
        n_networks_required = 0
        for vm in template.findall('.//vcd:Vm', _NS):
            # Get all the network connections associated with the VM
            nics = vm.findall('.//vcd:NetworkConnection', _NS)
            if not nics:
                raise ProvisioningError('No network connection section for VM')
            n_nics = len(nics)
            n_networks_required = max(n_networks_required, n_nics)
            vm_configs.append({
                'href'          : vm.attrib['href'],
                'name'          : uuid.uuid4().hex,
                'n_nics'        : n_nics,
                'customisation' : script,
            })
        # Get the VDC to deploy the VM into
        # This is done by selecting the first VCD from the org we are using
        # First, we have to retrieve the org from the session
        session = ET.fromstring(self.api_request('GET', 'session').text)
        org_ref = session.find('.//vcd:Link[@type="application/vnd.vmware.vcloud.org+xml"]', _NS)
        if org_ref is None:
            raise ProvisioningError('Unable to find organisation for user')
        org = ET.fromstring(self.api_request('GET', org_ref.attrib['href']).text)
        # Then get the VDC from the org
        vdc_ref = org.find('.//vcd:Link[@type="application/vnd.vmware.vcloud.vdc+xml"]', _NS)
        if vdc_ref is None:
            raise ProvisioningError('Organisation has no VDCs')
        vdc = ET.fromstring(self.api_request('GET', vdc_ref.attrib['href']).text)
        # Find the available networks from the VDC
        network_refs = vdc.findall(
            './/vcd:AvailableNetworks/vcd:Network[@type="application/vnd.vmware.vcloud.network+xml"]', _NS
        )
        if not network_refs:
            raise ProvisioningError('No networks available in vdc')
        # Check that there are enough networks to satisfy the VMs
        if len(network_refs) < n_networks_required:
            raise ProvisioningError('Not enough networks for number of NICs')
        # Build the XML payload for the request
        payload = _ENV.get_template('ComposeVAppParams.xml').render({
            'appliance': {
                'name'        : name,
                'description' : description,
                'vms'         : vm_configs,
            },
            'networks': [n.attrib for n in network_refs],
        })
        # Send the request to vCD
        # The response is a vapp object
        app = ET.fromstring(self.api_request(
            'POST', '{}/action/composeVApp'.format(vdc.attrib['href']), payload
        ).text)
        # The vapp has a list of tasks associated with it
        # We keep checking that list until it has nothing in it
        while True:
            tasks = app.findall('./vcd:Tasks/vcd:Task', _NS)
            # If there are no tasks, we're done
            if not tasks: break
            # Wait for each task to complete
            for task in tasks:
                self.wait_for_task(task.attrib['href'], ProvisioningError)
            # Refresh our view of the app
            app = ET.fromstring(self.api_request('GET', app.attrib['href']).text)
        return self.get_machine(app.attrib['href'].rstrip('/').split('/').pop())
            
    def expose(self, machine_id):
        # We need to access the edge device that the machine is connected to the internet via
        # To do this, we first get the machine details, then the vdc details
        app = ET.fromstring(self.api_request('GET', 'vApp/{}'.format(machine_id)).text)
        gateway = self.__gateway_from_app(app)
        if gateway is None:
            raise NetworkingError('Could not find edge gateway')
        # Find the uplink gateway interface (assume there is only one)
        uplink = gateway.find('.//vcd:GatewayInterface[vcd:InterfaceType="uplink"]', _NS)
        if uplink is None:
            raise NetworkingError('Edge gateway has no uplink')
        # Find the pool of available external IP addresses, assume only one ip range is defined
        ip_range = uplink.find('.//vcd:IpRange', _NS)
        if ip_range is None:
            raise NetworkingError('Uplink has no IP range defined')
        start_ip = IPv4Address(ip_range.find('./vcd:StartAddress', _NS).text)
        end_ip = IPv4Address(ip_range.find('./vcd:EndAddress', _NS).text)
        ip_pool = set(ip for net in summarize_address_range(start_ip, end_ip) for ip in net)
        # Find our internal IP address
        internal_ip = self.__internal_ip_from_app(app)
        if internal_ip is None:
            raise NetworkingError('Machine has no network connections')
        # Search the existing NAT rules:
        #   1. If we find an existing DNAT rule specifically for our IP, we are done
        #      We assume that all NAT configuration was done by this method, in which case the
        #      DNAT, SNAT and firewall rules should all be set in one call, and so if one
        #      exists, the others also will
        #   2. Remove ip addresses that already have an associated NAT rule from the pool
        nat_rules = gateway.findall('.//vcd:NatRule', _NS)
        for rule in nat_rules:
            rule_type = rule.find('vcd:RuleType', _NS).text.upper()
            if rule_type == 'SNAT':
                # For SNAT rules, we rule out the translated IP
                ip_pool.discard(IPv4Address(rule.find('.//vcd:TranslatedIp', _NS).text))
            elif rule_type == 'DNAT':
                # Check if this rule applies to our IP
                translated = IPv4Address(rule.find('.//vcd:TranslatedIp', _NS).text)
                if translated == internal_ip:
                    # Machine is already exposed, so just return
                    return self.get_machine(machine_id)
                # For DNAT rules, we rule out the original IP
                ip_pool.discard(IPv4Address(rule.find('.//vcd:OriginalIp', _NS).text))
        try:
            ip_use = ip_pool.pop()
        except KeyError:
            raise NetworkingError('No external IP addresses available')
        # Get the current edge gateway configuration
        gateway_config = gateway.find('.//vcd:EdgeGatewayServiceConfiguration', _NS)
        if gateway_config is None:
            raise NetworkingError('No edge gateway configuration exists')
        # Get the NAT service section
        # If there is no NAT service section, create one
        nat_service = gateway_config.find('vcd:NatService', _NS)
        if nat_service is None:
            nat_service = ET.fromstring(_ENV.get_template('NatService.xml').render())
            gateway_config.append(nat_service)
        network = uplink.find('vcd:Network', _NS)
        details = {
            'description' : 'Public facing IP',
            'network' : {
                'href' : network.attrib['href'],
                'name' : network.attrib['name'],
            },
            'external_ip' : ip_use,
            'internal_ip' : internal_ip,
        }
        # Prepend a new SNAT rule to the service
        # The first element is always IsEnabled, so we insert at index 1
        # NOTE: It is important that this is PREPENDED - to ensure that machine appears to
        #       that outside world with a specific IP it must appear before any generic
        #       SNAT rules
        nat_service.insert(1, ET.fromstring(_ENV.get_template('SNATRule.xml').render(details)))
        # Append a new DNAT rule to the service
        nat_service.append(ET.fromstring(_ENV.get_template('DNATRule.xml').render(details)))
        # Get the firewall service and append a new rule
        firewall = gateway_config.find('vcd:FirewallService', _NS)
        if firewall is None:
            raise NetworkingError('No firewall configuration defined')
        firewall.append(ET.fromstring(_ENV.get_template('InboundFirewallRule.xml').render(details)))
        # Make the changes
        edit_url = '{}/action/configureServices'.format(gateway.attrib['href'])
        task = ET.fromstring(self.api_request(
            'POST', edit_url, ET.tostring(gateway_config),
            headers = { 'Content-Type' : 'application/vnd.vmware.admin.edgeGatewayServiceConfiguration+xml' }
        ).text)
        self.wait_for_task(task.attrib['href'], NetworkingError)
        return self.get_machine(machine_id)
    
    def unexpose(self, machine_id):
        # We need to access the edge device that the machine is connected to the internet via
        # To do this, we first get the machine details, then the vdc details
        app = ET.fromstring(self.api_request('GET', 'vApp/{}'.format(machine_id)).text)
        gateway = self.__gateway_from_app(app)
        if gateway is None:
            raise NetworkingError('Could not find edge gateway')
        # Find our internal IP address
        internal_ip = self.__internal_ip_from_app(app)
        if internal_ip is None:
            return self.get_machine(machine_id)
        # Get the current edge gateway configuration
        # If none exists, there aren't any NAT rules
        gateway_config = gateway.find('.//vcd:EdgeGatewayServiceConfiguration', _NS)
        if gateway_config is None:
            return self.get_machine(machine_id)
        # Get the NAT service section
        # If there is no NAT service section, there aren't any NAT rules
        nat_service = gateway_config.find('vcd:NatService', _NS)
        if nat_service is None:
            return self.get_machine(machine_id)
        # Remove any NAT rules from the service that apply specifically to our internal IP
        # As we go, we save the mapped external ip in order to remove firewall rules after
        nat_rules = nat_service.findall('vcd:NatRule', _NS)
        external_ip = None
        for rule in nat_rules:
            rule_type = rule.find('vcd:RuleType', _NS).text.upper()
            if rule_type == 'SNAT':
                # For SNAT rules, we check the original ip
                # The default SNAT rule has a /24 network, so we need to catch the AddressValueError
                try:
                    original = IPv4Address(rule.find('.//vcd:OriginalIp', _NS).text)
                    if original == internal_ip:
                        nat_service.remove(rule)
                        # The external IP is the translated ip, and should NEVER be a network
                        external_ip = IPv4Address(rule.find('.//vcd:TranslatedIp', _NS).text)
                except AddressValueError:
                    # We should only get to here if original ip is a network, which we ignore
                    pass
            elif rule_type == 'DNAT':
                # For DNAT rules, we check the translated ip, which should NEVER be a network
                translated = IPv4Address(rule.find('.//vcd:TranslatedIp', _NS).text)
                if translated == internal_ip:
                    nat_service.remove(rule)
                    # The external ip is the original ip
                    external_ip = IPv4Address(rule.find('.//vcd:OriginalIp', _NS).text)
        # If we didn't find an external ip, the machine must not be exposed
        if external_ip is None:
            return self.get_machine(machine_id)
        # Remove any firewall rules (inbound or outbound) that apply specifically to the ip
        firewall = gateway_config.find('vcd:FirewallService', _NS)
        if firewall is None:
            # If we get to here, we would expect a firewall config to exist
            raise NetworkingError('No firewall configuration defined')
        firewall_rules = firewall.findall('vcd:FirewallRule', _NS)
        for rule in firewall_rules:
            # Try the source and destination ips independently
            # We ignore AddressValueErrors, since the ip couldn't possibly match
            try:
                source_ip = IPv4Address(rule.find('vcd:SourceIp', _NS).text)
                if source_ip == external_ip:
                    firewall.remove(rule)
            except AddressValueError:
                pass
            try:
                dest_ip = IPv4Address(rule.find('vcd:DestinationIp', _NS).text)
                if dest_ip == external_ip:
                    firewall.remove(rule)
            except AddressValueError:
                pass
        # Make the changes
        edit_url = '{}/action/configureServices'.format(gateway.attrib['href'])
        task = ET.fromstring(self.api_request(
            'POST', edit_url, ET.tostring(gateway_config),
            headers = { 'Content-Type' : 'application/vnd.vmware.admin.edgeGatewayServiceConfiguration+xml' }
        ).text)
        self.wait_for_task(task.attrib['href'], NetworkingError)
        return self.get_machine(machine_id)
        
    def start_machine(self, machine_id):
        task = ET.fromstring(self.api_request(
            'POST', 'vApp/{}/power/action/powerOn'.format(machine_id)
        ).text)
        self.wait_for_task(task.attrib['href'], PowerActionError)
        
    def stop_machine(self, machine_id):
        task = ET.fromstring(self.api_request(
            'POST', 'vApp/{}/power/action/powerOff'.format(machine_id)
        ).text)
        self.wait_for_task(task.attrib['href'], PowerActionError)
        
    def restart_machine(self, machine_id):
        task = ET.fromstring(self.api_request(
            'POST', 'vApp/{}/power/action/reset'.format(machine_id)
        ).text)
        self.wait_for_task(task.attrib['href'], PowerActionError)
        
    def destroy_machine(self, machine_id):
        payload = _ENV.get_template('UndeployVAppParams.xml').render()
        task = ET.fromstring(self.api_request(
            'POST', 'vApp/{}/action/undeploy'.format(machine_id), payload
        ).text)
        self.wait_for_task(task.attrib['href'], PowerActionError)
        
    def delete_machine(self, machine_id):
        # Before deleting a machine, we want to remove any exposure to the internet
        # If we don't, we risk exposing to the internet the next machine that picks
        # up the IP address from the pool
        # We don't care too much about the return value
        self.unexpose(machine_id)
        task = ET.fromstring(self.api_request(
            'DELETE', 'vApp/{}'.format(machine_id)
        ).text)
        self.wait_for_task(task.attrib['href'], PowerActionError)
            
    def close(self):
        if self.__session is None:
            # Already closed, so nothing to do
            return
        # Send a request to vCD to kill our session
        # We catch any errors and swallow them, since this could be called when an
        # exception has been thrown by a context manager
        try:
            self.api_request('DELETE', 'session')
            self.__session.close()
        except Exception:
            pass
        finally:
            self.__session = None
