import functools
import re

import httpx
import yaml

from ..authenticator.openstack import normalize_auth_url  # noqa: TID252
from . import base, dto, errors


def convert_httpx_exceptions(f):
    """
    Decorator that converts HTTPX exceptions into auth session errors.
    """

    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 400:
                raise errors.BadInputError(str(exc))
            elif exc.response.status_code == 401:
                raise errors.AuthenticationError("Your session has expired.")
            elif exc.response.status_code == 403:
                raise errors.PermissionDeniedError("Permission denied.")
            elif exc.response.status_code == 404:
                raise errors.ObjectNotFoundError(
                    "The requested resource could not be found."
                )
            elif exc.response.status_code == 409:
                raise errors.InvalidOperationError(str(exc))
            else:
                raise errors.CommunicationError("Error with OpenStack API.") from exc
        except httpx.HTTPError as exc:
            raise errors.CommunicationError(
                "Could not connect to OpenStack API."
            ) from exc

    return wrapper


class OpenStackAuth(httpx.Auth):
    """
    Authentication scheme for OpenStack requests.
    """

    def __init__(self, token):
        self.token = token

    def auth_flow(self, request):
        request.headers["X-Auth-Token"] = self.token
        yield request


class Provider(base.Provider):
    """
    Provider that understands OpenStack tokens.
    """

    def __init__(self, auth_url, region=None, interface="public", verify_ssl=True):
        self.auth_url = normalize_auth_url(auth_url)
        self.region = region
        self.interface = interface
        self.verify_ssl = verify_ssl

    def from_token(self, token: str) -> "Session":
        return Session(
            httpx.Client(
                auth=OpenStackAuth(token),
                base_url=self.auth_url,
                verify=self.verify_ssl,
            ),
            self.auth_url,
            self.region,
            self.interface,
            self.verify_ssl,
        )


class Session(base.Session):
    """
    Session for OpenStack clouds.
    """

    def __init__(self, client, auth_url, region, interface, verify_ssl):
        self.client = client
        self.auth_url = auth_url
        self.region = region
        self.interface = interface
        self.verify_ssl = verify_ssl
        # Cached information about the token
        self._token_data = None

    def token(self):
        return self.client.auth.token

    def _get_token_data(self):
        if not self._token_data:
            response = self.client.get(
                "/auth/tokens", headers={"X-Subject-Token": self.token()}
            )
            # A 401 or a 404 indicates a failure to validate the token
            if response.status_code in {401, 404}:
                raise errors.AuthenticationError("Your session has expired.")
            response.raise_for_status()
            self._token_data = response.json()["token"]
        return self._token_data

    @convert_httpx_exceptions
    def user(self):
        token_data = self._get_token_data()
        user_data = token_data["user"]
        username = user_data["name"]
        # If the username "looks like" an email address, just use that as the email
        # Otherwise construct a fake email from the username + domain
        if "@" in username:
            user_email = username
        else:
            user_email = f"{username}@{user_data['domain']['name'].lower()}.openstack"
        return dto.User(user_data["id"], username, user_email)

    @convert_httpx_exceptions
    def tenancies(self):
        response = self.client.get("/auth/projects")
        response.raise_for_status()
        # NOTE(mkjpryor)
        # If the token was issued for an appcred, return only the project that the
        # appcred is for
        # This is a because tokens issued for appcreds are able to list all the projects
        # that the owner belongs to but cannot be rescoped to any of the other projects
        token_data = self._get_token_data()
        is_app_cred = token_data["methods"][0] == "application_credential"
        project_id = token_data.get("project", {}).get("id")
        return [
            dto.Tenancy(project["id"], project["name"])
            for project in response.json()["projects"]
            if project["enabled"] and (not is_app_cred or project["id"] == project_id)
        ]

    def _scoped_token(self, project_id=None):
        """
        Returns a scoped token for the specified project, or any project if not
        specified.
        """
        # If we already have a scoped token for the correct project, we are done
        token_data = self._get_token_data()
        token_project_id = token_data.get("project", {}).get("id")
        if token_project_id and (not project_id or token_project_id == project_id):
            return self.token(), token_data
        # If not, attempt to obtain a new token with the correct scope
        # If no project is specified, we use the first project
        if not project_id:
            try:
                project_id = next(t.id for t in self.tenancies())
            except StopIteration:
                raise errors.InvalidOperationError(
                    "User does not belong to any tenancies."
                )
        response = self.client.post(
            "/auth/tokens",
            json={
                "auth": {
                    "identity": {
                        "methods": ["token"],
                        "token": {
                            "id": self.token(),
                        },
                    },
                    "scope": {
                        "project": {
                            "id": project_id,
                        },
                    },
                },
            },
        )
        response.raise_for_status()
        return response.headers["X-Subject-Token"], response.json()["token"]

    def _compute_client(self):
        """
        Creates a HTTPX client for the compute service, used to manage SSH keypairs.
        SSH keys are user-scoped in OpenStack not project-scoped, however we need a
        project-scoped token to use the compute API to read/write them.

        Returns a tuple of (client, keypair_name) so that we don't need a separate HTTP
        request to get the username to build the keypair name.
        """
        token, token_data = self._scoped_token()
        try:
            compute_url = next(
                ep["url"]
                for entry in token_data["catalog"]
                for ep in entry["endpoints"]
                if (
                    entry["type"] == "compute"
                    and ep["interface"] == self.interface
                    and (not self.region or ep["region"] == self.region)
                )
            )
        except StopIteration:
            raise errors.InvalidOperationError("Unable to find compute service.")
        client = httpx.Client(
            auth=OpenStackAuth(token), base_url=compute_url, verify=self.verify_ssl
        )
        return client, re.sub("[^a-zA-Z0-9]+", "-", token_data["user"]["name"])

    @convert_httpx_exceptions
    def ssh_public_key(self):
        client, keypair_name = self._compute_client()
        # Use the client to fetch the keypair for the user
        response = client.get(f"/os-keypairs/{keypair_name}")
        response.raise_for_status()
        return response.json()["keypair"]["public_key"]

    @convert_httpx_exceptions
    def update_ssh_public_key(self, public_key):
        client, keypair_name = self._compute_client()
        # Keypairs are immutable in OpenStack, so we remove the existing keypair first
        response = client.delete(f"/os-keypairs/{keypair_name}")
        # A 404 is fine here, i.e. the keypair doesn't exist
        if response.is_error and response.status_code != 404:
            response.raise_for_status()
        # Create a new keypair with the new public key
        response = client.post(
            "/os-keypairs",
            json={
                "keypair": {
                    "name": keypair_name,
                    "public_key": public_key,
                },
            },
        )
        response.raise_for_status()
        return response.json()["keypair"]["public_key"]

    def credential(self, tenancy_id, provider):
        # We only know how to produce credentials for the openstack provider
        if provider != "openstack":
            return None
        # Get a scoped token for the specified tenancy
        token, _ = self._scoped_token(tenancy_id)
        # Return the contents of a clouds.yaml configured to use the token
        data = {
            "clouds": {
                "openstack": {
                    "identity_api_version": 3,
                    "auth_type": "v3token",
                    "auth": {
                        "auth_url": self.auth_url,
                        "token": token,
                    },
                    "interface": self.interface,
                    "verify": self.verify_ssl,
                },
            },
        }
        if self.region:
            data["clouds"]["openstack"]["region_name"] = self.region
        return dto.Credential(provider, yaml.safe_dump(data))

    def close(self):
        self.client.close()
