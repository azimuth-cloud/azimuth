"""Shared pytest fixtures."""

import pytest
from azimuth.provider import dto as cloud_dto

QUOTA_SIZES = {
    "small": cloud_dto.Size("small", "small", None, 2, 4096, 20, 0, {}),
    "large": cloud_dto.Size("large", "large", None, 8, 16384, 20, 0, {}),
}


class FakeCloudSession:
    """Provide the tenancy and machine sizes for a cloud session."""

    def username(self) -> str:
        """Return a fixed username."""
        return "test-user"

    def user_id(self) -> str:
        """Return a fixed user id."""
        return "test-user-id"

    def tenancy(self) -> cloud_dto.Tenancy:
        """Return a fixed tenancy."""
        return cloud_dto.Tenancy(id="tenancy-id", name="tenancy")

    def sizes(self) -> list[cloud_dto.Size]:
        """Return a single machine size."""
        return [cloud_dto.Size("size-id", "small", None, 2, 4096, 20, 0, {})]


class FakeQuotaSession:
    """Provide machine sizes and an unlimited CPU and machine quota."""

    def find_size(self, size_id: str) -> cloud_dto.Size:
        """Return the size with the given id."""
        return QUOTA_SIZES[size_id]

    def quotas(self) -> list[cloud_dto.Quota]:
        """Return quotas with no limit so that only the deltas matter."""
        return [
            cloud_dto.Quota(
                resource, resource, None, -1, 0, cloud_dto.QuotaType.COMPUTE
            )
            for resource in ("machines", "cpus")
        ]


@pytest.fixture
def cloud_session() -> FakeCloudSession:
    """A cloud session with a single machine size."""
    return FakeCloudSession()


@pytest.fixture
def quota_session() -> FakeQuotaSession:
    """A cloud session with "small" and "large" sizes and unlimited quotas."""
    return FakeQuotaSession()
