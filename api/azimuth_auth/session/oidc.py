import base64
import binascii
import functools
import itertools
import json
import logging

import httpx

import oauthlib.common
import oauthlib.oauth2

import easykube

from . import base, dto, errors


# The labels that indicate a namespace is a tenancy namespace
# A legacy stackhpc.com label and a new-style azimuth-cloud.io label are both supported
TENANCY_ID_LABEL = "tenant.azimuth-cloud.io/id"
TENANCY_ID_LABEL_LEGACY = "azimuth.stackhpc.com/tenant-id"
# The name of the optional annotation setting the tenancy name
TENANCY_NAME_ANNOTATION = "tenant.azimuth-cloud.io/name"
# The annotation indicating which OIDC group grants access
TENANCY_GROUP_ANNOTATION = "tenant.azimuth-cloud.io/oidc-group"
# The label used to identify cloud credentials
# The value is the name of the provider that is able to consume the credential
CLOUD_CREDENTIAL_PROVIDER_LABEL = "credential.azimuth-cloud.io/provider"


logger = logging.getLogger(__name__)


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
                raise errors.ObjectNotFoundError("The requested resource could not be found.")
            elif exc.response.status_code == 409:
                raise errors.InvalidOperationError(str(exc))
            else:
                raise errors.CommunicationError("Error contacting OIDC issuer.") from exc
        except httpx.HTTPError as exc:
            raise errors.CommunicationError("Could not connect to OIDC issuer.") from exc
    return wrapper


class Auth(httpx.Auth):
    """
    Authentication class that consumes the token produced by the OIDC authenticator.
    """
    requires_response_body = True

    def __init__(self, token_url, client_id, client_secret, scope, token):
        self.token_url = token_url
        self.client_id = client_id
        self.client_secret = client_secret
        self.scope = scope
        self.token = token
        self.access_token, self.refresh_token = self._parse_token(token)

    def _parse_token(self, token):
        """
        Parse the given token and return an access token and refresh token, if available.

        The given token is either a raw access token or a base64-encoded JSON blob containing
        the full token data, as returned by the OIDC authenticator.
        """
        # First, try to parse the token as base64-encoded JSON
        # If this fails, assume the original token is the access token
        logger.info("attempting to parse token")
        try:
            token_data = json.loads(base64.b64decode(token))
        except (binascii.Error, json.JSONDecodeError):
            logger.warning(
                "failed to parse token as base64-encoded JSON - "
                "treating as string access token"
            )
            return token, None
        # If there is no access token in the decoded data, assume the original token is the
        # access token but just happens to be a base64-encoded JSON string :shrugs:
        if "access_token" not in token_data:
            logger.warning(
                "access_token not present in token data - "
                "treating as string access token"
            )
            return token, None
        # If there is no refresh token in the token data, log that
        if "refresh_token" not in token_data:
            logger.warning("no refresh token present in token data")
        # Return the access and optional refresh tokens
        return token_data["access_token"], token_data.get("refresh_token")

    def _refresh_token_request(self):
        client = oauthlib.oauth2.WebApplicationClient(self.client_id)
        return httpx.Request(
            "POST",
            self.token_url,
            data = dict(
                oauthlib.common.urldecode(
                    client.prepare_refresh_body(
                        refresh_token = self.refresh_token,
                        scope = self.scope,
                        include_client_id = True,
                        client_id = self.client_id,
                        client_secret = self.client_secret
                    )
                )
            ),
            headers = {
                "Accept": "application/json",
                "Content-Type": "application/x-www-form-urlencoded",
            }
        )

    def _update_tokens(self, response):
        # If the refresh response was a client error, log it but don't update the tokens
        if response.is_client_error:
            logger.warning("failed to refresh access token")
            return
        # Raise any non-client errors
        response.raise_for_status()
        logger.info("extract and store updated tokens")
        client = oauthlib.oauth2.WebApplicationClient(self.client_id)
        token_data = client.parse_request_body_response(response.text, scope = self.scope)
        self.token = base64.b64encode(json.dumps(token_data).encode()).decode()
        self.access_token = token_data["access_token"]
        self.refresh_token = token_data.get("refresh_token")

    def auth_flow(self, request):
        # Add the current access token to the request as a bearer token
        request.headers["Authorization"] = f"Bearer {self.access_token}"
        response = yield request
        # Refresh the token and retry the request, if possible
        if self.refresh_token and response.status_code == 401:
            logger.info("attempting to refresh OIDC token")
            response = yield self._refresh_token_request()
            self._update_tokens(response)
            logger.info("retrying request with refreshed token")
            request.headers["Authorization"] = f"Bearer {self.access_token}"
            yield request


