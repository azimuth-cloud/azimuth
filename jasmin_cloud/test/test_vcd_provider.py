"""
Integration tests for jasmin_cloud.cloudservices.vcloud.

This runs against a real vCloud Director instance.

The tests are designed to run against an unmanaged organisation.
"""
from jasmin_cloud.test.vcd_settings import known_image

__author__ = "Matt Pryor"
__copyright__ = "Copyright 2015 UK Science and Technology Facilities Council"


import unittest, uuid
from collections import OrderedDict

from .util import IntegrationTest
from . import vcd_settings as settings

from ..cloudservices import NATPolicy, MachineStatus, CloudServiceError, PermissionsError
from ..cloudservices.vcloud import VCloudSession


class TestVcdProvider(unittest.TestCase, IntegrationTest):
    """
    Test case for vCloud Director provider
    """
    
    def steps(self):
        return OrderedDict((
            ('create_session', self.create_session),
            ('get_known_image', self.get_known_image),
            # Provision a machine (uses False for expose)
            #   This should be overridden by the NAT policy
            ('provision_exposed_machine', self.provision_exposed_machine),
            ('machine_in_list', self.machine_in_list),
            ('image_from_machine', self.image_from_machine),
            ('image_in_list', self.image_in_list),
            # Provision a machine using the created image (again, uses False for expose)
            #   This time, the NAT policy should be USER, so there should be no
            #   external ip
            ('provision_machine', self.provision_machine),
            ('machine_in_list_', self.machine_in_list),
            ('start_machine', self.start_machine),
            ('restart_machine', self.restart_machine),
            ('stop_machine', self.stop_machine),
            ('delete_machine', self.delete_machine),
            ('close_session', self.close_session),
        ))
        
    def create_session(self, notused):
        """
        Creates a session and tests that it is active
        """
        self.session = VCloudSession(settings.endpoint, settings.username, settings.password)
        self.assertTrue(self.session.poll())
        
    def get_known_image(self, notused):
        """
        Uses the current session to get a known image and returns it
        """
        image = next(i for i in self.session.list_images() if i.name == known_image)
        # The known image should be public
        self.assertTrue(image.is_public)
        # The known image should have a NAT policy of USER
        self.assertEqual(image.nat_policy, NATPolicy.USER)
        return image
        
    def provision_exposed_machine(self, image):
        """
        Uses the current session to provision a machine using the given image and
        returns the provisioned machine.
        
        Uses a value of True for expose.
        
        Deletes the image if it is not the known image.
        """
        machine = self.session.provision_machine(
            image.id, uuid.uuid4().hex, 'A description', '', True
        )
        # Machines should be created in an off state
        self.assertIs(machine.status, MachineStatus.POWERED_OFF)
        # Check the provisioned machine has an internal IP
        self.assertIsNotNone(machine.internal_ip)
        # Check the provisioned machine has an external IP
        self.assertIsNotNone(machine.external_ip)
        # Delete the image if it is not the known image
        if image.name != settings.known_image:
            self.session.delete_image(image.id)
        return machine
        
    def provision_machine(self, image):
        """
        Uses the current session to provision a machine using the given image and
        returns the provisioned machine.
        
        Uses a value of False for expose.
        
        Deletes the image if it is not the known image.
        """
        machine = self.session.provision_machine(
            image.id, uuid.uuid4().hex, 'A description', '', False
        )
        # Machines should be created in an off state
        self.assertIs(machine.status, MachineStatus.POWERED_OFF)
        # Check the provisioned machine has an internal IP
        self.assertIsNotNone(machine.internal_ip)
        # Check the provisioned machine has no external IP
        self.assertIsNone(machine.external_ip)
        # Delete the image if it is not the known image
        if image.name != settings.known_image:
            self.session.delete_image(image.id)
        return machine
        
    def machine_in_list(self, machine):
        """
        Uses the session to check that the given machine is in the list of
        available machines before returning the machine
        """
        # Input is the provisioned machine
        machines = self.session.list_machines()
        self.assertTrue(any(m.id == machine.id for m in machines))
        return machine
    
    def image_from_machine(self, machine):
        """
        Uses the session to create an image from the given machine and returns
        the created image
        """
        image = self.session.image_from_machine(
            machine.id, uuid.uuid4().hex, 'A description'
        )
        # This image should be private
        self.assertFalse(image.is_public)
        # The machine should have a NAT policy of USER
        self.assertEqual(image.nat_policy, NATPolicy.USER)
        # Check that the source machine was deleted
        machines = self.session.list_machines()
        self.assertFalse(any(m.id == machine.id for m in machines))
        return image
    
    def image_in_list(self, image):
        """
        Uses the session to check that the given image is in the list of available
        images before returning the image
        """
        images = self.session.list_images()
        self.assertGreater(len(images), 0)
        self.assertTrue(any(i.id == image.id for i in images))
        return image
    
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
        self.session.stop_machine(machine.id)
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
        # vCD raises a permissions error if an invalid id is given to avoid exposing
        # details about what is a real id
        with self.assertRaises(PermissionsError):
            self.session.get_machine(machine.id)
        
    def close_session(self, notused):
        """
        Closes the session and checks that it is no longer active
        """
        self.session.close()
        with self.assertRaises(CloudServiceError):
            self.session.poll()
        self.session = None
    