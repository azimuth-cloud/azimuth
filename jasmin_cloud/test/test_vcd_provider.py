"""
Integration tests for jasmin_cloud.cloudservices.vcloud

This runs against a real vCloud Director instance
"""

__author__ = "Matt Pryor"
__copyright__ = "Copyright 2015 UK Science and Technology Facilities Council"


import unittest, uuid

from .util import IntegrationTest
from . import vcd_settings as settings

from ..cloudservices import MachineStatus, CloudServiceError
from ..cloudservices.vcloud import VCloudProvider


class TestVcdProvider(unittest.TestCase, IntegrationTest):
    """
    Test case for vCloud Director provider
    """
    
    def steps(self):
        return (
            'create_session',
            'get_known_image',
            'provision_machine_from_image',
            'check_machine_in_list',
            'create_image_from_machine',
            'check_image_in_list',
            'provision_machine_from_image',
            'check_machine_in_list',
            'expose_machine',
            'unexpose_machine',
            'start_machine',
            'restart_machine',
            'stop_machine',
            'delete_machine',
            'close_session',
        )
        
    def create_session(self, notused):
        """
        Creates a session and tests that it is active
        """
        self.session = VCloudProvider(settings.endpoint).\
                         new_session(settings.username, settings.password)
        self.assertTrue(self.session.poll())
        
    def get_known_image(self, notused):
        """
        Uses the current session to get a known image and returns it
        """
        image = self.session.get_image(settings.image_uuid)
        # The known image should be public
        self.assertTrue(image.is_public)
        return image
        
    def provision_machine_from_image(self, image):
        """
        Uses the current session to provision a machine from the given image
        and returns the provisioned machine
        
        If the image is not the known image, it is deleted
        """
        machine = self.session.provision_machine(
            image.id, uuid.uuid4().hex, 'A description', '', ''
        )
        # Machines should be created in an off state
        self.assertIs(machine.status, MachineStatus.POWERED_OFF)
        # Check the provisioned machine has an internal IP
        self.assertIsNotNone(machine.internal_ip)
        # Delete the image if it is not the known image
        if image.id != settings.image_uuid:
            self.session.delete_image(image.id)
        return machine
        
    def check_machine_in_list(self, machine):
        """
        Uses the session to check that the given machine is in the list of
        available machines before returning the machine
        """
        # Input is the provisioned machine
        machines = self.session.list_machines()
        self.assertTrue(any(m.id == machine.id for m in machines))
        return machine
    
    def create_image_from_machine(self, machine):
        """
        Uses the session to create an image from the given machine and returns
        the created image
        
        The source machine is deleted
        """
        image = self.session.image_from_machine(
            machine.id, uuid.uuid4().hex, 'A description'
        )
        # This image should be private
        self.assertFalse(image.is_public)
        # Delete the source machine
        self.session.delete_machine(machine.id)
        return image
    
    def check_image_in_list(self, image):
        """
        Uses the session to check that the given image is in the list of available
        images before returning the image
        """
        images = self.session.list_images()
        self.assertGreater(len(images), 0)
        self.assertTrue(any(i.id == image.id for i in images))
        return image
    
    def expose_machine(self, machine):
        """
        Uses the session to expose the machine before returning it
        """
        # Input is the machine
        # First check it has no external IP
        self.assertIsNone(machine.external_ip)
        machine = self.session.expose_machine(machine.id)
        self.assertIsNotNone(machine.external_ip)
        return machine
    
    def unexpose_machine(self, machine):
        """
        Uses the session to unexpose the machine before returning it
        """
        # Input is the machine
        # First check it has no external IP
        self.assertIsNotNone(machine.external_ip)
        machine = self.session.unexpose_machine(machine.id)
        self.assertIsNone(machine.external_ip)
        return machine
    
    def start_machine(self, machine):
        """
        Uses the session to start the machine that it should receive as input
        and returns the machine
        """
        # Input is the machine
        self.session.start_machine(machine.id)
        # Fetch the machine and check it is on
        machine = self.session.get_machine(machine.id)
        self.assertIs(machine.status, MachineStatus.POWERED_ON)
        return machine
    
    def restart_machine(self, machine):
        """
        Uses the session to restart the machine that it should recieve as input
        and returns the machine
        """
        # Input is the machine
        self.session.restart_machine(machine.id)
        # Fetch the machine and check it is on
        machine = self.session.get_machine(machine.id)
        self.assertIs(machine.status, MachineStatus.POWERED_ON)
        return machine
    
    def stop_machine(self, machine):
        """
        Uses the session to stop the machine that it should recieve as input
        and returns the machine
        """
        # Input is the machine
        self.session.destroy_machine(machine.id)
        # Fetch the machine and check it is off
        machine = self.session.get_machine(machine.id)
        self.assertIs(machine.status, MachineStatus.POWERED_OFF)
        return machine
        
    def delete_machine(self, machine):
        """
        Uses the session to delete the machine that it should recieve as input
        """
        # Input is the machine to delete
        self.session.delete_machine(machine.id)
        
    def close_session(self, notused):
        """
        Closes the session and checks that it is no longer active
        """
        self.session.close()
        self.assertRaises(CloudServiceError, self.session.poll)
        self.session = None
    