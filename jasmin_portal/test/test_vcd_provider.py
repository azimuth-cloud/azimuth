"""
Integration tests for jasmin_portal.cloudservices.vcloud

This runs against a real vCloud Director instance
"""

__author__ = "Matt Pryor"
__copyright__ = "Copyright 2015 UK Science and Technology Facilities Council"


import unittest, uuid

from jasmin_portal.test.util import IntegrationTest
from jasmin_portal.test.vcd_settings import endpoint, username, password

from jasmin_portal.cloudservices import MachineStatus
from jasmin_portal.cloudservices.vcloud import VCloudProvider


class TestVcdProvider(unittest.TestCase, IntegrationTest):
    """
    Test case for vCloud Director provider
    """
    
    def steps(self):
        return (
            'create_session',
            'list_images',
            'provision_machine',
            'list_machines',
            'expose_machine',
            'unexpose_machine',
            'start_machine',
            'restart_machine',
            'stop_machine',
            'delete_machine',
            'close_session',
        )
        
    def create_session(self, input):
        """
        Creates a session and tests that it is active
        """
        p = VCloudProvider(endpoint)
        self.session = p.new_session(username, password)
        self.assertTrue(self.session.is_active())
        
    def list_images(self, input):
        """
        Uses the current session to list images, and returns the list
        """
        images = self.session.list_images()
        self.assertGreater(len(images), 0)
        # Assert that the image we want to use is in the list
        self.assertTrue(any(i.name == "ssh_bastion" for i in images))
        return images
    
    def provision_machine(self, input):
        """
        Uses the current session to provision a machine from a template
        and returns the provisioned machine
        """
        # The input should be the list of images
        bastion_image = next(i for i in input if i.name == "ssh_bastion")
        machine = self.session.provision_machine(
            bastion_image.id, uuid.uuid4().hex, 'A description', ''
        )
        # Machines should be created in an off state
        self.assertIs(machine.status, MachineStatus.POWERED_OFF)
        # Check the provisioned machine has an internal IP
        self.assertIsNotNone(machine.internal_ip)
        return machine
        
    def list_machines(self, input):
        """
        Uses the session to list the available machines and checks that the
        provisioned machine is present in the list, before returning the
        machine
        """
        # Input is the provisioned machine
        machines = self.session.list_machines()
        self.assertTrue(any(m.name == input.name for m in machines))
        return input
    
    def expose_machine(self, input):
        """
        Uses the session to expose the machine before returning it
        """
        # Input is the machine
        # First check it has no external IP
        self.assertIsNone(input.external_ip)
        machine = self.session.expose(input.id)
        self.assertIsNotNone(machine.external_ip)
        return machine
    
    def unexpose_machine(self, input):
        """
        Uses the session to unexpose the machine before returning it
        """
        # Input is the machine
        # First check it has no external IP
        self.assertIsNotNone(input.external_ip)
        machine = self.session.unexpose(input.id)
        self.assertIsNone(machine.external_ip)
        return machine
    
    def start_machine(self, input):
        """
        Uses the session to start the machine that it should recieve as input
        and returns the machine
        """
        # Input is the machine
        self.session.start_machine(input.id)
        # Fetch the machine and check it is on
        machine = self.session.get_machine(input.id)
        self.assertIs(machine.status, MachineStatus.POWERED_ON)
        return machine
    
    def restart_machine(self, input):
        """
        Uses the session to restart the machine that it should recieve as input
        and returns the machine
        """
        # Input is the machine
        self.session.restart_machine(input.id)
        # Fetch the machine and check it is on
        machine = self.session.get_machine(input.id)
        self.assertIs(machine.status, MachineStatus.POWERED_ON)
        return machine
    
    def stop_machine(self, input):
        """
        Uses the session to stop the machine that it should recieve as input
        and returns the machine
        """
        # Input is the machine
        self.session.destroy_machine(input.id)
        # Fetch the machine and check it is off
        machine = self.session.get_machine(input.id)
        self.assertIs(machine.status, MachineStatus.POWERED_OFF)
        return machine
        
    def delete_machine(self, input):
        """
        Uses the session to delete the machine that it should recieve as input
        """
        # Input is the machine to delete
        self.session.delete_machine(input.id)
        
    def close_session(self, input):
        """
        Closes the session and checks that it is no longer active
        """
        self.session.close()
        self.assertFalse(self.session.is_active())
        self.session = None
    