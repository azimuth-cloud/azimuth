import logging
import re

import easykube

from .provider import dto

MANAGED_BY_LABEL = "app.kubernetes.io/managed-by"
# A legacy stackhpc.com label and a new-style azimuth-cloud.io label are both supported
TENANCY_ID_LABEL = "tenant.azimuth-cloud.io/id"
TENANCY_ID_LABEL_LEGACY = "azimuth.stackhpc.com/tenant-id"


logger = logging.getLogger(__name__)


class DuplicateTenancyIDError(Exception):
    """
    Raised when there are multiple namespaces with the same tenancy ID.
    """

    def __init__(self, tenancy_id: str):
        super().__init__(f"multiple tenancy namespaces found with ID '{tenancy_id}'")


class NamespaceOwnershipError(Exception):
    """
    Raised when there is a conflict in the namespace ownership.
    """

    def __init__(self, namespace: str, expected_owner: str, current_owner: str):
        super().__init__(
            f"expected namespace '{namespace}' to be owned by tenant "
            f"'{expected_owner}' but found '{current_owner}'"
        )


def sanitise(value):
    """
    Returns a sanitised form of the given value suitable for Kubernetes resource names.
    """
    return re.sub(r"[^a-z0-9]+", "-", str(value).lower()).strip("-")


def unique_namespaces(ekresource, tenancy_id):
    """
    Returns an iterator over the unique namespaces for the given tenancy ID.
    """
    seen_namespaces = set()
    for namespace in ekresource.list(labels={TENANCY_ID_LABEL: tenancy_id}):
        # We won't see any duplicate namespaces in this first loop
        seen_namespaces.add(namespace["metadata"]["name"])
        yield namespace
    for namespace in ekresource.list(labels={TENANCY_ID_LABEL_LEGACY: tenancy_id}):
        # We might see namespaces in this loop that appeared in the previous loop, if a
        # namespace has both labels
        ns_name = namespace["metadata"]["name"]
        if ns_name in seen_namespaces:
            logger.warning(
                f"namespace '{ns_name}' has both new-style and legacy tenancy ID labels"
            )
            continue
        else:
            yield namespace


def get_namespace(ekclient, tenancy: dto.Tenancy) -> str:
    """
    Returns the correct namespace to use for the given tenancy.
    """
    tenancy_id = sanitise(tenancy.id)
    tenancy_name = sanitise(tenancy.name)
    ekresource = ekclient.api("v1").resource("namespaces")
    expected_namespace = f"az-{tenancy_name}"
    # Try to find the namespace that is labelled with the tenant ID
    # We require that the namespace is unique
    namespaces = list(unique_namespaces(ekresource, tenancy_id))
    # If there is exactly one namespace, return it
    if len(namespaces) == 1:
        found_namespace = namespaces[0]["metadata"]["name"]
        logger.info(f"using namespace '{found_namespace}' for tenant '{tenancy_id}'")
        if found_namespace != expected_namespace:
            logger.warning(
                f"expected namespace '{expected_namespace}' for "
                f"tenant '{tenancy_id}', but found '{found_namespace}'"
            )
        return found_namespace
    # If there are multiple namespaces with the ID, bail
    elif len(namespaces) > 1:
        raise DuplicateTenancyIDError(tenancy_id)
    # If there is no namespace labelled with the tenant ID, find the namespace
    # that uses the standard naming convention
    try:
        namespace = ekresource.fetch(expected_namespace)
    except easykube.ApiError as exc:
        if exc.status_code == 404:
            # Even if the namespace doesn't exist, it is still the correct one to use
            logger.info(
                f"using namespace '{expected_namespace}' for tenant '{tenancy_id}'"
            )
            return expected_namespace
        else:
            raise
    # Before returning it, verify that it isn't labelled with another tenancy ID
    labels = namespace["metadata"].get("labels", {})
    owner_id = labels.get(TENANCY_ID_LABEL, labels.get(TENANCY_ID_LABEL_LEGACY))
    if not owner_id or owner_id == tenancy_id:
        logger.info(f"using namespace '{expected_namespace}' for tenant '{tenancy_id}'")
        return expected_namespace
    else:
        raise NamespaceOwnershipError(expected_namespace, tenancy_id, owner_id)


def ensure_namespace(ekclient, namespace: str, tenancy: dto.Tenancy):
    """
    Ensures that the specified namespace exists and is labelled correctly for
    the specified tenancy.

    Assumes that the namespace name was discovered using ``get_namespace``.
    """
    # First try to patch the namespace to add the label
    ekclient.api("v1").resource("namespaces").create_or_patch(
        namespace,
        {
            "metadata": {
                "labels": {
                    MANAGED_BY_LABEL: "azimuth",
                    TENANCY_ID_LABEL: sanitise(tenancy.id),
                },
            },
        },
    )
