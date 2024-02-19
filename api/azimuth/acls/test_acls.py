from unittest import TestCase
from acls import (
    ACL_ALLOW_IDS_KEY,
    ACL_ALLOW_PATTERN_KEY,
    ACL_DENY_IDS_KEY,
    ACL_DENY_PATTERN_KEY,
    allowed_by_acls,
)

from ..provider.dto import Tenancy


class ACLTestCase(TestCase):

    def test_allow_ids(self):
        tenancies = [Tenancy(id=f"test-id-{i}", name="") for i in range(3)]
        test_resource = {
            "metadata": {
                "annotations": {
                    ACL_ALLOW_IDS_KEY: ",".join(t.id for t in tenancies[:2])
                }
            }
        }
        self.assertTrue(allowed_by_acls(test_resource, tenancies[0]))
        self.assertTrue(allowed_by_acls(test_resource, tenancies[1]))
        self.assertFalse(allowed_by_acls(test_resource, tenancies[2]))

    def test_deny_ids(self):
        tenancies = [Tenancy(id=f"test-id-{i}", name="") for i in range(3)]
        test_resource = {
            "metadata": {
                "annotations": {ACL_DENY_IDS_KEY: ",".join(t.id for t in tenancies[:2])}
            }
        }
        self.assertFalse(allowed_by_acls(test_resource, tenancies[0]))
        self.assertFalse(allowed_by_acls(test_resource, tenancies[1]))
        self.assertTrue(allowed_by_acls(test_resource, tenancies[2]))

    def test_allow_pattern(self):
        tenancies = [Tenancy(id=f"", name=f"test-name-{i}") for i in range(3)]
        test_resource = {
            "metadata": {"annotations": {ACL_ALLOW_PATTERN_KEY: ".*-[0-1]"}}
        }
        self.assertTrue(allowed_by_acls(test_resource, tenancies[0]))
        self.assertTrue(allowed_by_acls(test_resource, tenancies[1]))
        self.assertFalse(allowed_by_acls(test_resource, tenancies[2]))

    def test_deny_pattern(self):
        tenancies = [Tenancy(id=f"", name=f"test-name-{i}") for i in range(3)]
        test_resource = {
            "metadata": {"annotations": {ACL_DENY_PATTERN_KEY: ".*-[0-1]"}}
        }
        self.assertFalse(allowed_by_acls(test_resource, tenancies[0]))
        self.assertFalse(allowed_by_acls(test_resource, tenancies[1]))
        self.assertTrue(allowed_by_acls(test_resource, tenancies[2]))

    def test_default_deny_with_allows(self):
        test_resource = {"metadata": {"annotations": {ACL_ALLOW_IDS_KEY: ""}}}
        self.assertFalse(allowed_by_acls(test_resource, Tenancy("id-1", "name-1")))
