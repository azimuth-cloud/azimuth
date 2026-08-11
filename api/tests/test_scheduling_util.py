"""Test scheduling utilities and lifetimes."""

import datetime as dt
from types import SimpleNamespace
from unittest import TestCase, mock

from azimuth.scheduling.util import (
    check_max_platform_lifetime,
    lifetime_from_annotations,
)

from tests.helpers import override_cloud_settings

FIXED_NOW = dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc)


class LifetimeFromAnnotationsTestCase(TestCase):
    """Test serialisation to/from the lifetime annotation."""

    def test_valid_annotation(self):
        annotations = {"scheduling.azimuth.stackhpc.com/max-lifetime-hours": "12"}
        self.assertEqual(lifetime_from_annotations(annotations), dt.timedelta(hours=12))

    def test_no_annotation(self):
        self.assertIsNone(lifetime_from_annotations({}))

    def test_empty_annotation(self):
        annotations = {"scheduling.azimuth.stackhpc.com/max-lifetime-hours": ""}
        self.assertIsNone(lifetime_from_annotations(annotations))


class CheckMaxPlatformLifetimeTestCase(TestCase):
    def setUp(self):
        # Patch now to be fixed.
        patcher = mock.patch("azimuth.scheduling.util.dt.datetime")
        mock_datetime = patcher.start()
        mock_datetime.now.return_value = FIXED_NOW
        self.addCleanup(patcher.stop)

    def platform_data(self, *, end_time):
        return {"schedule": SimpleNamespace(end_time=end_time)}

    def test_no_max_lifetime(self):
        with override_cloud_settings(SCHEDULING={"ENABLED": True}):
            platform_data = self.platform_data(
                end_time=FIXED_NOW + dt.timedelta(hours=1000)
            )
            self.assertTrue(check_max_platform_lifetime(platform_data, None))

    def test_scheduling_disabled(self):
        with override_cloud_settings(SCHEDULING={"ENABLED": False}):
            platform_data = self.platform_data(
                end_time=FIXED_NOW + dt.timedelta(hours=1000)
            )
            self.assertTrue(
                check_max_platform_lifetime(platform_data, dt.timedelta(hours=1))
            )

    def test_lifetime_within_max(self):
        with override_cloud_settings(SCHEDULING={"ENABLED": True}):
            platform_data = self.platform_data(
                end_time=FIXED_NOW + dt.timedelta(hours=1)
            )
            self.assertTrue(
                check_max_platform_lifetime(platform_data, dt.timedelta(hours=12))
            )

    def test_lifetime_at_max_boundary(self):
        # Existing behaviour- boundary is < not <=.
        with override_cloud_settings(SCHEDULING={"ENABLED": True}):
            max_lifetime = dt.timedelta(hours=12)
            platform_data = self.platform_data(end_time=FIXED_NOW + max_lifetime)
            self.assertFalse(check_max_platform_lifetime(platform_data, max_lifetime))

    def test_lifetime_exceeds_max(self):
        with override_cloud_settings(SCHEDULING={"ENABLED": True}):
            platform_data = self.platform_data(
                end_time=FIXED_NOW + dt.timedelta(hours=24)
            )
            self.assertFalse(
                check_max_platform_lifetime(platform_data, dt.timedelta(hours=12))
            )