class Provider(base.Provider):
    """
    Provider that understands OpenID Connect tokens.
    """
    def __init__(
        self,
        token_url: str,
        userinfo_url: str,
        userid_claim: str,
        username_claim: str,
        email_claim: str,
        groups_claim: str,
        client_id: str,
        client_secret: str,
        scope: str,
        verify_ssl: bool
    ):
        self.token_url = token_url
        self.userinfo_url = userinfo_url
        self.userid_claim = userid_claim
        self.username_claim = username_claim
        self.email_claim = email_claim
        self.groups_claim = groups_claim
        self.client_id = client_id
        self.client_secret = client_secret
        self.scope = scope
        self.verify_ssl = verify_ssl
        # Initialise an easykube client from the environment
        self.ekclient = easykube.Configuration.from_environment().sync_client()

    def from_token(self, token):
        return Session(
            self.ekclient,
            self.token_url,
            self.userinfo_url,
            self.userid_claim,
            self.username_claim,
            self.email_claim,
            self.groups_claim,
            self.client_id,
            self.client_secret,
            self.scope,
            self.verify_ssl,
            token
        )


class Session(base.Session):
    """
    Session implementation that understands OIDC tokens.
    """
    def __init__(
        self,
        ekclient: easykube.SyncClient,
        token_url: str,
        userinfo_url: str,
        userid_claim: str,
        username_claim: str,
        email_claim: str,
        groups_claim: str,
        client_id: str,
        client_secret: str,
        scope: str,
        verify_ssl: bool,
        token: str
    ):
        self._ekclient = ekclient
        self._userinfo_url = userinfo_url
        self._userid_claim = userid_claim
        self._username_claim = username_claim
        self._email_claim = email_claim
        self._groups_claim = groups_claim
        self._verify_ssl = verify_ssl
        # Build the httpx auth object using the parameters
        self._auth = Auth(token_url, client_id, client_secret, scope, token)

    @functools.cached_property
    def _userinfo(self):
        logger.info("fetching OIDC userinfo")
        response = httpx.get(
            self._userinfo_url,
            auth = self._auth,
            headers = { "Accept": "application/json" },
            verify = self._verify_ssl
        )
        response.raise_for_status()
        return response.json()

    def token(self):
        return self._auth.token

    @convert_httpx_exceptions
    def user(self):
        # We populate the user from the OIDC userinfo
        logger.info("extracting user claims from OIDC userinfo")
        try:
            return dto.User(
                self._userinfo[self._userid_claim],
                self._userinfo[self._username_claim],
                self._userinfo[self._email_claim]
            )
        except KeyError:
            # If the user does not have the required claims, log the error and deny access
            # The sub claim should ALWAYS be present, so use that to identify the user
            logger.exception("required claim missing for user '%s'", self._userinfo["sub"])
            raise errors.PermissionDeniedError("Permission denied.")

    @convert_httpx_exceptions
    def tenancies(self):
        #####
        # NOTE(mkjpryor)
        # Look for tenancy namespaces that correspond to the user's groups
        #
        # We find tenancy namespaces by looking for the presence of a tenant ID label
        # There are azimuth-cloud.io and (legacy) stackhpc.com variants of this label
        #
        # We decide if the user is permitted to access the namespace by checking if they have the
        # group specified in the OIDC group annotation, where the absence of the annotation means
        # no OIDC groups have access
        # We use an annotation rather than a label because group names may contain characters that
        # are not valid in a label value, e.g. Keycloak groups contain '/'
        #####
        user = self.user()
        # Get the user's groups from the OIDC userinfo
        user_groups = self._userinfo.get(self._groups_claim, [])
        if user_groups:
            logger.info("[%s] found groups - %s", user.username, ",".join(user_groups))
        else:
            logger.warning("[%s] user does not have any groups", user.username)
            # If the user has no groups, there is no point looking for tenancies
            return
        # Search for the tenancy namespaces that the user is permitted to use
        logger.info("[%s] searching for tenancy namespaces", user.username)
        namespaces = self._ekclient.api("v1").resource("namespaces")
        # We want to de-dupe namespaces that have both labels
        seen_namespaces = set()
        # We want to produce a warning if we see two different namespaces with the same ID
        seen_tenancy_ids = set()
        for ns in itertools.chain(
            # Unfortunately, two labels with an OR relationship means two queries
            namespaces.list(labels = {TENANCY_ID_LABEL: easykube.PRESENT}),
            namespaces.list(labels = {TENANCY_ID_LABEL_LEGACY: easykube.PRESENT})
        ):
            # If we have already seen the namespace, that means it has both labels so skip it
            ns_name = ns["metadata"]["name"]
            if ns_name in seen_namespaces:
                logger.warning(
                    "namespace '%s' has both new-style and legacy tenancy ID labels",
                    ns_name
                )
                continue
            else:
                seen_namespaces.add(ns_name)

            # Use the value of the label as the ID, with the new-style label taking precedence
            # Note that we know at least one of the labels is definitely present
            labels = ns["metadata"]["labels"]
            tenancy_id_legacy = labels.get(TENANCY_ID_LABEL_LEGACY)
            tenancy_id = labels.get(TENANCY_ID_LABEL, tenancy_id_legacy)
            # If the namespace has both labels and the values are different, emit a warning
            if tenancy_id_legacy and tenancy_id != tenancy_id_legacy:
                logger.warning(
                    "namespace '%s' has new-style and legacy tenancy ID labels with different values",
                    ns_name
                )
            # If the same tenancy ID has appeared on a previous namespace, emit a warning and skip
            if tenancy_id in seen_tenancy_ids:
                logger.error("tenancy ID '%s' appears on multiple namespaces", tenancy_id)
                continue
            else:
                seen_tenancy_ids.add(tenancy_id)

            # Allow the tenancy name to come from an annotation, if present
            # If not, use the tenancy name with the 'az-' prefix removed
            annotations = ns["metadata"].get("annotations", {})
            tenancy_name = annotations.get(TENANCY_NAME_ANNOTATION, ns_name.removeprefix("az-"))

            # Check if the user has the required group for the tenancy
            # No annotation means no OIDC users are permitted
            tenancy_group = annotations.get(TENANCY_GROUP_ANNOTATION)
            if not tenancy_group:
                logger.warning("namespace '%s' has no OIDC group annotation", ns_name)
                continue
            if tenancy_group not in user_groups:
                # This is not an exceptional condition so no need to log
                continue

            # If we get to here, the user is allowed to use the tenancy!
            yield dto.Tenancy(tenancy_id, tenancy_name)

    def _iter_namespaces(self, tenancy_id):
        # Returns an iterator over the tenancy namespaces
        # This avoids the second query for the legacy label unless required
        namespaces = self._ekclient.api("v1").resource("namespaces")
        yield from namespaces.list(labels = {TENANCY_ID_LABEL: tenancy_id})
        yield from namespaces.list(labels = {TENANCY_ID_LABEL_LEGACY: tenancy_id})

    def credential(self, tenancy_id):
        # Try to find a cloud credential in a secret with a known label in the tenancy namespace
        # If no such credential exists, return a null credential so that the null cloud provider
        # can still be used to deploy Kubernetes apps
        user = self.user()
        logger.info("[%s] locating namespace for tenant ID '%s'", user.username, tenancy_id)
        try:
            ns = next(self._iter_namespaces(tenancy_id))
        except StopIteration:
            logger.warning("[%s] no namespace for tenant ID '%s'", user.username, tenancy_id)
            return dto.Credential("null", {})
        else:
            namespace = ns["metadata"]["name"]
            tenancy_name = (
                ns["metadata"]
                    .get("annotations", {})
                    .get(TENANCY_NAME_ANNOTATION, namespace.removeprefix("az-"))
            )
        # Find the first secret in the namespace with the required label
        logger.info("[%s] [%s] searching for credential secret", user.username, tenancy_name)
        secrets = self._ekclient.api("v1").resource("secrets")
        secret = secrets.first(
            labels = { CLOUD_CREDENTIAL_PROVIDER_LABEL: easykube.PRESENT },
            namespace = namespace
        )
        if not secret:
            logger.warning(
                "[%s] [%s] no credential secrets available for tenant",
                user.username,
                tenancy_name
            )
            return dto.Credential("null", {})
        secret_name = secret["metadata"]["name"]
        # Take the provider name from the label value
        credential_provider = secret["metadata"]["labels"][CLOUD_CREDENTIAL_PROVIDER_LABEL]
        logger.info(
            "[%s] [%s] found credential secret '%s' for provider '%s'",
            user.username,
            tenancy_name,
            secret_name,
            credential_provider
        )
        # Use the first data item as the credential data
        try:
            credential_data = next(iter(secret.get("data", {}).values()))
        except StopIteration:
            logger.warning(
                "[%s] [%s] credential secret '%s' has no data",
                user.username,
                tenancy_name,
                secret_name
            )
            return dto.Credential("null", {})
        return dto.Credential(
            credential_provider,
            # The data from the secret is base64-encoded
            base64.b64decode(credential_data).decode()
        )

    # TODO(mkjpryor)
    # Implement SSH key management by reading/writing public keys stored in configmaps
