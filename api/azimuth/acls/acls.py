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
    """
    annotations = raw.get("metadata", {}).get("annotations", {})

    # If no ACL annotations are found then access is granted
    if not any(k in annotations for k in ACL_KEYS):
        return True
    # Deny IDs list takes priority over allow IDs list and any regex patterns
    if ACL_DENY_IDS_KEY in annotations:
        # Split into list and strip any whitespace between IDs
        denied_tenancies = [t.strip() for t in annotations[ACL_DENY_IDS_KEY].split(",")]
        # Return immediately if access is denied
        if tenancy.id in denied_tenancies:
            return False
    # Allow IDs list takes priority over any regex patterns
    if ACL_ALLOW_IDS_KEY in annotations:
        allowed_tenancies = [
            t.strip() for t in annotations[ACL_ALLOW_IDS_KEY].split(",")
        ]
        # Return immediately if allowed since allow by
        # IDs takes priority over deny by regex
        if tenancy.id in allowed_tenancies:
            return True
    # Deny regex takes priority over allow regex
    if ACL_DENY_PATTERN_KEY in annotations:
        pattern = annotations[ACL_DENY_PATTERN_KEY]
        # Return immediately if access is denied
        if re.search(pattern, tenancy.name):
            return False
    if ACL_ALLOW_PATTERN_KEY in annotations:
        pattern = annotations[ACL_ALLOW_PATTERN_KEY]
        # Return immediately since we've already checked all deny
        # annotations by this point so there won't be conflicts
        if re.search(pattern, tenancy.name):
            return True

    return (
        ACL_ALLOW_IDS_KEY not in annotations and
        ACL_ALLOW_PATTERN_KEY not in annotations
    )
