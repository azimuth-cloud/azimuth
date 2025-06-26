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

    In this implementation we do not use the OIDC ID token to identify the user. Instead, we
    use the OAuth2 access token to query the OIDC userinfo endpoint on every request.

    This decision was made, at the expense of more requests to the IDP, for a number of reasons:

      * It means we do not have to deal with parsing JWTs and all the things that come with
        that, e.g. fetching and caching JWKS keys and knowing when they have been rotated.
      * We don't have to decide how long we are happy working with stale user information due
        to ID token caching. Changes to user information at the IDP, and in particular group
        memberships, are reflected immediately.
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
        eknamespaces = self._ekclient.api("v1").resource("namespaces")
        # Collect the namespaces indexed by ID
        # This is a map of tenancy ID -> a list of namespaces with that ID
        # We do this to avoid non-deterministic behaviour if multiple namespaces have the same ID
        namespaces_by_id = {}
        # We de-dupe namespaces that have both labels as we go
        seen_namespaces = set()
        for ns in itertools.chain(
            # Unfortunately, two labels with an OR relationship means two queries
            eknamespaces.list(labels = {TENANCY_ID_LABEL: easykube.PRESENT}),
            eknamespaces.list(labels = {TENANCY_ID_LABEL_LEGACY: easykube.PRESENT})
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
            # Store the namespace by ID for further processing
            namespaces_by_id.setdefault(tenancy_id, []).append(ns)
        # Process the indexed namespaces
        # We require each list to have size one, or we have an error
        for tenancy_id, namespaces in namespaces_by_id.items():
            if len(namespaces) != 1:
                logger.error("tenancy ID '%s' appears on multiple namespaces", tenancy_id)
                continue

            ns_name = namespaces[0]["metadata"]["name"]

            # Allow the tenancy name to come from an annotation, if present
            # If not, use the tenancy name with the 'az-' prefix removed
            annotations = namespaces[0]["metadata"].get("annotations", {})
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
        # Returns an iterator over the unique tenancy namespaces
        # This avoids the second query for the legacy label unless required
        eknamespaces = self._ekclient.api("v1").resource("namespaces")
        seen_namespaces = set()
        for namespace in eknamespaces.list(labels = {TENANCY_ID_LABEL: tenancy_id}):
            # We won't see any duplicate namespaces in this first loop
            seen_namespaces.add(namespace["metadata"]["name"])
            yield namespace
        for namespace in eknamespaces.list(labels = {TENANCY_ID_LABEL_LEGACY: tenancy_id}):
            if namespace["metadata"]["name"] not in seen_namespaces:
                yield namespace

    def credential(self, tenancy_id, provider):
        #####
        # NOTE(mkjpryor)
        # Credentials are stored in secrets in the tenancy namespace
        # The secrets have a label indicating the provider that they are for
        #
        # If no secret exists with the correct label for the provider, then we are unable
        # to supply a credential for that provider and we return None
        #####
        user = self.user()
        logger.info("[%s] locating namespace for tenant ID '%s'", user.username, tenancy_id)
        # Attempt to find a unique namespace for the tenancy ID
        namespaces = list(self._iter_namespaces(tenancy_id))
        if len(namespaces) > 1:
            logger.error(
                "[%s] multiple namespaces found for tenant ID '%s'",
                user.username,
                tenancy_id
            )
            return None
        elif len(namespaces) < 1:
            logger.warning("[%s] no namespace for tenant ID '%s'", user.username, tenancy_id)
            return None
        else:
            namespace = namespaces[0]["metadata"]["name"]
            tenancy_name = (
                namespaces[0]["metadata"]
                    .get("annotations", {})
                    .get(TENANCY_NAME_ANNOTATION, namespace.removeprefix("az-"))
            )
        # Find a unique secret in the namespace with the required label
        # This is to avoid non-deterministic behaviour when returning the first secret
        logger.info(
            "[%s] [%s] searching for credential secrets for provider '%s'",
            user.username,
            tenancy_name,
            provider
        )
        secrets = list(
            self._ekclient.api("v1").resource("secrets").list(
                labels = { CLOUD_CREDENTIAL_PROVIDER_LABEL: provider },
                namespace = namespace
            )
        )
        if len(secrets) > 1:
            logger.error(
                "[%s] [%s] multiple credential secrets found for provider '%s'",
                user.username,
                tenancy_name,
                provider
            )
            return None
        elif len(secrets) < 1:
            logger.warning(
                "[%s] [%s] no credential secrets available for provider '%s'",
                user.username,
                tenancy_name,
                provider
            )
            return None
        else:
            secret = secrets[0]
        secret_name = secret["metadata"]["name"]
        logger.info(
            "[%s] [%s] found credential secret '%s' for provider '%s'",
            user.username,
            tenancy_name,
            secret_name,
            provider
        )
        # Check that there is exactly one key and return the data from it
        # This is to avoid non-deterministic behaivour when returning the first key
        secret_data = secret.get("data", {}).values()
        if len(secret_data) > 1:
            logger.warning(
                "[%s] [%s] credential secret '%s' has multiple keys",
                user.username,
                tenancy_name,
                secret_name
            )
            return None
        elif len(secret_data) < 1:
            logger.warning(
                "[%s] [%s] credential secret '%s' has no data",
                user.username,
                tenancy_name,
                secret_name
            )
            return None
        else:
            # The data from the secret is base64-encoded
            credential_data = next(iter(secret_data))
            return dto.Credential(provider, base64.b64decode(credential_data).decode())

    # TODO(mkjpryor)
    # Implement SSH key management by reading/writing public keys stored in configmaps
