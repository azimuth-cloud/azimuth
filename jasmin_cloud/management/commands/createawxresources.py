"""
Module containing the management command for creating AWX resources required for CaaS.
"""

import re
import time

from django.core.management.base import BaseCommand, CommandError

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PrivateFormat, PublicFormat, NoEncryption

from ...settings import cloud_settings

from ...provider.cluster_engine.awx import api


CAAS_ORGANISATION_NAME = "CaaS"

CAAS_DEPLOY_KEYPAIR_CREDENTIAL_NAME = 'CaaS Deploy Keypair'
CAAS_CREDENTIAL_TYPES = [
    {
        'name': 'OpenStack Token',
        'description': 'Authenticate with an OpenStack cloud using a previously acquired token.',
        'kind': 'cloud',
        'inputs': {
            'fields': [
                {
                    'type': 'string',
                    'id': 'auth_url',
                    'label': 'Auth URL',
                },
                {
                    'type': 'string',
                    'id': 'project_id',
                    'label': 'Project ID',
                },
                {
                    'type': 'string',
                    'id': 'token',
                    'label': 'Token',
                },
            ],
            'required': ['auth_url', 'project_id', 'token'],
        },
        'injectors': {
            'env': {
                'OS_AUTH_TYPE': 'token',
                'OS_AUTH_URL': '{{ auth_url }}',
                'OS_PROJECT_ID': '{{ project_id }}',
                'OS_TOKEN': '{{ token }}',
            },
        },
    },
    {
        'name': CAAS_DEPLOY_KEYPAIR_CREDENTIAL_NAME,
        'description': 'SSH keypair used for CaaS deployments.',
        'kind': 'cloud',
        'inputs': {
            'fields': [
                {
                    'type': 'string',
                    'id': 'public_key',
                    'label': 'Public key',
                },
                {
                    'type': 'string',
                    'id': 'private_key',
                    'label': 'Private key',
                    'secret': True,
                    'multiline': True,
                },
            ],
            'required': ['public_key', 'private_key'],
        },
        'injectors': {
            # Inject the private key as a file
            'file': {
                'template': '{{ private_key }}',
            },
            'extra_vars': {
                # Set a variable pointing to the private key file
                'cluster_ssh_private_key_file': '{{ tower.filename }}',
                # Also set a variable containing the public key
                'cluster_deploy_ssh_public_key': '{{ public_key }}',
            },
        },
    },
]


