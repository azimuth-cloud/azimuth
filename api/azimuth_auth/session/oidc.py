import base64
import binascii
import functools
import itertools
import json
import logging
import time

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
        self._token_url = token_url
        self._userinfo_url = userinfo_url
        self._userid_claim = userid_claim
        self._username_claim = username_claim
        self._email_claim = email_claim
        self._groups_claim = groups_claim
        self._client_id = client_id
        self._client_secret = client_secret
        self._scope = scope
        self._verify_ssl = verify_ssl
        self._token = token
        self._logger = logging.getLogger(__name__)
        # Cached information from the userinfo endpoint
        self._userinfo = None

    def _get_access_token(self):
        """
        Returns an access token to use in the userinfo request.

        This may include refreshing the token if it is expired and a refresh token is available.
        """
        # First, try to parse the token as base64-encoded JSON
        # If this fails, assume the original token is the access token
        self._logger.info("attempting to parse access token")
        try:
            token_data = json.loads(base64.b64decode(self._token))
        except (binascii.Error, json.JSONDecodeError):
            self._logger.warning(
                "failed to parse token as base64-encoded JSON - "
                "treating as string access token"
            )
            return self._token
        # If there is no access token, assume the original token is the access token
        # but just happens to be a base64-encoded JSON string :shrugs:
        if "access_token" not in token_data:
            self._logger.warning(
                "access token not present in token data - "
                "treating as string access token"
            )
            return self._token
        # If there is no refresh token, just return the access token
        if "refresh_token" not in token_data:
            self._logger.warning(
                "no refresh token present in token data - "
                "using existing access token"
            )
            return token_data["access_token"]
        # Check if there is a valid expiry time in the token data
        try:
            expires_at = float(token_data["expires_at"])
        # If there isn't, just return the access token
        except:
            self._logger.warning(
                "unable to determine access token expiry time - "
                "using existing access token"
            )
            return token_data["access_token"]
        # If there is and the token is still valid, return it
        if expires_at > time.time():
            self._logger.info("existing access token is still valid")
            return token_data["access_token"]
        # If we get to here, the access token is expired but we have a refresh token
        # So use the refresh token to get a new access token
        self._logger.info("current access token has expired - using refresh token")
        client = oauthlib.oauth2.WebApplicationClient(self._client_id)
        response = httpx.post(
            self._token_url,
            data = dict(
                oauthlib.common.urldecode(
                    client.prepare_refresh_body(
                        refresh_token = token_data["refresh_token"],
                        scope = self._scope,
                        include_client_id = True,
                        client_id = self._client_id,
                        client_secret = self._client_secret
                    )
                )
            ),
            headers = {
                "Accept": "application/json",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            verify = self._verify_ssl
        )
        # For any client failures, force a reauthentication
        if response.is_client_error:
            self._logger.warning("failed to obtain new access token using refresh token")
            raise errors.AuthenticationError("Your session has expired.")
        response.raise_for_status()
        token_data = client.parse_request_body_response(response.text, scope = self._scope)
        # Update the stored token and return the access token
        self._logger.info("storing updated token data")
        self._token = base64.b64encode(json.dumps(token_data).encode()).decode()
        return token_data["access_token"]

    def _fetch_userinfo(self):
        if not self._userinfo:
            access_token = self._get_access_token()
            self._logger.info("fetching OIDC userinfo")
            response = httpx.get(
                self._userinfo_url,
                headers = {
                    "Accept": "application/json",
                    "Authorization": f"Bearer {access_token}",
                }
            )
            response.raise_for_status()
            self._userinfo = response.json()
        return self._userinfo

    def token(self):
        return self._token

    @convert_httpx_exceptions
    def user(self):
        # We populate the user from the OIDC userinfo
        userinfo = self._fetch_userinfo()
        self._logger.info("extracting user claims from OIDC userinfo")
        try:
            return dto.User(
                userinfo[self._userid_claim],
                userinfo[self._username_claim],
                userinfo[self._email_claim]
            )
        except KeyError:
            # If the user does not have the required claims, log the error and deny access
            # The sub claim should ALWAYS be present, so use that to identify the user
            self._logger.exception("required claim missing for user '%s'", userinfo["sub"])
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
        user_groups = self._fetch_userinfo().get(self._groups_claim, [])
        if user_groups:
            self._logger.info("[%s] found groups - %s", user.username, ",".join(user_groups))
        else:
            self._logger.warning("[%s] user does not have any groups", user.username)
            # If the user has no groups, there is no point looking for tenancies
            return
        # Search for the tenancy namespaces that the user is permitted to use
        self._logger.info("[%s] searching for tenancy namespaces", user.username)
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
                self._logger.warning(
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
                self._logger.warning(
                    "namespace '%s' has new-style and legacy tenancy ID labels with different values",
                    ns_name
                )
            # If the same tenancy ID has appeared on a previous namespace, emit a warning and skip
            if tenancy_id in seen_tenancy_ids:
                self._logger.error("tenancy ID '%s' appears on multiple namespaces", tenancy_id)
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
                self._logger.warning("namespace '%s' has no OIDC group annotation", ns_name)
                continue
            if tenancy_group not in user_groups:
                # This is not an exceptional condition so no need to log
                continue

            # If we get to here, the user is allowed to use the tenancy!
            yield dto.Tenancy(tenancy_id, tenancy_name)

    # TODO(mkjpryor)
    # Implement SSH key management by reading/writing public keys stored in configmaps

    # TODO(mkjpryor)
    # Implement cloud credential retrieval from a secret with a known type and/or label
