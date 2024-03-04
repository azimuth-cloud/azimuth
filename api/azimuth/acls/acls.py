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

    If the annotation is present but empty then we treat it is as if it were not
    present at all.
    """
    annotations = raw.get("metadata", {}).get("annotations", {})

    # If no ACL annotations are found then access is granted
    if not any(k in annotations for k in ACL_KEYS):
        return True
    # Deny IDs list takes priority over allow IDs list and any regex patterns
    if ACL_DENY_IDS_KEY in annotations:
        value = annotations[ACL_DENY_IDS_KEY]
        if value != "":
            # Split into list and strip any whitespace between IDs
            denied_tenancies = [t.strip() for t in value.split(",")]
            # Return immediately if access is denied
            if tenancy.id in denied_tenancies:
                return False
    # Allow IDs list takes priority over any regex patterns
    if ACL_ALLOW_IDS_KEY in annotations:
        value = annotations[ACL_ALLOW_IDS_KEY]
        if value != "":
            allowed_tenancies = [t.strip() for t in value.split(",")]
            # Return immediately if allowed since allow by
            # IDs takes priority over deny by regex
            if tenancy.id in allowed_tenancies:
                return True
    # Deny regex takes priority over allow regex
    if ACL_DENY_PATTERN_KEY in annotations:
        pattern = annotations[ACL_DENY_PATTERN_KEY]
        if pattern != "":
            # Return immediately if access is denied
            if re.search(pattern, tenancy.name):
                return False
    if ACL_ALLOW_PATTERN_KEY in annotations:
        pattern = annotations[ACL_ALLOW_PATTERN_KEY]
        if pattern != "":
            # Return immediately since we've already checked all deny
            # annotations by this point so there won't be conflicts
            if re.search(pattern, tenancy.name):
                return True

    # If either 'allow' annotation is present and non-empty then default to deny
    return not (
        (ACL_ALLOW_IDS_KEY in annotations and annotations[ACL_ALLOW_IDS_KEY] != "") or
        (ACL_ALLOW_PATTERN_KEY in annotations and annotations[ACL_ALLOW_PATTERN_KEY] != "")
    )
