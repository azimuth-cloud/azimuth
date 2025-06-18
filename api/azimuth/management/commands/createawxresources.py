"""
Module containing the management command for creating AWX resources required for CaaS.
"""

import json
import re
import time

import rackit
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    PublicFormat,
)
from django.core.management.base import BaseCommand

from azimuth.cluster_engine.drivers.awx import api
from azimuth.cluster_engine.drivers.awx.driver import CREDENTIAL_TYPE_NAMES
from azimuth.settings import cloud_settings

CAAS_ORGANISATION_NAME = "CaaS"

CAAS_DEPLOY_KEYPAIR_CREDENTIAL_NAME = "CaaS Deploy Keypair"
CAAS_CONSUL_CREDENTIAL_NAME = "Hashicorp Consul"

OPENSTACK_TOKEN_CLOUDS_TEMPLATE = """
clouds:
  openstack:
    auth:
      auth_url: "{{ auth_url }}"
      project_id: "{{ project_id }}"
      token: "{{ token }}"
    auth_type: token
    verify: {{ 'true' if verify_ssl else 'false' }}
"""

CAAS_CREDENTIAL_TYPES = [
    {
        "name": CREDENTIAL_TYPE_NAMES["openstack_token"],
        "description": (
            "Authenticate with an OpenStack cloud using a previously acquired token."
        ),
        "kind": "cloud",
        "inputs": {
            "fields": [
                {
                    "type": "string",
                    "id": "auth_url",
                    "label": "Auth URL",
                },
                {
                    "type": "string",
                    "id": "project_id",
                    "label": "Project ID",
                },
                {
                    "type": "string",
                    "id": "token",
                    "label": "Token",
                    "secret": True,
                },
                {
                    "type": "boolean",
                    "id": "verify_ssl",
                    "label": "Verify SSL?",
                },
            ],
            "required": ["auth_url", "project_id", "token"],
        },
        "injectors": {
            # Make a clouds.yaml file for the token
            "file": {
                "template": OPENSTACK_TOKEN_CLOUDS_TEMPLATE,
            },
            # Point the OpenStack SDK at it using environment variables
            "env": {
                "OS_CLIENT_CONFIG_FILE": "{{ tower.filename }}",
                "OS_CLOUD": "openstack",
            },
        },
    },
    {
        "name": CAAS_DEPLOY_KEYPAIR_CREDENTIAL_NAME,
        "description": "SSH keypair used for CaaS deployments.",
        "kind": "cloud",
        "inputs": {
            "fields": [
                {
                    "type": "string",
                    "id": "public_key",
                    "label": "Public key",
                },
                {
                    "type": "string",
                    "id": "private_key",
                    "label": "Private key",
                    "secret": True,
                    "multiline": True,
                },
            ],
            "required": ["public_key", "private_key"],
        },
        "injectors": {
            # Inject the private key as a file
            "file": {
                "template": "{{ private_key }}",
            },
            "extra_vars": {
                # Set a variable pointing to the private key file
                "cluster_ssh_private_key_file": "{{ tower.filename }}",
                # Also set a variable containing the public key
                "cluster_deploy_ssh_public_key": "{{ public_key }}",
            },
        },
    },
    {
        "name": CAAS_CONSUL_CREDENTIAL_NAME,
        "description": "Credentials for a Hashicorp Consul instance.",
        "kind": "cloud",
        "inputs": {
            "fields": [
                {
                    "type": "string",
                    "id": "address",
                    "label": "Consul address (including port)",
                },
                {
                    "type": "boolean",
                    "id": "http_ssl",
                    "label": "Use SSL?",
                },
                {
                    "type": "string",
                    "id": "access_token",
                    "label": "Access token (optional)",
                    "secret": True,
                },
                {
                    "type": "string",
                    "id": "http_auth",
                    "label": "Basic Auth credentials (optional)",
                    "secret": True,
                },
            ],
            "required": ["address"],
        },
        "injectors": {
            "env": {
                "CONSUL_HTTP_ADDR": "{{ address }}",
                "CONSUL_HTTP_TOKEN": "{{ access_token }}",
                "CONSUL_HTTP_SSL": "{% if http_ssl %}true{% endif %}",
                "CONSUL_HTTP_AUTH": "{{ http_auth }}",
            },
        },
    },
]


