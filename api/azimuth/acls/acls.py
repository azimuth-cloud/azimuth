import logging
import re

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
    deny_ids_annotation = annotations.get(ACL_DENY_IDS_KEY)
    if deny_ids_annotation:
        # Split into list and strip any whitespace between IDs
        denied_tenancies = [t.strip() for t in deny_ids_annotation.split(",")]
        # Return immediately if access is denied
        if tenancy.id in denied_tenancies:
            return False

    # Allow IDs list takes priority over any regex patterns
    allow_ids_annotation = annotations.get(ACL_ALLOW_IDS_KEY)
    if allow_ids_annotation:
        allowed_tenancies = [t.strip() for t in allow_ids_annotation.split(",")]
        # Return immediately if allowed since allow by
        # IDs takes priority over deny by regex
        if tenancy.id in allowed_tenancies:
            return True

    # Deny regex takes priority over allow regex
    deny_pattern = annotations.get(ACL_DENY_PATTERN_KEY)
    # Return immediately if access is denied
    if deny_pattern and re.search(deny_pattern, tenancy.name):
        return False

    # Check allow regex last
    allow_pattern = annotations.get(ACL_ALLOW_PATTERN_KEY)
    if allow_pattern and re.search(allow_pattern, tenancy.name):
        # Return immediately since we've already checked all deny
        # annotations by this point so there won't be conflicts
        return True

    # If either 'allow' annotation is present and non-empty then default to deny
    return not (
        annotations.get(ACL_ALLOW_IDS_KEY) or annotations.get(ACL_ALLOW_PATTERN_KEY)
    )
