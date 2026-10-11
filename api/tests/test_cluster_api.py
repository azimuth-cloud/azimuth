import datetime
import json
import types
import unittest

# Load the DTO definitions before the base module to match the application import order.
import azimuth.cluster_api.dto as capi_dto
from azimuth.cluster_api import base


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
            datetime.datetime(2027, 7, 31, 12, tzinfo=datetime.timezone.utc),
        )
        self.assertEqual(result.control_plane_certificate_rotation_days, 21)
        self.assertEqual(
            result.control_plane_certificate_rotation_date,
            datetime.datetime(2027, 7, 10, 12, tzinfo=datetime.timezone.utc),
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
