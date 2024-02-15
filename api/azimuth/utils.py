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

class TemplateFilterException(Exception):
    pass

def allowed_by_acls(raw, tenancy):
    """
    Returns true if the application template is permitted in the given tenancy.
    The regex pattern matching starts at the beginning of the string (i.e uses
    re.match rather than re.search), therefore to match e.g. both 'tenancy-test-1'
    and 'tenancy-test-2' tenancies the regex pattern should be '.*-test-'.
    """
    
    is_allowed = True    
    annotations = raw.get("metadata").get("annotations")
    annotation_keys = annotations.keys()

    # If no ACL annotations are found then access is granted
    if not any(k in annotation_keys for k in ACL_KEYS):
        pass
    # Deny IDs list takes priority over allow IDs list and any regex patterns
    elif ACL_DENY_IDS_KEY in annotation_keys:
        denied_tenancies = annotations[ACL_DENY_IDS_KEY]
        is_allowed = (not tenancy.id in denied_tenancies)
    elif ACL_ALLOW_IDS_KEY in annotation_keys:
        allowed_tenancies = annotations[ACL_ALLOW_IDS_KEY]
        is_allowed = (tenancy.id in allowed_tenancies)
    # Deny regex takes priority for allow regex
    elif ACL_DENY_PATTERN_KEY in annotation_keys:
        pattern = annotations[ACL_DENY_PATTERN_KEY]
        is_match = (re.match(pattern, tenancy.name) is not None)
        is_allowed = not is_match
    elif ACL_ALLOW_PATTERN_KEY in annotation_keys:
        pattern = annotations[ACL_ALLOW_PATTERN_KEY]
        is_match = (re.match(pattern, tenancy.name) is not None)
        is_allowed = is_match
        
    return is_allowed