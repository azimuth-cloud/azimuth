"""
Module containing helpers for interacting with the OpenStack API.
"""

import json
import logging
from urllib.parse import urlsplit

import requests

import rackit


logger = logging.getLogger(__name__)


class UnmanagedResourceOptions(rackit.resource.Options):
    def __init__(self, options = None):
        options = options or dict()
        endpoint = options.get('endpoint')
        if endpoint:
            if 'resource_key' not in options:
                options.update(
                    resource_key = endpoint.strip('/')
                )
        super().__init__(options)


class UnmanagedResource(rackit.UnmanagedResource):
    """
    Base class for unmanaged OpenStack resources.
    """
    class Meta:
        options_cls = UnmanagedResourceOptions

    def _fetch(self):
        data = super()._fetch()
        # The data is under a key, which we need to extract
        return data[self._opts.resource_key] if self._opts.resource_key else data


class ResourceManager(rackit.ResourceManager):
    """
    Base class for an OpenStack resource manager.
    """
    def related_manager(self, resource_cls):
        # Modify related manager discovery to handle cross-service relationships
        # Use the main connection to get the service for the resource
        service_name = resource_cls._connection_cls.name
        service = getattr(self.connection.session.auth, service_name)
        # Then return the root manager for the resource class in that service
        root = service.root_manager(resource_cls)
        if root:
            return root
        else:
            raise RuntimeError('Unable to locate manager for embedded resource')

    def extract_list(self, response):
        # OpenStack responses have the list under a named key
        # If there is a next page, that is provided under a links attribute
        data = response.json()
        list_data = data[self.resource_cls._opts.resource_list_key]
        next_url = self.extract_next_url(data)
        return list_data, next_url, {}

    def extract_next_url(self, data):
        """
        Given the response data, extract the next URL from it.
        """
        # By default, use the resource_links_key
        return next(
            (
                link['href']
                for link in data.get(self.resource_cls._opts.resource_links_key, [])
                if link['rel'] == 'next'
            ),
            None
        )

    def extract_one(self, response):
        # Some OpenStack responses have the instance under a named key
        if self.resource_cls._opts.resource_key:
            return response.json()[self.resource_cls._opts.resource_key]
        else:
            return response.json()

    def prepare_params(self, params):
        # If there is a resource key, nest the parameters using it
        params = super().prepare_params(params)
        if self.resource_cls._opts.resource_key:
            return { self.resource_cls._opts.resource_key: params }
        else:
            return params


class ResourceWithDetailManager(ResourceManager):
    """
    Base class for a resource where lists can be fetched with or without detail.

    When a list is fetched without detail, partial entities will be returned.
    """
    def all(self, detail = True, **params):
        endpoint = self.prepare_url()
        if detail:
            endpoint = endpoint + '/detail'
        return self._fetch_all(endpoint, params, not detail)


class ResourceOptions(rackit.resource.Options):
    """
    Custom options class derives default options for OpenStack resources.
    """
    def __init__(self, options = None):
        options = options or dict()
        endpoint = options.get('endpoint')
        if endpoint:
            # Derive default values for response keys, if not given
            if 'resource_list_key' not in options:
                options.update(
                    resource_list_key = endpoint.strip('/')
                )
            if 'resource_links_key' not in options:
                options.update(
                    resource_links_key = '{}_links'.format(options['resource_list_key'])
                )
            if 'resource_key' not in options:
                options.update(
                    # By default, assume the list key ends with an 's' that we trim
                    resource_key = options['resource_list_key'][:-1]
                )
        super().__init__(options)


class Resource(rackit.Resource):
    """
    Base class for OpenStack resources.
    """
    class Meta:
        options_cls = ResourceOptions
        manager_cls = ResourceManager
        update_http_verb = 'put'


class ResourceWithDetail(Resource):
    """
    Base class for OpenStack resources that support a detail view.
    """
    class Meta:
        manager_cls = ResourceWithDetailManager


class AuthProjectManager(ResourceManager):
    """
    Custom manager for projects implementing pagination.
    """
    def extract_list(self, response):
        list_data, next_url, next_params = super().extract_list(response)
        # HACK
        # When the current token is for an app cred, limit the returned results to the project
        # that the app cred is for
        # This is a hack around the fact app creds are able to list all the projects that the
        # owner can see, even though they cannot use those projects
        # IMHO this is a bug
        if self.connection.auth_method == "application_credential":
            list_data = [p for p in list_data if p['id'] == self.connection.project_id]
        return list_data, next_url, next_params

    def extract_next_url(self, data):
        return data.get('links', {}).get('next')


class AuthProject(Resource):
    """
    Resource for the projects for a user.

    Manipulation of projects more generally is available through the identity service.
    """
    class Meta:
        manager_cls = AuthProjectManager
        endpoint = '/auth/projects'
        resource_list_key = 'projects'


