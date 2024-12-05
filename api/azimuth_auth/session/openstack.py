import functools

import httpx

from ..authenticator.openstack import normalize_auth_url

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
            if exc.response.status_code == 401:
                raise errors.AuthenticationError("Your session has expired.")
            else:
                raise errors.CommunicationError("Error with OpenStack API.") from exc
        except httpx.HTTPError as exc:
            raise errors.CommunicationError("Could not connect to OpenStack API.") from exc
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
    def __init__(
        self,
        auth_url,
        region = None,
        interface = "public",
        verify_ssl = True
    ):
        self.auth_url = normalize_auth_url(auth_url)
        self.region = region
        self.interface = interface
        self.verify_ssl = verify_ssl

    def from_token(self, token: str) -> 'Session':
        return Session(
            httpx.Client(
                auth = OpenStackAuth(token),
                base_url = self.auth_url,
                verify = self.verify_ssl
            ),
            self.auth_url,
            self.region,
            self.interface,
            self.verify_ssl
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

    def token(self):
        return self.client.auth.token

    @convert_httpx_exceptions
    def user(self):
        response = self.client.get(
            "/auth/tokens",
            headers = {"X-Subject-Token": self.client.auth.token},
            params = {"nocatalog": "1"}
        )
        # A 401 or a 404 indicates a failure to validate the token
        if response.status_code in {401, 404}:
            raise errors.AuthenticationError("Your session has expired.")
        response.raise_for_status()
        user_data = response.json()["token"]["user"]
        username = user_data["name"]
        # If the username "looks like" an email address, just use that as the email
        # Otherwise construct a fake email from the username + domain
        if "@" in username:
            user_email = username
        else:
            user_email = f"{username}@{user_data['domain']['name'].lower()}.openstack"
        return dto.User(user_data["id"], username, user_email)

    def ssh_public_key(self):
        raise NotImplementedError

    def update_ssh_public_key(self, public_key):
        raise NotImplementedError

    @convert_httpx_exceptions
    def tenancies(self):
        response = self.client.get("/auth/projects")
        response.raise_for_status()
        return [
            dto.Tenancy(project["id"], project["name"])
            for project in response.json()["projects"]
            # Only include enabled projects
            if project["enabled"]
        ]

    def credential(self, tenancy_id):
        # Return the contents of a clouds.yaml configured to use a token
        data = {
            "clouds": {
                "openstack": {
                    "identity_api_version": 3,
                    "auth_type": "v3token",
                    "auth": {
                        "auth_url": self.auth_url,
                        "token": self.client.auth.token,
                        "project_id": tenancy_id,
                    },
                    "interface": self.interface,
                    "verify": self.verify_ssl,
                },
            },
        }
        if self.region:
            data["clouds"]["openstack"]["region_name"] = self.region
        return dto.Credential("openstack", data)

    def close(self):
        self.client.close()
