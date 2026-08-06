"""Settings for running the api test suite."""

from pathlib import Path
from unittest import mock

import easykube
from flexi_settings import include

# Patch out requirement for kubeconfig at runtime in tests.
mock.patch.object(
    easykube.Configuration,
    "from_environment",
    classmethod(lambda cls, **kwargs: cls(**kwargs)),
).start()

etc_azimuth = Path(__file__).resolve().parent.parent / "etc" / "azimuth"

include(etc_azimuth / "defaults.py")
include(etc_azimuth / "app.py")

AZIMUTH_AUTH = {
    "AUTH_TYPE": "openstack",
    "OPENSTACK": {"AUTH_URL": "https://openstack.example.test:5000/v3"},
}
