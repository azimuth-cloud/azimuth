"""Test how Kubernetes clusters from the Cluster API are exposed by the API."""

import dataclasses
import datetime
import typing as t

import pytest
from azimuth import serializers, views
from azimuth.cluster_api import base
from azimuth.cluster_api import dto as capi_dto
from azimuth.provider import base as cloud_base
from easykube import SyncClient
from easykube.rest.util import PropertyDict
from pytest_mock import MockerFixture


@dataclasses.dataclass
class FakeClusterClient:
    """Serve a single cluster object as if fetched from the Kubernetes API."""

    cluster: PropertyDict

    def api(self, api_version: str) -> "FakeClusterClient":
        """Return this client as the API for any version."""
        return self

    def resource(self, name: str) -> "FakeClusterClient":
        """Return this client as the resource for any name."""
        return self

    def fetch(self, name: str) -> PropertyDict:
        """Return the configured cluster."""
        return self.cluster

    def close(self) -> None:
        """Do nothing, as there is no connection to close."""


def make_cluster(
    spec: dict[str, t.Any] | None = None, status: dict[str, t.Any] | None = None
) -> PropertyDict:
    """Build a Cluster API cluster object with the given spec and status overrides."""
    return PropertyDict(
        metadata={"name": "test-cluster", "creationTimestamp": "2026-11-04T12:00:00Z"},
        spec={
            "templateName": "kube-1-34",
            "controlPlaneMachineSize": "small",
            "nodeGroups": [],
            "autohealing": True,
            "addons": {},
            **(spec or {}),
        },
        status={"phase": "Ready", **(status or {})},
    )


def find_cluster(cluster: PropertyDict, cloud_session: t.Any) -> capi_dto.Cluster:
    """Fetch a cluster through a Cluster API session."""
    session = base.Session(
        t.cast(SyncClient, FakeClusterClient(cluster)),
        t.cast(cloud_base.ScopedSession, cloud_session),
    )
    return session.find_cluster("test-cluster")


def find_cluster_as_json(
    cluster: PropertyDict, cloud_session: t.Any
) -> dict[str, t.Any]:
    """Fetch a cluster through a Cluster API session and serialize it for the UI."""
    return serializers.KubernetesClusterSerializer(
        find_cluster(cluster, cloud_session)
    ).data


def test_cluster_exposes_certificate_status(cloud_session: t.Any) -> None:
    """Check that the control plane certificate status is read from the cluster."""
    result = find_cluster(
        make_cluster(
            status={
                "controlPlaneCertificateExpiryDate": "2027-07-31T12:00:00Z",
                "controlPlaneCertificateRotationDays": 21,
                "controlPlaneCertificateRotationDate": "2027-07-10T12:00:00Z",
            }
        ),
        cloud_session,
    )

    assert result.control_plane_certificate_expiry_date == datetime.datetime(
        2027, 7, 31, 12, tzinfo=datetime.UTC
    )
    assert result.control_plane_certificate_rotation_days == 21
    assert result.control_plane_certificate_rotation_date == datetime.datetime(
        2027, 7, 10, 12, tzinfo=datetime.UTC
    )


def test_cluster_without_certificate_status_exposes_none(
    cloud_session: t.Any,
) -> None:
    """Check that a cluster with no certificate status reports each field as None."""
    result = find_cluster(make_cluster(), cloud_session)

    assert result.control_plane_certificate_expiry_date is None
    assert result.control_plane_certificate_rotation_days is None
    assert result.control_plane_certificate_rotation_date is None


@pytest.mark.parametrize("count", [1, 3])
def test_cluster_exposes_control_plane_count(count: int, cloud_session: t.Any) -> None:
    """Check that the control plane count set on a cluster is returned to the UI.

    The edit form reads this value; without it a single-node control plane is
    shown as (and resubmitted with) the default of three nodes.
    """
    data = find_cluster_as_json(
        make_cluster(spec={"controlPlaneMachineCount": count}), cloud_session
    )

    assert data["control_plane_count"] == count


def test_cluster_without_control_plane_count_exposes_none(
    cloud_session: t.Any,
) -> None:
    """Check that a cluster with no control plane count reports it as None."""
    data = find_cluster_as_json(make_cluster(), cloud_session)

    assert data["control_plane_count"] is None


def test_legacy_cluster_update_keeps_template_count(
    cloud_session: t.Any, mocker: MockerFixture
) -> None:
    """Check that updating a cluster with no count set doesn't set one."""
    client = mocker.MagicMock()
    resource = client.api.return_value.resource.return_value
    resource.patch.return_value = make_cluster()
    session = base.Session(
        t.cast(SyncClient, client), t.cast(cloud_base.ScopedSession, cloud_session)
    )

    session.update_cluster("test-cluster", control_plane_size=cloud_session.sizes()[0])

    resource.patch.assert_called_once()
    _, patch = resource.patch.call_args.args
    assert "controlPlaneMachineCount" not in patch["spec"]


