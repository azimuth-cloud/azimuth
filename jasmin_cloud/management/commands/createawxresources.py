"""
Module containing the management command for creating AWX resources required for CaaS.
"""

from django.core.management.base import BaseCommand, CommandError

from ...settings import cloud_settings

from ...provider.cluster_engine.awx import api


CAAS_ORGANISATION_NAME = "CaaS"

CAAS_EXECUTION_ENVIRONMENT_NAME = "CaaS EE"

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
]


class Command(BaseCommand):
    """
    Management command for creating the AWX resources required by Cluster-as-a-Service.
    """
    help = 'Creates AWX resources required by Cluster-as-a-Service.'

    def ensure_execution_environment(self, connection):
        """
        Ensure that the CaaS execution environment exists.
        """
        ee = connection.execution_environments.find_by_name(CAAS_EXECUTION_ENVIRONMENT_NAME)
        if ee:
            ee._update(image = cloud_settings.AWX.EXECUTION_ENVIRONMENT_IMAGE)
        else:
            ee = connection.execution_environments.create(
                name = CAAS_EXECUTION_ENVIRONMENT_NAME,
                image = cloud_settings.AWX.EXECUTION_ENVIRONMENT_IMAGE
            )
        # Set the execution environment as the default
        connection.api_patch("/settings/system/", json = { "DEFAULT_EXECUTION_ENVIRONMENT": ee.id })
        return ee

    def ensure_credential_types(self, connection):
        """
        Ensures that the credential types that are used by Cluster-as-a-Service exist.
        """
        for ct_spec in CAAS_CREDENTIAL_TYPES:
            ct = connection.credential_types.find_by_name(ct_spec['name'])
            if ct:
                ct._update(**ct_spec)
            else:
                connection.credential_types.create(**ct_spec)

    def ensure_organisation(self, connection):
        """
        Ensures that the CaaS organisation exists.
        """
        organisation = connection.organisations.find_by_name(CAAS_ORGANISATION_NAME)
        if not organisation:
            organisation = connection.organisations.create(name = CAAS_ORGANISATION_NAME)
        return organisation

    def ensure_template_inventory(self, connection, organisation):
        """
        Ensures that the template inventory used by Cluster-as-a-Service exists.
        """
        inventory_name = cloud_settings.AWX.TEMPLATE_INVENTORY
        # Ensure that the template inventory exists and is in the correct organisation
        inventory = connection.inventories.find_by_name(inventory_name)
        if inventory:
            # Make sure the inventory is in the correct organisation
            inventory._update(organization = organisation.id)
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
            localhost._update(inventory = inventory.id)
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
            scm_type = 'git',
            scm_url = project_spec['GIT_URL'],
            scm_branch = project_spec['GIT_VERSION'],
            organization = organisation.id,
            scm_update_on_launch = True
        )
        if project:
            project._update(**params)
            return project
        else:
            return connection.projects.create(name = project_spec['NAME'], **params)

    def ensure_projects(self, connection, organisation):
        """
        Ensure that the configured projects exist.
        """
        return {
            project['NAME']: self.ensure_project(connection, organisation, project)
            for project in cloud_settings.AWX.DEFAULT_PROJECTS
        }

    def handle(self, *args, **options):
        connection = api.Connection(
            cloud_settings.AWX.URL,
            cloud_settings.AWX.ADMIN_USERNAME,
            cloud_settings.AWX.ADMIN_PASSWORD,
            cloud_settings.AWX.VERIFY_SSL
        )
        self.ensure_execution_environment(connection)
        self.ensure_credential_types(connection)
        organisation = self.ensure_organisation(connection)
        self.ensure_template_inventory(connection, organisation)
        self.ensure_projects(connection, organisation)