class Command(BaseCommand):
    """
    Management command for creating the AWX resources required by Cluster-as-a-Service.
    """
    help = 'Creates AWX resources required by Cluster-as-a-Service.'

    def ensure_credential_type(self, connection, ct_spec):
        """
        Ensures that given credential type exists.
        """
        ct = connection.credential_types.find_by_name(ct_spec['name'])
        if ct:
            ct = ct._update(**ct_spec)
        else:
            ct = connection.credential_types.create(**ct_spec)
        return ct

    def ensure_credential_types(self, connection):
        """
        Ensures that the credential types that are used by Cluster-as-a-Service exist.
        """
        return {
            ct['name']: self.ensure_credential_type(connection, ct)
            for ct in CAAS_CREDENTIAL_TYPES
        }

    def ensure_organisation(self, connection):
        """
        Ensures that the CaaS organisation exists.
        """
        organisation = connection.organisations.find_by_name(CAAS_ORGANISATION_NAME)
        if not organisation:
            organisation = connection.organisations.create(name = CAAS_ORGANISATION_NAME)
        return organisation

    def ensure_galaxy_credential(self, connection, organisation):
        """
        Ensure that the organisation has a Galaxy credential.

        This is important to allow roles to be downloaded.
        """
        # Get the galaxy credential type
        galaxy_ct = connection.credential_types.find_by_kind("galaxy")
        # Get the galaxy credential associated with the org
        credential = next(
            connection.credentials.all(
                organization = organisation.id,
                credential_type = galaxy_ct.id
            ),
            None
        )
        if not credential:
            credential = connection.credentials.create(
                name = f"{CAAS_ORGANISATION_NAME} Galaxy Credential",
                credential_type = galaxy_ct.id,
                organization = organisation.id,
                inputs = dict(url = "https://galaxy.ansible.com")
            )
        # Weirdly, although the credential is created under the organisation, we also
        # need to make this association
        connection.api_post(
            f"/organizations/{organisation.id}/galaxy_credentials/",
            json = dict(id = credential.id)
        )
        return credential

    def ensure_execution_environment(self, connection, organisation):
        """
        Ensure that the CaaS execution environment exists.
        """
        ee_name = f"{CAAS_ORGANISATION_NAME} EE"
        ee = connection.execution_environments.find_by_name(ee_name)
        if ee:
            ee = ee._update(image = cloud_settings.AWX.EXECUTION_ENVIRONMENT_IMAGE)
        else:
            ee = connection.execution_environments.create(
                name = ee_name,
                organization = organisation.id,
                image = cloud_settings.AWX.EXECUTION_ENVIRONMENT_IMAGE
            )
        # Set the execution environment as the default
        connection.api_patch("/settings/system/", json = { "DEFAULT_EXECUTION_ENVIRONMENT": ee.id })
        return ee

    def ensure_caas_deploy_keypair(self, connection, organisation, ct):
        """
        Ensure that a CaaS deploy keypair with the expected name exists.
        """
        credential = connection.credentials.find_by_name(CAAS_DEPLOY_KEYPAIR_CREDENTIAL_NAME)
        if not credential:
            # Generate a keypair to use
            keypair = Ed25519PrivateKey.generate()
            private_key = (
                keypair
                    .private_bytes(Encoding.PEM, PrivateFormat.OpenSSH, NoEncryption())
                    .decode()
            )
            public_key = (
                keypair
                    .public_key()
                    .public_bytes(Encoding.OpenSSH, PublicFormat.OpenSSH)
                    .decode()
            )
            credential = connection.credentials.create(
                name = CAAS_DEPLOY_KEYPAIR_CREDENTIAL_NAME,
                credential_type = ct.id,
                organization = organisation.id,
                inputs = dict(public_key = public_key, private_key = private_key)
            )
        return credential

    def ensure_template_inventory(self, connection, organisation):
        """
        Ensures that the template inventory used by Cluster-as-a-Service exists.
        """
        inventory_name = cloud_settings.AWX.TEMPLATE_INVENTORY
        # Ensure that the template inventory exists and is in the correct organisation
        inventory = connection.inventories.find_by_name(inventory_name)
        if inventory:
            # Make sure the inventory is in the correct organisation
            inventory = inventory._update(organization = organisation.id)
        else:
            inventory = connection.inventories.create(
                name = inventory_name,
                organization = organisation.id
            )
        # Create the openstack group
        group = inventory.groups.find_by_name('openstack')
        if not group:
            group = inventory.groups.create(name = 'openstack')
        # Create localhost in the inventory and group
        localhost = group.hosts.find_by_name("localhost")
        if localhost:
            localhost = localhost._update(inventory = inventory.id)
        else:
            localhost = group.hosts.create(name = "localhost", inventory = inventory.id)
        # Update the variables associated with localhost
        localhost.variable_data._update(
            dict(
                ansible_host = '127.0.0.1',
                ansible_connection = 'local',
                ansible_python_interpreter = '{{ ansible_playbook_python }}',
            )
        )

    def ensure_project(self, connection, organisation, project_spec):
        """
        Ensure that the given project exists.
        """
        project = connection.projects.find_by_name(project_spec['NAME'])
        params = dict(
            description = project_spec['METADATA_ROOT'],
            scm_type = 'git',
            scm_url = project_spec['GIT_URL'],
            scm_branch = project_spec['GIT_VERSION'],
            organization = organisation.id,
            scm_update_on_launch = True
        )
        if project:
            project = project._update(**params)
        else:
            project = connection.projects.create(name = project_spec['NAME'], **params)
        # Wait for the project to move into the successful state
        while project.status != "successful":
            time.sleep(3)
            project = connection.projects.get(project.id, force = True)
        return project

    def ensure_projects(self, connection, organisation):
        """
        Ensure that the configured projects exist.
        """
        return [
            self.ensure_project(connection, organisation, project)
            for project in cloud_settings.AWX.DEFAULT_PROJECTS
        ]

    def ensure_job_template_for_playbook(self, connection, project, playbook):
        """
        Ensures that a job template exists for the given project and playbook.
        """
        # Sanitise any weird characters in the playbook name
        template_name = re.sub(
            '[^a-zA-Z0-9-]+',
            '-',
            playbook.removesuffix('.yml')
        )
        # The metadata root should be in the project description
        # The metadata file should be named after the playbook
        metadata_url = f"{project.description.rstrip('/')}/{playbook}"
        job_template = connection.job_templates.find_by_name(template_name)
        params = dict(
            description = metadata_url,
            job_type = 'run',
            project = project.id,
            playbook = playbook,
            ask_inventory_on_launch = True,
            allow_simultaneous = True
        )
        if job_template:
            job_template = job_template._update(**params)
        else:
            job_template = connection.job_templates.create(name = template_name, **params)
        return job_template

    def ensure_job_templates_for_project(self, connection, project):
        """
        Ensures that a job template exists for each playbook in a project.
        """
        return [
            self.ensure_job_template_for_playbook(connection, project, playbook)
            for playbook in project.playbooks._fetch()
        ]

    def ensure_job_templates(self, connection, projects):
        """
        Ensure that a job template exists for each playbook in each project.
        """
        return [
            job_template
            for project in projects
            for job_template in self.ensure_job_templates_for_project(connection, project)
        ]

    def handle(self, *args, **options):
        connection = api.Connection(
            cloud_settings.AWX.URL,
            cloud_settings.AWX.ADMIN_USERNAME,
            cloud_settings.AWX.ADMIN_PASSWORD,
            cloud_settings.AWX.VERIFY_SSL
        )
        credential_types = self.ensure_credential_types(connection)
        organisation = self.ensure_organisation(connection)
        self.ensure_galaxy_credential(connection, organisation)
        self.ensure_caas_deploy_keypair(
            connection,
            organisation,
            credential_types[CAAS_DEPLOY_KEYPAIR_CREDENTIAL_NAME]
        )
        self.ensure_execution_environment(connection, organisation)
        self.ensure_template_inventory(connection, organisation)
        projects = self.ensure_projects(connection, organisation)
        self.ensure_job_templates(connection, projects)