class Command(BaseCommand):
    """
    Management command for creating the AWX resources required by Cluster-as-a-Service.
    """

    help = "Creates AWX resources required by Cluster-as-a-Service."

    def wait_for_awx(self, connection):
        """
        Waits for the AWX API to become available before returning.
        """
        self.stdout.write("Waiting for AWX API to become available...")
        # Just try to fetch the API information until it loads properly
        while True:
            try:
                connection.api_get("/")
            except (rackit.ConnectionError, rackit.ApiError):
                # If there is an error response, we need to continue
                pass
            else:
                break
            time.sleep(5)

    def ensure_credential_type(self, connection, ct_spec):
        """
        Ensures that given credential type exists.
        """
        ct = connection.credential_types.find_by_name(ct_spec["name"])
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
            ct["name"]: self.ensure_credential_type(connection, ct)
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
            organisation = connection.organisations.create(name=CAAS_ORGANISATION_NAME)
        return organisation

    def ensure_organisation_ee_cred(self, connection, organisation, credentials):
        """
        Ensures that the registry credential for the CaaS organisation EE exists,
        if required.
        """
        ct = connection.credential_types.find_by_kind("registry")
        credential_name = f"{CAAS_ORGANISATION_NAME} EE Credential"
        credential = connection.credentials.find_by_name(credential_name)
        params = dict(
            credential_type=ct.id,
            organization=organisation.id,
            inputs=dict(
                host=credentials["HOST"],
                username=credentials["USERNAME"],
                password=credentials["TOKEN"],
            ),
        )
        if credential:
            self.stdout.write("Updating organisation registry credential")
            credential = credential._update(**params)
        else:
            self.stdout.write("Creating registry credential for organisation")
            credential = connection.credentials.create(name=credential_name, **params)
        return credential

    def ensure_organisation_ee(self, connection, organisation):
        """
        Ensures that the execution environment for the CaaS organisation exists,
        if required.
        """
        if not cloud_settings.AWX.EXECUTION_ENVIRONMENT:
            self.stdout.write("Using default execution environment")
            return None
        credentials = cloud_settings.AWX.EXECUTION_ENVIRONMENT.get("CREDENTIALS")
        if credentials:
            credential = self.ensure_organisation_ee_cred(
                connection, organisation, credentials
            )
        else:
            credential = None
        ee_name = f"{CAAS_ORGANISATION_NAME} EE"
        ee = connection.execution_environments.find_by_name(ee_name)
        params = dict(
            image=cloud_settings.AWX.EXECUTION_ENVIRONMENT["IMAGE"],
            organization=organisation.id,
            pull=(
                "always"
                if cloud_settings.AWX.EXECUTION_ENVIRONMENT.get("ALWAYS_PULL", False)
                else "missing"
            ),
            credential=getattr(credential, "id", None),
        )
        if ee:
            self.stdout.write(f"Updating execution environment '{ee.name}'")
            ee = ee._update(**params)
        else:
            self.stdout.write(f"Creating execution environment '{ee_name}'")
            ee = connection.execution_environments.create(name=ee_name, **params)
        # Set the execution environment as the default environment for the org
        organisation._update(default_environment=ee.id)
        return ee

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
                organization=organisation.id, credential_type=galaxy_ct.id
            ),
            None,
        )
        if credential:
            self.stdout.write("Found existing Galaxy credential for organisation")
        else:
            self.stdout.write("Creating Galaxy credential for organisation")
            credential = connection.credentials.create(
                name=f"{CAAS_ORGANISATION_NAME} Galaxy Credential",
                credential_type=galaxy_ct.id,
                organization=organisation.id,
                inputs=dict(url="https://galaxy.ansible.com"),
            )
        # Weirdly, although the credential is created under the organisation, we also
        # need to make this association
        connection.api_post(
            f"/organizations/{organisation.id}/galaxy_credentials/",
            json=dict(id=credential.id),
        )
        return credential

    def ensure_caas_deploy_keypair(self, connection, organisation, ct):
        """
        Ensure that a CaaS deploy keypair with the expected name exists.
        """
        credential = connection.credentials.find_by_name(
            CAAS_DEPLOY_KEYPAIR_CREDENTIAL_NAME
        )
        if credential:
            self.stdout.write("Found existing CaaS deploy keypair credential")
        else:
            self.stdout.write("Generating ed25519 key pair")
            # Generate a keypair to use
            keypair = Ed25519PrivateKey.generate()
            private_key = keypair.private_bytes(
                Encoding.PEM, PrivateFormat.OpenSSH, NoEncryption()
            ).decode()
            public_key = (
                keypair.public_key()
                .public_bytes(Encoding.OpenSSH, PublicFormat.OpenSSH)
                .decode()
            )
            self.stdout.write("Creating CaaS deploy keypair credential")
            credential = connection.credentials.create(
                name=CAAS_DEPLOY_KEYPAIR_CREDENTIAL_NAME,
                credential_type=ct.id,
                organization=organisation.id,
                inputs=dict(public_key=public_key, private_key=private_key),
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
            inventory = inventory._update(organization=organisation.id)
        else:
            self.stdout.write(f"Creating inventory '{inventory_name}'")
            inventory = connection.inventories.create(
                name=inventory_name, organization=organisation.id
            )
        # Create the openstack group
        group = inventory.groups.find_by_name("openstack")
        if group:
            self.stdout.write("Found existing inventory group 'openstack'")
        else:
            self.stdout.write("Creating inventory group 'openstack'")
            group = inventory.groups.create(name="openstack")
        # Create localhost in the inventory and group
        localhost = group.hosts.find_by_name("localhost")
        if localhost:
            self.stdout.write("Found existing localhost for inventory")
        else:
            self.stdout.write("Creating localhost for inventory")
            localhost = group.hosts.create(name="localhost", inventory=inventory.id)
        # Update the variables associated with localhost
        self.stdout.write("Updating inventory variables for localhost")
        localhost.variable_data._update(
            dict(
                ansible_host="127.0.0.1",
                ansible_connection="local",
                ansible_python_interpreter="{{ ansible_playbook_python }}",
            )
        )

    def ensure_extra_credential(
        self, connection, organisation, credential_types, cred_spec
    ):
        """
        Ensure that the specified extra credential exists.
        """
        # Try to find the credential type from the name
        credential = connection.credentials.find_by_name(cred_spec["NAME"])
        params = dict(
            credential_type=credential_types[cred_spec["TYPE"]].id,
            organization=organisation.id,
            inputs=cred_spec["INPUTS"],
        )
        if credential:
            self.stdout.write(f"Updating credential '{credential.name}'")
            credential = credential._update(**params)
        else:
            self.stdout.write(f"Creating credential '{cred_spec['NAME']}'")
            credential = connection.credentials.create(name=cred_spec["NAME"], **params)
        return credential

    def ensure_extra_credentials(self, connection, organisation, credential_types):
        """
        Ensure that any extra credentials that are configured exist.
        """
        return [
            self.ensure_extra_credential(
                connection, organisation, credential_types, cred_spec
            )
            for cred_spec in cloud_settings.AWX.EXTRA_CREDENTIALS
        ]

    def ensure_project(self, connection, organisation, project_spec):
        """
        Ensure that the given project exists.
        """
        project = connection.projects.find_by_name(project_spec["NAME"])
        params = dict(
            scm_type="git",
            scm_url=project_spec["GIT_URL"],
            scm_branch=project_spec["GIT_VERSION"],
            organization=organisation.id,
            scm_update_on_launch=project_spec.get("ALWAYS_UPDATE", False),
        )
        if project:
            self.stdout.write(f"Updating project '{project.name}'")
            project = project._update(**params)
        else:
            self.stdout.write(f"Creating project '{project_spec['NAME']}'")
            project = connection.projects.create(name=project_spec["NAME"], **params)
        # Wait for the project to move into the successful state
        self.stdout.write("Waiting for project to become available...")
        while project.status != "successful":
            time.sleep(3)
            project = connection.projects.get(project.id, force=True)
        return project

    def ensure_projects(self, connection, organisation):
        """
        Ensure that the configured projects exist.
        """
        # Return (project_spec, project) pairs so we have access to the spec later
        return [
            (project_spec, self.ensure_project(connection, organisation, project_spec))
            for project_spec in cloud_settings.AWX.DEFAULT_PROJECTS
        ]

    def ensure_job_template_for_playbook(
        self, connection, project_spec, project, playbook, credentials
    ):
        """
        Ensures that a job template exists for the given project and playbook.
        """
        # Sanitise any weird characters in the playbook name
        template_name = re.sub(
            "[^a-zA-Z0-9-]+", "-", playbook.removesuffix(".yml").removesuffix(".yaml")
        )
        # Work out what extra vars we should use for the job template
        # Start with the common extra vars
        extra_vars_spec = project_spec.get("EXTRA_VARS", {})
        extra_vars = dict(extra_vars_spec.get("__ALL__", {}))
        # Update with specific variables for the playbook
        extra_vars.update(extra_vars_spec.get(playbook, {}))
        # The metadata root should be in the project spec
        # If can have the git version interpolated into it
        git_version = project_spec["GIT_VERSION"]
        metadata_root = project_spec["METADATA_ROOT"].format(
            git_version=git_version, gitVersion=git_version
        )
        # The metadata file should be named after the playbook
        metadata_url = f"{metadata_root}/{playbook}"
        job_template = connection.job_templates.find_by_name(template_name)
        params = dict(
            description=metadata_url,
            job_type="run",
            project=project.id,
            playbook=playbook,
            extra_vars=json.dumps(extra_vars),
            # We will add the deploy keypair as a default credential,
            # but also allow extra credentials to be added
            ask_credential_on_launch=True,
            ask_inventory_on_launch=True,
            # As well as the extra vars for the template, we allow per-job variables
            ask_variables_on_launch=True,
            allow_simultaneous=True,
        )
        if job_template:
            self.stdout.write(f"Updating job template '{template_name}'")
            job_template = job_template._update(**params)
        else:
            self.stdout.write(f"Creating job template '{template_name}'")
            job_template = connection.job_templates.create(name=template_name, **params)
        existing_creds = [c["id"] for c in job_template.summary_fields["credentials"]]
        # Update credential associations where required
        unassociated_creds = [c for c in credentials if c.id not in existing_creds]
        for cred in unassociated_creds:
            self.stdout.write(f"Associating credential '{cred.name}' with job template")
            connection.api_post(
                f"/job_templates/{job_template.id}/credentials/", json=dict(id=cred.id)
            )
        return job_template

    def ensure_job_templates_for_project(
        self, connection, project_spec, project, credentials
    ):
        """
        Ensures that a job template exists for each playbook in a project.
        """
        self.stdout.write(f"Creating or updating job templates for '{project.name}'")
        if "PLAYBOOKS" in project_spec:
            playbooks = project_spec["PLAYBOOKS"]
        else:
            self.stdout.write(f"Fetching playbooks for project '{project.name}'")
            playbooks = project.playbooks._fetch()
        self.stdout.write(f"Using playbooks: {playbooks}")
        return [
            self.ensure_job_template_for_playbook(
                connection, project_spec, project, playbook, credentials
            )
            for playbook in playbooks
        ]

    def ensure_job_templates(self, connection, projects, credentials):
        """
        Ensure that a job template exists for each playbook in each project.
        """
        return [
            job_template
            for (project_spec, project) in projects
            for job_template in self.ensure_job_templates_for_project(
                connection, project_spec, project, credentials
            )
        ]

    def handle(self, *args, **options):
        connection = api.Connection(
            cloud_settings.AWX.URL,
            cloud_settings.AWX.ADMIN_USERNAME,
            cloud_settings.AWX.ADMIN_PASSWORD,
            cloud_settings.AWX.VERIFY_SSL,
        )
        self.wait_for_awx(connection)
        credential_types = self.ensure_credential_types(connection)
        organisation = self.ensure_organisation(connection)
        self.ensure_organisation_ee(connection, organisation)
        self.ensure_galaxy_credential(connection, organisation)
        deploy_keypair_cred = self.ensure_caas_deploy_keypair(
            connection,
            organisation,
            credential_types[CAAS_DEPLOY_KEYPAIR_CREDENTIAL_NAME],
        )
        self.ensure_template_inventory(connection, organisation)
        credentials = self.ensure_extra_credentials(
            connection, organisation, credential_types
        )
        credentials.insert(0, deploy_keypair_cred)
        projects = self.ensure_projects(connection, organisation)
        self.ensure_job_templates(connection, projects, credentials)