def make_template(control_plane_count: int) -> capi_dto.ClusterTemplate:
    """Build a cluster template with the given control plane count."""
    return capi_dto.ClusterTemplate(
        id="kube-1-34",
        name="Kubernetes 1.34",
        description=None,
        kubernetes_version="1.34.0",
        deprecated=False,
        control_plane_count=control_plane_count,
        etcd_volume_size=0,
        control_plane_root_volume_size=0,
        node_group_root_volume_size=0,
        tags=[],
        created_at=datetime.datetime(2026, 11, 4, tzinfo=datetime.UTC),
        max_lifetime=None,
        catalogue_name="default",
        catalogue_precedence=0,
        platform_eol=False,
    )


def quota_deltas(
    quota_session: t.Any,
    cluster: capi_dto.Cluster,
    template: capi_dto.ClusterTemplate,
    **data: t.Any,
) -> dict[str, int]:
    """Run the update quota check and return the change in each resource."""
    cluster = dataclasses.replace(cluster, control_plane_size_id="small")
    _, fits, quotas = views.kubernetes_cluster_check_quotas(
        quota_session, cluster, template, **data
    )
    assert fits
    return {q.resource: q.delta for q in quotas}


def test_control_plane_resize_uses_cluster_count(
    cloud_session: t.Any, quota_session: t.Any
) -> None:
    """Check that resizing the control plane is charged for the cluster's count.

    A single-node cluster on a template that deploys three nodes was previously
    charged for resizing three control plane machines.
    """
    cluster = find_cluster(
        make_cluster(spec={"controlPlaneMachineCount": 1}), cloud_session
    )

    deltas = quota_deltas(
        quota_session,
        cluster,
        make_template(control_plane_count=3),
        control_plane_size=quota_session.find_size("large"),
    )

    assert deltas == {"machines": 0, "cpus": 6}


@pytest.mark.parametrize(
    ("current", "requested", "machines"),
    [(1, 3, 2), (3, 1, -2), (None, 1, -2), (None, 3, 0)],
)
def test_control_plane_count_change_is_charged(
    current: int | None,
    requested: int,
    machines: int,
    cloud_session: t.Any,
    quota_session: t.Any,
) -> None:
    """Check that changing the control plane count changes the machines charged.

    A cluster with no count set uses the template's count of three.
    """
    spec = {"controlPlaneMachineCount": current} if current is not None else {}
    cluster = find_cluster(make_cluster(spec=spec), cloud_session)

    deltas = quota_deltas(
        quota_session,
        cluster,
        make_template(control_plane_count=3),
        control_plane_count=requested,
    )

    assert deltas == {"machines": machines, "cpus": machines * 2}


@pytest.mark.parametrize("count", [1, 3])
def test_update_accepts_control_plane_count(count: int) -> None:
    """Check that an update can change the control plane count."""
    serializer = serializers.UpdateKubernetesClusterSerializer(
        data={"control_plane_count": count}
    )

    assert serializer.is_valid(), serializer.errors
    assert serializer.validated_data == {"control_plane_count": count}


def test_update_rejects_even_control_plane_count() -> None:
    """Check that an update can't set a count other than one or three."""
    serializer = serializers.UpdateKubernetesClusterSerializer(
        data={"control_plane_count": 2}
    )

    assert not serializer.is_valid()
    assert "control_plane_count" in serializer.errors


def test_condition_from_dict() -> None:
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

    test_condition = base.condition_from_dict(valid_test_dict_full)

    assert test_condition.last_transition_time == datetime.datetime(
        2026, 11, 2, 10, 31, 24, tzinfo=datetime.UTC
    )

    assert test_condition.message == "test message"
    assert test_condition.reason == "testReason"
    assert test_condition.status == capi_dto.ConditionStatus.TRUE
    assert test_condition.severity == capi_dto.ConditionSeverity.INFO
    assert test_condition.type == "Testing"

    # Test correct parsing of valid dict with minimal data
    valid_test_dict_min = {
        "lastTransitionTime": "2026-11-02T10:31:24Z",
        "reason": "testReason",
        "status": "Unknown",
        "type": "Testing",
    }

    test_condition = base.condition_from_dict(valid_test_dict_min)

    assert test_condition.last_transition_time == datetime.datetime(
        2026, 11, 2, 10, 31, 24, tzinfo=datetime.UTC
    )
    assert test_condition.reason == "testReason"
    assert test_condition.status == capi_dto.ConditionStatus.UNKNOWN
    assert test_condition.type == "Testing"

    # Check that parsing an invalid time raises an exception
    invalid_time_test_dict = {
        "lastTransitionTime": "notATime",
        "reason": "testReason",
        "status": "True",
        "type": "Testing",
    }

    with pytest.raises(ValueError):
        base.condition_from_dict(invalid_time_test_dict)

    # Test invalid values for enums default correctly
    invalid_enums_test_dict = {
        "lastTransitionTime": "2026-02-02T22:57:26.000Z",
        "reason": "testReason",
        "status": "INVALID",
        "type": "Testing",
        "severity": "INVALID",
    }

    test_condition = base.condition_from_dict(invalid_enums_test_dict)
    assert test_condition.status == capi_dto.ConditionStatus.UNKNOWN
