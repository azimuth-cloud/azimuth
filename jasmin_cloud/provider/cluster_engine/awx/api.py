"""
Module containing helpers for interacting with the AWX API.
"""

import requests

import rackit


class ResourceManager(rackit.ResourceManager):
    """
    Default resource manager for all AWX resources.
    """
    def extract_list(self, response):
        json = response.json()
        return json['results'], json.get('next')


class Resource(rackit.Resource):
    """
    Base resource for all AWX resouces.
    """
    class Meta:
        manager_cls = ResourceManager


class Organisation(Resource):
    class Meta:
        endpoint = "/organizations/"


class ExecutionEnvironment(Resource):
    class Meta:
        endpoint = "/execution_environments/"


class CredentialType(Resource):
    class Meta:
        endpoint = "/credential_types/"


class Credential(Resource):
    class Meta:
        endpoint = "/credentials/"


class Role(Resource):
    class Meta:
        endpoint = "/roles/"


class Team(Resource):
    class Meta:
        endpoint = "/teams/"

    roles = rackit.NestedResource(Role)


class Playbooks(rackit.UnmanagedResource):
    class Meta:
        endpoint = "/playbooks/"


class Project(Resource):
    class Meta:
        endpoint = "/projects/"

    playbooks = rackit.NestedEndpoint(Playbooks)


class JobTemplate(Resource):
    class Meta:
        endpoint = "/job_templates/"
        cache_keys = ('name', )

    def launch(self, *args, **kwargs):
        return self._action('launch', *args, **kwargs)


class JobEvent(Resource):
    class Meta:
        endpoint = "/job_events/"


class Job(Resource):
    class Meta:
        endpoint = "/jobs/"

    job_events = rackit.NestedResource(JobEvent)


class HostVariableData(rackit.UnmanagedResource):
    class Meta:
        endpoint = "/variable_data/"


class Host(Resource):
    class Meta:
        endpoint = "/hosts/"

    variable_data = rackit.NestedEndpoint(HostVariableData)


class GroupVariableData(rackit.UnmanagedResource):
    class Meta:
        endpoint = "/variable_data/"


class Group(Resource):
    class Meta:
        endpoint = "/groups/"

    hosts = rackit.NestedResource(Host)
    variable_data = rackit.NestedEndpoint(GroupVariableData)


class InventoryManager(ResourceManager):
    def copy(self, resource_or_key, name):
        endpoint = self.prepare_url(resource_or_key, 'copy')
        response = self.connection.api_post(endpoint, json = dict(name = name))
        return self.make_instance(self.extract_one(response))


class InventoryVariableData(rackit.UnmanagedResource):
    class Meta:
        endpoint = "/variable_data/"


class Inventory(Resource):
    class Meta:
        manager_cls = InventoryManager
        endpoint = "/inventories/"

    groups = rackit.NestedResource(Group)
    hosts = rackit.NestedResource(Host)
    variable_data = rackit.NestedEndpoint(InventoryVariableData)

    def copy(self, name):
        return self._manager.copy(self, name)


class Connection(rackit.Connection):
    """
    Class for a connection to an AWX API server.
    """
    path_prefix = "/api/v2"

    organisations = rackit.RootResource(Organisation)
    execution_environments = rackit.RootResource(ExecutionEnvironment)
    credential_types = rackit.RootResource(CredentialType)
    credentials = rackit.RootResource(Credential)
    teams = rackit.RootResource(Team)
    projects = rackit.RootResource(Project)
    job_templates = rackit.RootResource(JobTemplate)
    jobs = rackit.RootResource(Job)
    inventories = rackit.RootResource(Inventory)
    groups = rackit.RootResource(Group)
    hosts = rackit.RootResource(Host)
    roles = rackit.RootResource(Role)
    job_events = rackit.RootResource(JobEvent)

    def __init__(self, url, username, password, verify_ssl = True):
        # Build the session to use basic auth for requests
        session = requests.Session()
        session.auth = requests.auth.HTTPBasicAuth(username, password)
        session.verify = verify_ssl
        super().__init__(url, session)
