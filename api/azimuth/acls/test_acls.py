from unittest import TestCase
from .acls import (
    ACL_KEYS,
    ACL_ALLOW_IDS_KEY,
    ACL_ALLOW_PATTERN_KEY,
    ACL_DENY_IDS_KEY,
    ACL_DENY_PATTERN_KEY,
    allowed_by_acls,
)

from ..provider.dto import Tenancy


class ACLTestCase(TestCase):

    def assert_allowed(self, resource, tenancy):
        """Helper method to make logic clearer"""
        self.assertTrue(allowed_by_acls(resource, tenancy))

    def assert_denied(self, resource, tenancy):
        """Helper method to make logic clearer"""
        self.assertFalse(allowed_by_acls(resource, tenancy))

    # Check that all tenancies are allowed when no ACL annotations are present
    def test_no_annotations(self):
        tenancies = [Tenancy(id=f"test-id-{i}", name=f"name-{i}") for i in range(3)]
        test_resource = {"metadata": {"annotations": {}}}
        for t in tenancies:
            self.assert_allowed(test_resource, t)

    # Check that all tenancies are allowed when all ACL annotations are present but empty
    def test_empty_annotations(self):
        tenancies = [Tenancy(id=f"test-id-{i}", name=f"name-{i}") for i in range(3)]
        test_resource = {"metadata": {"annotations": {k: "" for k in ACL_KEYS}}}
        for t in tenancies:
            self.assert_allowed(test_resource, t)

    # Check that filtering by denied IDs works
    def test_deny_ids(self):
        test_resource = {
            "metadata": {
                "annotations": {
                    # Also check that whitespace stripping works within lists
                    ACL_DENY_IDS_KEY: " test-id-1 , test-id-2 "
                }
            }
        }
        self.assert_denied(test_resource, Tenancy(id="test-id-1", name=""))
        self.assert_denied(test_resource, Tenancy(id="test-id-2", name=""))
        self.assert_allowed(test_resource, Tenancy(id="test-id-3", name=""))

    # Check that filtering by allowed IDs works
    def test_allow_ids(self):
        test_resource = {
            "metadata": {"annotations": {ACL_ALLOW_IDS_KEY: "test-id-1,test-id-2"}}
        }
        self.assert_allowed(test_resource, Tenancy(id="test-id-1", name=""))
        self.assert_allowed(test_resource, Tenancy(id="test-id-2", name=""))
        self.assert_denied(test_resource, Tenancy(id="test-id-3", name=""))

    # Check that filtering by allowed name pattern works
    def test_allow_pattern(self):
        test_resource = {"metadata": {"annotations": {ACL_ALLOW_PATTERN_KEY: "prod-"}}}
        self.assert_allowed(test_resource, Tenancy(id="", name=f"prod-123"))
        self.assert_allowed(test_resource, Tenancy(id="", name=f"test-prod-2"))
        self.assert_denied(test_resource, Tenancy(id="", name=f"staging"))

    # Check that filtering by denied name patterm works
    def test_deny_pattern(self):
        test_resource = {"metadata": {"annotations": {ACL_DENY_PATTERN_KEY: "prod-"}}}
        self.assert_denied(test_resource, Tenancy(id="", name="prod-123"))
        self.assert_denied(test_resource, Tenancy(id="", name=f"test-prod-2"))
        self.assert_allowed(test_resource, Tenancy(id="", name=f"staging-123"))

    # Check that presence of any 'allow' key triggers deny by default
    def test_default_deny_with_allows(self):
        test_resource = {"metadata": {"annotations": {ACL_ALLOW_IDS_KEY: "abc"}}}
        self.assert_denied(test_resource, Tenancy("id-1", "name-1"))
        test_resource = {"metadata": {"annotations": {ACL_ALLOW_PATTERN_KEY: "def"}}}
        self.assert_denied(test_resource, Tenancy("id-2", "name-2"))
        test_resource = {
            "metadata": {
                "annotations": {ACL_ALLOW_IDS_KEY: "abc", ACL_ALLOW_PATTERN_KEY: "def"}
            }
        }
        self.assert_denied(test_resource, Tenancy("id-3", "name-3"))

    # Check that deny by ID takes priority over allow by ID
    def test_deny_vs_allow_ids(self):
        test_resource = {
            "metadata": {
                "annotations": {
                    ACL_DENY_IDS_KEY: "id-1",
                    ACL_ALLOW_IDS_KEY: "id-1,id-2",
                }
            }
        }
        self.assert_denied(test_resource, Tenancy("id-1", ""))
        self.assert_allowed(test_resource, Tenancy("id-2", ""))
        # Denied by default since an allow annotation is present
        self.assert_denied(test_resource, Tenancy("id-3", ""))

    # Check that deny regex takes priotiry over allow regex
    def test_deny_vs_allow_regex(self):
        test_resource = {
            "metadata": {
                "annotations": {
                    ACL_DENY_PATTERN_KEY: "prod",
                    ACL_ALLOW_PATTERN_KEY: "(prod|staging)",
                }
            }
        }
        self.assert_denied(test_resource, Tenancy("", "prod"))
        self.assert_allowed(test_resource, Tenancy("", "staging"))
        # Denied by default since an allow annotation is present
        self.assert_denied(test_resource, Tenancy("", "dev"))

    # Check that deny by ID and regex are both checked
    def test_deny_ids_and_regex(self):
        test_resource = {
            "metadata": {
                "annotations": {
                    ACL_DENY_IDS_KEY: "id-1",
                    ACL_DENY_PATTERN_KEY: "prod",
                }
            }
        }
        self.assert_denied(test_resource, Tenancy("id-1", ""))
        self.assert_denied(test_resource, Tenancy("", "prod"))
        self.assert_allowed(test_resource, Tenancy("id-2", ""))
        self.assert_allowed(test_resource, Tenancy("", "staging"))

    # Check that deny by ID and regex are both checked
    def test_allow_ids_and_regex(self):
        test_resource = {
            "metadata": {
                "annotations": {
                    ACL_ALLOW_IDS_KEY: "id-2",
                    ACL_ALLOW_PATTERN_KEY: "staging",
                }
            }
        }
        self.assert_denied(test_resource, Tenancy("id-1", ""))
        self.assert_denied(test_resource, Tenancy("", "prod"))
        self.assert_allowed(test_resource, Tenancy("id-2", ""))
        self.assert_allowed(test_resource, Tenancy("", "staging"))

    # Check all annotations at once
    def test_all_the_things(self):
        test_resource = {
            "metadata": {
                "annotations": {
                    ACL_DENY_IDS_KEY: "id-1",
                    ACL_DENY_PATTERN_KEY: "prod",
                    ACL_ALLOW_IDS_KEY: "id-2",
                    ACL_ALLOW_PATTERN_KEY: "staging",
                }
            }
        }
        # Denied by ID
        self.assert_denied(test_resource, Tenancy("id-1", ""))
        # Denied by regex
        self.assert_denied(test_resource, Tenancy("", "prod"))
        # Denied by regex
        self.assert_denied(test_resource, Tenancy("", "prod-staging"))
        # Allowed by ID
        self.assert_allowed(test_resource, Tenancy("id-2", ""))
        # Allowed by regex
        self.assert_allowed(test_resource, Tenancy("", "staging-1"))
        # Allowed by regex
        self.assert_allowed(test_resource, Tenancy("", "staging-2"))
        # Denied by default because allows are present
        self.assert_denied(test_resource, Tenancy("id-3", ""))
        # Denied by default because allows are present
        self.assert_denied(test_resource, Tenancy("", "dev"))
        # Allowed since IDs take priority over regex matches
        self.assert_allowed(test_resource, Tenancy("id-2", "prod"))
