import datetime
import json
import types
import unittest

# Load the DTO definitions before the base module to match the application import order.
import azimuth.cluster_api.dto as capi_dto
from azimuth.cluster_api import base
from azimuth.cluster_api.base import condition_from_dict


class AttrDict(dict):
    __getattr__ = dict.__getitem__


class ClusterApiTest(unittest.TestCase):
    def test_cluster_certificate_status_is_exposed(self):
        spec = {
            "templateName": "kubernetes-v1.34",
            "controlPlaneMachineSize": "medium",
            "nodeGroups": [],
            "autohealing": True,
            "addons": {},
        }
        cluster = AttrDict(
            metadata=AttrDict(
                name="test-cluster",
                creationTimestamp="2026-07-31T12:00:00Z",
                annotations={
                    "azimuth.stackhpc.com/last-handled-configuration": json.dumps(
                        {"spec": spec}
                    )
                },
            ),
            spec=spec,
            status={
                "phase": "Ready",
                "controlPlanePhase": "Ready",
                "controlPlaneCertificateExpiryDate": "2027-07-31T12:00:00Z",
                "controlPlaneCertificateRotationDays": 21,
                "controlPlaneCertificateRotationDate": "2027-07-10T12:00:00Z",
            },
        )
        sizes = [types.SimpleNamespace(id="medium-id", name="medium")]

        client = types.SimpleNamespace(close=lambda: None)
        result = base.Session(client, None)._from_api_cluster(cluster, sizes)

        self.assertIsInstance(result, capi_dto.Cluster)
        self.assertEqual(
            result.control_plane_certificate_expiry_date,
            datetime.datetime(2027, 7, 31, 12, tzinfo=datetime.UTC),
        )
        self.assertEqual(result.control_plane_certificate_rotation_days, 21)
        self.assertEqual(
            result.control_plane_certificate_rotation_date,
            datetime.datetime(2027, 7, 10, 12, tzinfo=datetime.UTC),
        )

    def test_missing_cluster_certificate_status_is_supported(self):
        spec = {
            "templateName": "kubernetes-v1.34",
            "controlPlaneMachineSize": "medium",
            "nodeGroups": [],
            "autohealing": True,
            "addons": {},
        }
        cluster = AttrDict(
            metadata=AttrDict(
                name="test-cluster",
                creationTimestamp="2026-07-31T12:00:00Z",
                annotations={
                    "azimuth.stackhpc.com/last-handled-configuration": json.dumps(
                        {"spec": spec}
                    )
                },
            ),
            spec=spec,
            status={"phase": "Ready", "controlPlanePhase": "Ready"},
        )
        sizes = [types.SimpleNamespace(id="medium-id", name="medium")]

        client = types.SimpleNamespace(close=lambda: None)
        result = base.Session(client, None)._from_api_cluster(cluster, sizes)

        self.assertIsNone(result.control_plane_certificate_expiry_date)
        self.assertIsNone(result.control_plane_certificate_rotation_days)
        self.assertIsNone(result.control_plane_certificate_rotation_date)

    def test_condition_from_dict(self):
        """
        Tests the function designed to parse dicts from capi-operator and
        create condition objects
        """

        # Test correct parsing of valid dict with all data
        valid_test_dict_full = {
            "lastTransitionTime": "2026-11-02T10:31:24Z",
            "message": "test message",
            "reason": "testReason",
            "status": "True",
            "severity": "Info",
            "type": "Testing",
        }

        test_condition = condition_from_dict(valid_test_dict_full)

        self.assertEqual(
            test_condition.last_transition_time,
            datetime.datetime(2026, 11, 2, 10, 31, 24, tzinfo=datetime.UTC),
        )
        self.assertEqual(test_condition.message, "test message")
        self.assertEqual(test_condition.reason, "testReason")
        self.assertEqual(test_condition.status, capi_dto.ConditionStatus.TRUE)
        self.assertEqual(test_condition.severity, capi_dto.ConditionSeverity.INFO)
        self.assertEqual(test_condition.type, "Testing")

        # Test correct parsing of valid dict with minimal data
        valid_test_dict_min = {
            "lastTransitionTime": "2026-11-02T10:31:24Z",
            "reason": "testReason",
            "status": "Unknown",
            "type": "Testing",
        }

        test_condition = condition_from_dict(valid_test_dict_min)

        self.assertEqual(
            test_condition.last_transition_time,
            datetime.datetime(2026, 11, 2, 10, 31, 24, tzinfo=datetime.UTC),
        )
        self.assertEqual(test_condition.reason, "testReason")
        self.assertEqual(test_condition.status, capi_dto.ConditionStatus.UNKNOWN)
        self.assertEqual(test_condition.type, "Testing")

        # Check that parsing an invalid time raises an exception
        invalid_time_test_dict = {
            "lastTransitionTime": "notATime",
            "reason": "testReason",
            "status": "True",
            "type": "Testing",
        }

        with self.assertRaises(ValueError):
            condition_from_dict(invalid_time_test_dict)

        # Test invalid values for enums default correctly
        invalid_enums_test_dict = {
            "lastTransitionTime": "2026-02-02T22:57:26.000Z",
            "reason": "testReason",
            "status": "INVALID",
            "type": "Testing",
            "severity": "INVALID",
        }

        test_condition = condition_from_dict(invalid_enums_test_dict)
        self.assertEqual(test_condition.status, capi_dto.ConditionStatus.UNKNOWN)