class Connection(rackit.Connection):
    """
    Class for a connection to an OpenStack API, which handles the authentication,
    project and service discovery elements.

    Can be used as an auth object for a requests session.
    """
    projects = rackit.RootResource(AuthProject)

    def __init__(self, auth_url, token, interface = 'public', verify = True):
        # Store the given parameters, as it is sometimes useful to be able to query them later
        self.auth_url = auth_url.rstrip('/')
        self.token = token
        self.interface = interface
        self.verify = verify

        # Configure the session
        session = requests.Session()
        # This object is the auth object for the session
        session.auth = self
        session.verify = verify

        # Once the superclass init is called, we can use the api_{} methods
        super().__init__(auth_url, session)

        # Confirm whether the token is still valid
        # If this returns anything other than a 200, close the session
        try:
            response = self.api_get('/auth/tokens', headers = { 'X-Subject-Token': token })
        except rackit.ApiError:
            session.close()
            raise

        # Extract information about the user and project from the response
        json = response.json()
        self.auth_method = json['token']['methods'][0]
        user = json['token']['user']
        self.user_id = user['id']
        self.username = user['name']
        self.domain_id = user['domain']['id']
        self.domain_name = user['domain']['name']
        project = json['token'].get('project', {})
        self.project_id = project.get('id')
        self.project_name = project.get('name')
        self.roles = json['token'].get('roles', [])

        # Extract the endpoints from the catalog on the correct interface
        self.endpoints = {}
        for entry in json['token'].get('catalog', []):
            # Find the endpoint on the specified interface
            try:
                endpoint = next(
                    ep['url']
                    for ep in entry['endpoints']
                    if ep['interface'] == self.interface
                )
            except StopIteration:
                continue
            # Strip any path component from the endpoint
            self.endpoints[entry['type']] = urlsplit(endpoint)._replace(path = '').geturl()

    def __call__(self, request):
        # This is what allows the connection to be used as a requests auth
        # If there is a token, set the OpenStack auth token header
        try:
            request.headers['X-Auth-Token'] = self.token
        except AttributeError:
            pass
        return request

    def scoped_connection(self, project_or_id):
        """
        Return a new connection that is scoped to the given project.
        """
        # Extract the project id from a resource if required
        if isinstance(project_or_id, Resource):
            project_id = project_or_id.id
        else:
            project_id = project_or_id
        if project_id == self.project_id:
            return self
        else:
            # Obtain a new token with the requested scope
            response = self.api_post(
                '/auth/tokens',
                json = dict(
                    auth = dict(
                        identity = dict(methods = ['token'], token = dict(id = self.token)),
                        scope = dict(project = dict(id = project_id))
                    )
                )
            )
            token = response.headers['X-Subject-Token']
            return self.__class__(self.auth_url, token, self.interface, self.verify)


class ServiceNotSupported(RuntimeError):
    """
    Raised when a service that is not supported by the cloud is asked for.
    """
    def __init__(self, service, *args, **kwargs):
        super().__init__(f"Service not supported: {service}", *args, **kwargs)


class ServiceDescriptor(rackit.CachedProperty):
    """
    Property descriptor for attaching a :py:class:`Service` to a :py:class:`Connection`.

    The returned service instances are configured using the endpoints discovered from
    the service catalog.
    """
    def __init__(self, service_cls):
        self.service_cls = service_cls
        super().__init__(self.get_service)

    def get_service(self, instance):
        try:
            url = instance.endpoints[self.service_cls.catalog_type]
        except KeyError:
            raise ServiceNotSupported(self.service_cls.catalog_type)
        return self.service_cls(url, instance.session)


class Service(rackit.Connection):
    """
    Base class for OpenStack service connections.
    """
    #: The name of the catalog type that this service is for
    #: This is used to retrieve the endpoint from the service catalog
    catalog_type = None
    #: The specific microversion to request, if required
    microversion = None

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        # If the service has a catalog type, add it to the connection
        if cls.catalog_type:
            # If no explicit name is given, use the catalog type
            if hasattr(cls, 'name'):
                name = cls.name
            else:
                name = cls.catalog_type.replace('-', '_')
                cls.name = name
            descriptor = ServiceDescriptor(cls)
            setattr(Connection, name, descriptor)
            descriptor.__set_name__(Connection, name)

    def __init__(self, url, session):
        super().__init__(url, session)
        # Template the project id into the path prefix
        if self.path_prefix:
            # Template the project id into the path prefix
            project_id = session.auth.project_id
            self.path_prefix = self.path_prefix.format(project_id = project_id)

    def _find_message(self, obj):
        # Try to find a message property at any depth within the structure
        if isinstance(obj, dict):
            # Try a couple of different keys for error detail
            for key in ('message', 'detail'):
                if key in obj:
                    return obj[key]
            for item in obj.values():
                message = self._find_message(item)
                if message:
                    return message
        elif isinstance(obj, list):
            for item in obj:
                message = self._find_message(item)
                if message:
                    return message

    def prepare_request(self, request):
        # If a specific microversion is requested, add the appropriate header
        if self.microversion:
            request.headers["OpenStack-API-Version"] = f"{self.catalog_type} {self.microversion}"
        return super().prepare_request(request)

    def extract_error_message(self, response):
        """
        Extract an error message from the given error response and return it.
        """
        # First, try to parse the response as JSON
        # If it fails, just use the response text
        try:
            json_obj = response.json()
        except json.decoder.JSONDecodeError:
            return response.text
        else:
            # Traverse the structure looking for a message property
            # Use the response text if not found
            return self._find_message(json_obj) or response.text
