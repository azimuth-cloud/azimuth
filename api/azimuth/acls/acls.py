import re
import logging

LOG = logging.getLogger(__name__)

ACL_ALLOW_IDS_KEY = "acl.azimuth.stackhpc.com/allow-list"
ACL_DENY_IDS_KEY = "acl.azimuth.stackhpc.com/deny-list"
ACL_ALLOW_PATTERN_KEY = "acl.azimuth.stackhpc.com/allow-regex"
ACL_DENY_PATTERN_KEY = "acl.azimuth.stackhpc.com/deny-regex"
ACL_KEYS = [
    ACL_ALLOW_IDS_KEY,
    ACL_DENY_IDS_KEY,
    ACL_ALLOW_PATTERN_KEY,
    ACL_DENY_PATTERN_KEY,
]


def allowed_by_acls(raw, tenancy):
    """
    Returns true if the application template is permitted in the given tenancy.
    The regex pattern matching starts at the beginning of the string (i.e uses
    re.match rather than re.search), therefore to match e.g. both 'tenancy-test-1'
    and 'tenancy-test-2' tenancies the regex pattern should be '.*-test-'.
    """

    annotations = raw.get("metadata").get("annotations")
    annotation_keys = annotations.keys()
    # Default to allow access unless any 'allow' type annotation are present since
    # these annotations indicate an intention to deny access to non-matches.
    is_allowed = not (
        ACL_ALLOW_IDS_KEY in annotation_keys or ACL_ALLOW_PATTERN_KEY in annotation_keys
    )

    # If no ACL annotations are found then access is granted
    if not any(k in annotation_keys for k in ACL_KEYS):
        return True
    # Deny IDs list takes priority over allow IDs list and any regex patterns
    if ACL_DENY_IDS_KEY in annotation_keys:
        denied_tenancies = annotations[ACL_DENY_IDS_KEY].split(",")
        # Return immediately if access is denied
        return not tenancy.id in denied_tenancies
    if ACL_ALLOW_IDS_KEY in annotation_keys:
        allowed_tenancies = annotations[ACL_ALLOW_IDS_KEY].split(",")
        # Don't return immediately as we want to check allow regex pattern too
        is_allowed = tenancy.id in allowed_tenancies
    # Deny regex takes priority over allow regex
    if ACL_DENY_PATTERN_KEY in annotation_keys:
        pattern = annotations[ACL_DENY_PATTERN_KEY]
        # Return immediately if access is denied
        return re.match(pattern, tenancy.name) is None
    if ACL_ALLOW_PATTERN_KEY in annotation_keys:
        pattern = annotations[ACL_ALLOW_PATTERN_KEY]
        is_allowed = re.match(pattern, tenancy.name) is not None

    return is_allowed
