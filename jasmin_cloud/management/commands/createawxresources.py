"""
Module containing the management command for creating AWX resources required for CaaS.
"""

import re
import time

from django.core.management.base import BaseCommand

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    PrivateFormat,
    PublicFormat,
    NoEncryption
)

import rackit

from ...settings import cloud_settings
from ...provider.cluster_engine.awx.engine import CREDENTIAL_TYPE_NAMES
from ...provider.cluster_engine.awx import api


CAAS_ORGANISATION_NAME = "CaaS"

CAAS_DEPLOY_KEYPAIR_CREDENTIAL_NAME = 'CaaS Deploy Keypair'
CAAS_CREDENTIAL_TYPES = [
    {
        'name': CREDENTIAL_TYPE_NAMES['openstack_token'],
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
        'name': CREDENTIAL_TYPE_NAMES['openstack_application_credential'],
        'description': 'Authenticate with an OpenStack cloud using an application credential.',
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
                    'id': 'application_credential_id',
                    'label': 'Application Credential ID',
                },
                {
                    'type': 'string',
                    'id': 'application_credential_secret',
                    'label': 'Application Credential Secret',
                    'secret': True,
                },
            ],
            'required': [
                'auth_url',
                'application_credential_id',
                'application_credential_secret',
            ],
        },
        'injectors': {
            'env': {
                'OS_IDENTITY_API_VERSION': '3',
                'OS_AUTH_TYPE': 'v3applicationcredential',
                'OS_AUTH_URL': '{{ auth_url }}',
                'OS_APPLICATION_CREDENTIAL_ID': '{{ application_credential_id }}',
                'OS_APPLICATION_CREDENTIAL_SECRET': '{{ application_credential_secret }}',
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

    def wait_for_awx(self, connection):
        """
        Waits for the AWX API to become available before returning.
        """
        self.stdout.write('Waiting for AWX API to become available...')
        # Just try to fetch the API information until it loads properly
        while True:
            try:
                connection.api_get("/")
            except (rackit.ConnectionError, rackit.ApiError) as exc:
                # If there is an error response, we need to continue
                pass
            else:
                break
            time.sleep(5)

    def ensure_credential_type(self, connection, ct_spec):
        """
        Ensures that given credential type exists.
        """
        ct = connection.credential_types.find_by_name(ct_spec['name'])
        if ct:
            self.stdout.write(f"Updating credential type '{ct_spec['name']}'")
            ct = ct._update(**ct_spec)
        else:
            self.stdout.write(f"Creating credential type '{ct_spec['name']}'")
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
        if organisation:
            self.stdout.write(f"Found existing organisation '{CAAS_ORGANISATION_NAME}'")
        else:
            self.stdout.write(f"Creating organisation '{CAAS_ORGANISATION_NAME}'")
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
        if credential:
            self.stdout.write("Found existing Galaxy credential for organisation")
        else:
            self.stdout.write("Creating Galaxy credential for organisation")
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
            self.stdout.write(f"Updating execution environment '{ee_name}'")
            ee = ee._update(image = cloud_settings.AWX.EXECUTION_ENVIRONMENT_IMAGE)
        else:
            self.stdout.write(f"Creating execution environment '{ee_name}'")
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
        if credential:
            self.stdout.write("Found existing CaaS deploy keypair credential")
        else:
            self.stdout.write("Generating ed25519 key pair")
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
            self.stdout.write("Creating CaaS deploy keypair credential")
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
            self.stdout.write(f"Updating inventory '{inventory_name}'")
            # Make sure the inventory is in the correct organisation
            inventory = inventory._update(organization = organisation.id)
        else:
            self.stdout.write(f"Creating inventory '{inventory_name}'")
            inventory = connection.inventories.create(
                name = inventory_name,
                organization = organisation.id
            )
        # Create the openstack group
        group = inventory.groups.find_by_name('openstack')
        if group:
            self.stdout.write("Found existing inventory group 'openstack'")
        else:
            self.stdout.write("Creating inventory group 'openstack'")
            group = inventory.groups.create(name = 'openstack')
        # Create localhost in the inventory and group
        localhost = group.hosts.find_by_name("localhost")
        if localhost:
            self.stdout.write("Found existing localhost for inventory")
        else:
            self.stdout.write("Creating localhost for inventory")
            localhost = group.hosts.create(name = "localhost", inventory = inventory.id)
        # Update the variables associated with localhost
        self.stdout.write("Updating inventory variables for localhost")
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
            self.stdout.write(f"Updating project '{project.name}'")
            project = project._update(**params)
        else:
            self.stdout.write(f"Creating project '{project_spec['NAME']}'")
            project = connection.projects.create(name = project_spec['NAME'], **params)
        # Wait for the project to move into the successful state
        self.stdout.write(f"Waiting for project to become available...")
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

    def ensure_job_template_for_playbook(self, connection, project, playbook, deploy_keypair_cred):
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
            # We will add the deploy keypair as a default credential,
            # but also allow extra credentials to be added
            ask_credential_on_launch = True,
            ask_inventory_on_launch = True,
            ask_variables_on_launch = True,
            allow_simultaneous = True
        )
        if job_template:
            self.stdout.write(f"Updating job template '{template_name}'")
            job_template = job_template._update(**params)
        else:
            self.stdout.write(f"Creating job template '{template_name}'")
            job_template = connection.job_templates.create(name = template_name, **params)
        existing_creds = [c['id'] for c in job_template.summary_fields['credentials']]
        if deploy_keypair_cred.id not in existing_creds:
            self.stdout.write("Associating CaaS deploy keypair with job template")
            # Associate the deploy keypair credential with the job template
            connection.api_post(
                f"/job_templates/{job_template.id}/credentials/",
                json = dict(id = deploy_keypair_cred.id)
            )
        return job_template

    def ensure_job_templates_for_project(self, connection, project, deploy_keypair_cred):
        """
        Ensures that a job template exists for each playbook in a project.
        """
        return [
            self.ensure_job_template_for_playbook(
                connection,
                project,
                playbook,
                deploy_keypair_cred
            )
            for playbook in project.playbooks._fetch()
        ]

    def ensure_job_templates(self, connection, projects, deploy_keypair_cred):
        """
        Ensure that a job template exists for each playbook in each project.
        """
        return [
            job_template
            for project in projects
            for job_template in self.ensure_job_templates_for_project(
                connection,
                project,
                deploy_keypair_cred
            )
        ]

    def handle(self, *args, **options):
        connection = api.Connection(
            cloud_settings.AWX.URL,
            cloud_settings.AWX.ADMIN_USERNAME,
            cloud_settings.AWX.ADMIN_PASSWORD,
            cloud_settings.AWX.VERIFY_SSL
        )
        self.wait_for_awx(connection)
        credential_types = self.ensure_credential_types(connection)
        organisation = self.ensure_organisation(connection)
        self.ensure_galaxy_credential(connection, organisation)
        deploy_keypair_cred = self.ensure_caas_deploy_keypair(
            connection,
            organisation,
            credential_types[CAAS_DEPLOY_KEYPAIR_CREDENTIAL_NAME]
        )
        self.ensure_execution_environment(connection, organisation)
        self.ensure_template_inventory(connection, organisation)
        projects = self.ensure_projects(connection, organisation)
        self.ensure_job_templates(connection, projects, deploy_keypair_cred)
