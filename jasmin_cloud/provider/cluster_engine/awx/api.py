"""
Module containing helpers for interacting with the AWX API.
"""

import requests
import logging


logger = logging.getLogger(__name__)


class Error(RuntimeError):
    """Base class for resource fetching errors."""


class BadRequest(Error):
    """Raised when a 400 Bad Request occurs."""


class Unauthorized(Error):
    """Raised when a 401 Unauthorized occurs."""


class Forbidden(Error):
    """Raised when a 403 Forbidden occurs."""


class NotFound(Error):
    """Raised when a 404 Not Found occurs."""


class Conflict(Error):
    """Raised when a 409 Conflict occurs."""


class Connection:
    """
    Class for a connection to AWX.
    """
    resource_classes = {}

    def __init__(self, url, username, password, verify_ssl = True):
        self.session = requests.Session()
        self.session.verify = verify_ssl
        self.session.auth = requests.auth.HTTPBasicAuth(username, password)
        self.api_base = url
        self.resources = {}

    def api_request(self, method, path, *args, as_json = True, **kwargs):
        logger.info("AWX API request: {} {}".format(method.upper(), self.api_base + path))
        response = getattr(self.session, method.lower())(
            self.api_base + path,
            *args,
            **kwargs
        )
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as exc:
            if exc.response.status_code == 400:
                raise BadRequest
            elif exc.response.status_code == 401:
                raise Unauthorized
            elif exc.response.status_code == 403:
                raise Forbidden
            elif exc.response.status_code == 404:
                raise NotFound
            elif exc.response.status_code == 409:
                raise Conflict
            else:
                raise
        if as_json:
            return response.json()
        else:
            return response.text

    def api_get(self, *args, **kwargs):
        return self.api_request('get', *args, **kwargs)

    def api_post(self, *args, **kwargs):
        return self.api_request('post', *args, **kwargs)

    def api_put(self, *args, **kwargs):
        return self.api_request('put', *args, **kwargs)

    def api_patch(self, *args, **kwargs):
        return self.api_request('patch', *args, **kwargs)

    def api_delete(self, *args, **kwargs):
        return self.api_request('delete', *args, **kwargs)

    def __getattr__(self, name):
        # Cache the resource instance for the future
        if name not in self.resources:
            self.resources[name] = self.resource_classes[name](self)
        return self.resources[name]

    def close(self):
        self.session.close()

    @classmethod
    def register_resource(cls, resource_class):
        """
        Decorator that registers a resource class.
        """
        cls.resource_classes[resource_class.name] = resource_class


class Entity(dict):
    """
    Base class for an entity returned from the API.
    """
    def __init__(self, connection, data):
        self._connection = connection
        self._related_cache = {}
        super().__init__(data)

    def related_cache_has(self, related):
        return related in self._related_cache

    def related_cache_get(self, related):
        return self._related_cache[related]

    def related_cache_set(self, related, value):
        self._related_cache[related] = value
        return value

    def related_cache_evict(self, related):
        return self._related_cache.pop(related, None)

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError("No such attribute '{}'".format(name))

    def fetch_related(self, related):
        # Use/populate the cache as required
        if not self.related_cache_has(related):
            data = self._connection.api_get(self.related[related])
            if 'results' in data:
                return self.related_cache_set(
                    related,
                    tuple(Entity(self._connection, r) for r in data['results'])
                )
            else:
                return self.related_cache_set(
                    related,
                    Entity(self._connection, data)
                )
        return self.related_cache_get(related)

    def create_related(self, related, **params):
        return self.related_cache_set(
            related,
            Entity(
                self._connection,
                self._connection.api_post(self.related[related], json = params)
            )
        )

    def update_related(self, related, **params):
        return self.related_cache_set(
            related,
            Entity(
                self._connection,
                self._connection.api_patch(self.related[related], json = params)
            )
        )

    def cast_as(self, entity_class):
        return entity_class(self._connection, dict(self))


class Resource:
    """
    Base class for a resource.
    """
    #: The API endpoint for the resource
    endpoint = None
    #: The name of the resource
    name = None
    #: The plural name of the resource
    name_plural = None
    #: The entity class to use
    entity_class = Entity

    def __init__(self, connection):
        self._connection = connection
        self._cache = {}

    def cache_has(self, id):
        return str(id) in self._cache

    def cache_get(self, id):
        return self._cache[str(id)]

    def cache_set(self, id, value):
        self._cache[str(id)] = value
        return value

    def cache_evict(self, id):
        return self._cache.pop(str(id), None)

    def fetch_all(self, **params):
        data = self._connection.api_get(self.endpoint, params = params)
        # Cache the entities as we iterate
        return tuple(
            self.cache_set(r['id'], self.entity_class(self._connection, r))
            for r in data['results']
        )

    def fetch_one(self, id = None, **params):
        if id is not None:
            # If doing a fetch by id, use/populate the cache
            if not self.cache_has(id):
                return self.cache_set(
                    id,
                    self.entity_class(
                        self._connection,
                        self._connection.api_get('{}{}/'.format(self.endpoint, id))
                    )
                )
            return self.cache_get(id)
        else:
            try:
                return next(iter(self.fetch_all(**params)))
            except StopIteration:
                raise NotFound

    def create(self, **params):
        data = self._connection.api_post(self.endpoint, json = params)
        return self.cache_set(data['id'], self.entity_class(self._connection, data))

    def delete(self, entity):
        if isinstance(entity, Entity):
            entity = entity.id
        self._connection.api_delete('{}{}/'.format(self.endpoint, entity), as_json = False)
        self.cache_evict(entity)

    @classmethod
    def make(cls, name,
                  name_plural = None,
                  endpoint = None,
                  entity_class = Entity):
        """
        Utility function to create a new resource class where no additional
        methods are required.
        """
        name_plural = name_plural or name + 's'
        endpoint = endpoint or '/api/v2/{}/'.format(name_plural)
        return type(
            'Resource_{}'.format(name),
            (cls, ),
            dict(
                endpoint = endpoint,
                name = name,
                name_plural = name_plural,
                entity_class = entity_class
            )
        )


Connection.register_resource(Resource.make('organisation', endpoint = '/api/v2/organizations/'))
Connection.register_resource(Resource.make('credential_type'))
Connection.register_resource(Resource.make('credential'))
Connection.register_resource(Resource.make('team'))
Connection.register_resource(Resource.make('job_template'))
Connection.register_resource(Resource.make('job'))


@Connection.register_resource
class InventoryResource(Resource.make('inventory', 'inventories')):
    """
    Custom resource for inventories.
    """
    def copy(self, id, name):
        inventory = self._connection.api_post(
            '{}{}/copy/'.format(self.endpoint, id),
            json = dict(name = name)
        )
        return self.cache_set(
            inventory['id'],
            self.entity_class(self._connection, inventory)
        )
