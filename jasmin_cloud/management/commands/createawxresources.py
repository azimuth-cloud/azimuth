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
        'injectors': {
            'env': {
                'OS_AUTH_TYPE': 'token',
                'OS_AUTH_URL': '{{ os_auth_url }}',
                'OS_PROJECT_ID': '{{ os_project_id }}',
                'OS_TOKEN': '{{ os_token }}',
            },
        },
        'inputs': {
            'fields': [
                {
                    'type': 'string',
                    'id': 'os_auth_url',
                    'label': 'OpenStack Auth URL',
                },
                {
                    'type': 'string',
                    'id': 'os_project_id',
                    'label': 'OpenStack Project ID',
                },
                {
                    'type': 'string',
                    'id': 'os_token',
                    'label': 'OpenStack Token',
                },
            ],
            'required': [
                'os_auth_url',
                'os_project_id',
                'os_token',
            ],
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
            ee._update(
                image = cloud_settings.AWX.EXECUTION_ENVIRONMENT_IMAGE,
                pull = 'always'
            )
        else:
            ee = connection.execution_environments.create(
                name = CAAS_EXECUTION_ENVIRONMENT_NAME,
                image = cloud_settings.AWX.EXECUTION_ENVIRONMENT_IMAGE,
                pull = 'always'
            )
        return ee

    def ensure_organisation(self, connection):
        """
        Ensures that the CaaS organisation exists.
        """
        organisation = connection.organisations.find_by_name(CAAS_ORGANISATION_NAME)
        if not organisation:
            organisation = connection.organisations.create(name = CAAS_ORGANISATION_NAME)
        return organisation

    def ensure_credential_types(self, connection):
        """
        Ensure that the credential types that are used by Cluster-as-a-Service exist.
        """
        for ct_spec in CAAS_CREDENTIAL_TYPES:
            ct = connection.credential_types.find_by_name(ct_spec['name'])
            if ct:
                ct._update(**ct_spec)
            else:
                connection.credential_types.create(**ct_spec)

    def ensure_template_inventory(self, connection, organisation):
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
        # Make sure localhost belongs to the template inventory
        localhost = inventory.hosts.find_by_name("localhost")
        if not localhost:
            localhost = inventory.hosts.create(name = "localhost")
        # Update the variables associated with localhost
        localhost.variable_data._update(
            dict(
                ansible_host = '127.0.0.1',
                ansible_connection = 'local',
            )
        )

    def handle(self, *args, **options):
        connection = api.Connection(
            cloud_settings.AWX.URL,
            cloud_settings.AWX.ADMIN_USERNAME,
            cloud_settings.AWX.ADMIN_PASSWORD,
            cloud_settings.AWX.VERIFY_SSL
        )
#        self.ensure_execution_environment(connection)
        self.ensure_credential_types(connection)
        organisation = self.ensure_organisation(connection)
        self.ensure_template_inventory(connection, organisation)
